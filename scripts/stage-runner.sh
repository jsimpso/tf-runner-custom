#!/bin/bash
# Run inside the Rockcraft runner part's source directory.
set -euo pipefail
profile=${1:?Usage: stage-runner.sh ubuntu|juju}
case "$profile" in ubuntu|juju) ;; *) exit 2 ;; esac
# shellcheck source=rocks/versions.env
source rocks/versions.env
install_dir=${CRAFT_PART_INSTALL:?}
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
mkdir -p "$install_dir/usr/local/bin" "$install_dir/usr/local/share/ca-certificates"

skopeo --insecure-policy copy "docker://$RUNNER_IMAGE" "oci:$work/runner:base"
umoci unpack --rootless --image "$work/runner:base" "$work/bundle"
install -m 0755 "$work/bundle/rootfs/usr/local/bin/tf-runner" "$install_dir/usr/local/bin/tf-runner"

curl --fail --location --retry 3 \
  "https://releases.hashicorp.com/terraform/$TF_VERSION/terraform_${TF_VERSION}_linux_amd64.zip" \
  -o "$work/terraform.zip"
printf '%s  %s\n' "$TF_SHA256" "$work/terraform.zip" | sha256sum --check --strict
unzip -q "$work/terraform.zip" -d "$work/terraform"
install -m 0755 "$work/terraform/terraform" "$install_dir/usr/local/bin/terraform"
install -D -m 0644 "$work/terraform/LICENSE.txt" "$install_dir/usr/share/doc/terraform/LICENSE.txt"

if [ "$profile" = juju ]; then
  curl --fail --location --retry 3 \
    "https://github.com/juju/juju/releases/download/v$JUJU_VERSION/juju-$JUJU_VERSION-linux-amd64.tar.xz" \
    -o "$work/juju.tar.xz"
  printf '%s  %s\n' "$JUJU_SHA256" "$work/juju.tar.xz" | sha256sum --check --strict
  mkdir "$work/juju"
  tar -xJf "$work/juju.tar.xz" -C "$work/juju"
  install -m 0755 "$work/juju/juju" "$install_dir/usr/local/bin/juju"
fi
# Chisel's git slices ship only the git binary and transport helpers, not git's
# shell-script commands. Terraform's module getter runs `git submodule update`
# after every git clone, so add git-submodule and the shell libraries it sources,
# taken from the same git DEB as the chiselled binary.
git_core=usr/lib/git-core
(cd "$work" && apt-get -o APT::Sandbox::User=root download git)
dpkg-deb -x "$work"/git_*.deb "$work/git-deb"
if ! cmp -s "$work/git-deb/$git_core/git" "${CRAFT_STAGE:?}/$git_core/git"; then
  echo "Downloaded git DEB does not match the chiselled git binary" >&2
  exit 1
fi
for helper in git-submodule git-sh-setup git-sh-i18n git-sh-i18n--envsubst; do
  install -D -m "$(stat -c %a "$work/git-deb/$git_core/$helper")" \
    "$work/git-deb/$git_core/$helper" "$install_dir/$git_core/$helper"
done
install -m 0755 scripts/start-runner.sh "$install_dir/usr/local/bin/start-runner"
install -D -m 0644 LICENSE "$install_dir/usr/share/doc/tf-runner-rock/LICENSE"
ca_dir=tf-runner-ubuntu
if [ "$profile" = juju ]; then ca_dir=tf-runner-juju-ubuntu; fi
install -m 0644 "$ca_dir/hermitcrab-mirror-ca.crt" \
  "$install_dir/usr/local/share/ca-certificates/hermitcrab-mirror-ca.crt"
