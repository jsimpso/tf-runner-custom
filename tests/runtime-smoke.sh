#!/bin/bash
# Executed inside the candidate image, never directly against the host.
set -euo pipefail
test "$(id -u)" = 65532
test "$(id -un)" = runner
mkdir -p "$TF_PLUGIN_CACHE_DIR" "$HOME/.local/share/juju" /tmp/tf-smoke
for tool in sh bash python3 terraform tf-runner git ssh curl jq tar gzip xz unzip; do
  command -v "$tool"
done
for tool in apt apt-get dpkg vim cc gcc pip pip3; do
  if command -v "$tool"; then echo "Unexpected build/admin tool: $tool" >&2; exit 1; fi
done
python3 - <<'PY'
import boto3
import ldap
import hvac
import openstack
import openstackclient
import netaddr
import ssl
import pwd
import os
import pathlib
import certifi
import importlib.metadata
import base64
import hashlib
assert pwd.getpwuid(65532).pw_name == "runner"
assert ssl.create_default_context().get_ca_certs()
assert netaddr.EUI("00:1B:63:00:00:01").oui.registration().org
assert os.path.samefile(certifi.where(), "/etc/ssl/certs/ca-certificates.crt")
assert ldap.get_option(ldap.OPT_X_TLS_CACERTFILE) == "/etc/ssl/certs/ca-certificates.crt"
assert importlib.metadata.version("python-openstackclient") == "6.6.0"
assert importlib.metadata.version("python-ldap") == "3.4.8"
assert list(pathlib.Path("/var/lib/chisel").glob("*.wall")), "Missing Chisel manifest"
assert pathlib.Path("/usr/share/tf-runner/python-requirements.txt").is_file()
distribution = importlib.metadata.distribution("python-openstackclient")
script = next(file for file in distribution.files if file.name == "openstack" and "bin" in file.parts)
path = distribution.locate_file(script)
assert os.path.samefile(path, "/usr/local/bin/openstack")
assert script.hash.value == base64.urlsafe_b64encode(hashlib.sha256(path.read_bytes()).digest()).rstrip(b"=").decode()
PY
if [ "$RUNNER_PROFILE" = ubuntu ]; then
  python3 -c 'import launchpadlib'
  if command -v juju; then echo 'Unexpected Juju client in base profile' >&2; exit 1; fi
else
  juju version | grep -F 3.6.27
fi
terraform version -json | jq -e '.terraform_version == "1.15.5"'
openstack --version
git --version
# Unlike git_bins alone, this exercises the HTTPS transport helper and DNS/TLS.
git ls-remote https://github.com/flux-iac/tofu-controller.git HEAD
ssh -V
openssl verify -CAfile /etc/ssl/certs/ca-certificates.crt \
  /usr/local/share/ca-certificates/hermitcrab-mirror-ca.crt
# A git module source, which Terraform clones and then runs `git submodule update`
# on. The image only clones from remote servers, so it has no git-upload-pack;
# this test-only alias plays the server's part for a local repository.
mkdir -p /tmp/git-server-bin /tmp/tf-module
ln -s /usr/lib/git-core/git /tmp/git-server-bin/git-upload-pack
export PATH="/tmp/git-server-bin:$PATH"
git -C /tmp/tf-module init -q
echo 'output "source" { value = "git-module-ok" }' > /tmp/tf-module/main.tf
git -C /tmp/tf-module add main.tf
git -C /tmp/tf-module -c user.name=smoke -c user.email=smoke@example.invalid commit -q -m module
git -C /tmp/tf-module tag v1
cd /tmp/tf-smoke
cat > main.tf <<'EOF'
module "git_source" {
  source = "git::file:///tmp/tf-module?ref=v1"
}

output "module_source" {
  value = module.git_source.source
}

resource "terraform_data" "smoke" {
  input = "rock"
  provisioner "local-exec" {
    command = "python3 -c 'import boto3, ldap, hvac; print(\"runtime-ok\")' | tee runtime.txt"
  }
}
EOF
terraform init -input=false
terraform validate
terraform plan -input=false -out=plan
terraform apply -input=false plan
grep -q runtime-ok runtime.txt
test "$(terraform output -raw module_source)" = git-module-ok
terraform destroy -auto-approve -input=false
