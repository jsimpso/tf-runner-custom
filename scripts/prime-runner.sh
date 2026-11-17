#!/bin/bash
# Extend Chisel's trust bundle and prepare runtime accounts and aliases.
set -euo pipefail
prime=${CRAFT_PRIME:?}
mkdir -p "$prime/etc/ssl/certs" "$prime/etc" "$prime/home/runner"
# /bin/sh is normally selected by dash's maintainer script, which is not run
# when assembling a bare filesystem from unpacked runtime DEBs.
ln -sf dash "$prime/usr/bin/sh"
# Python's versioned slice does not supply the unversioned CLI alias.
ln -sf python3.14 "$prime/usr/bin/python3"
# libldap2_libs does not include libldap-common's configuration. Preserve the
# Ubuntu baseline's default TLS trust store for native LDAP clients as well.
mkdir -p "$prime/etc/ldap"
printf 'TLS_CACERT /etc/ssl/certs/ca-certificates.crt\n' > "$prime/etc/ldap/ldap.conf"
# OpenSSH 10.1+ warns on stderr when a server lacks post-quantum key exchange.
# Modules that treat any ssh stderr as failure (e.g. Plinth subnet lookups) then
# fail, so keep the quieter pre-26.04 behaviour until those servers support it.
mkdir -p "$prime/etc/ssh/ssh_config.d"
printf 'WarnWeakCrypto no\n' > "$prime/etc/ssh/ssh_config.d/50-tf-runner.conf"
# ca-certificates_data supplies the public bundle, not individual certificates.
# Preserve it, and avoid appending the private mirror's public CA twice on reprime.
python3 - "$prime" <<'PY'
from pathlib import Path
import base64
import csv
import hashlib
import io
import sys
root = Path(sys.argv[1])
bundle = root / "etc/ssl/certs/ca-certificates.crt"
mirror = (root / "usr/local/share/ca-certificates/hermitcrab-mirror-ca.crt").read_bytes()
public = bundle.read_bytes()
if not public:
    raise ValueError("Chisel's public CA bundle is empty")
if mirror not in public:
    bundle.write_bytes(public.rstrip(b"\n") + b"\n" + mirror)
# PyPI certifi normally brings its own CA store. Use Ubuntu's augmented store
# for requests, botocore and httplib2, as Ubuntu's certifi DEB did in the baseline.
certifi = root / "usr/local/lib/python3.14/dist-packages/certifi/cacert.pem"
certifi.unlink(missing_ok=True)
certifi.symlink_to("/etc/ssl/certs/ca-certificates.crt")
# Keep RECORD accurate for the deliberately substituted CA store rather than
# discarding package metadata. All other Python files retain their wheel hashes.
digest = base64.urlsafe_b64encode(hashlib.sha256(bundle.read_bytes()).digest()).rstrip(b"=").decode()
for record in certifi.parent.parent.glob("certifi-*.dist-info/RECORD"):
    rows = list(csv.reader(io.StringIO(record.read_text())))
    for row in rows:
        if row[0] == "certifi/cacert.pem":
            row[1:] = ["sha256=" + digest, str(bundle.stat().st_size)]
    stream = io.StringIO()
    csv.writer(stream).writerows(rows)
    record.write_text(stream.getvalue())
PY
# The controller's numeric UID must resolve for SSH and Python account lookups.
touch "$prime/etc/passwd" "$prime/etc/group"
if ! grep -q '^runner:' "$prime/etc/passwd"; then
  printf 'runner:x:65532:65532:Terraform runner:/home/runner:/bin/bash\n' >> "$prime/etc/passwd"
fi
if ! grep -q '^runner:' "$prime/etc/group"; then
  printf 'runner:x:65532:\n' >> "$prime/etc/group"
fi
# Rockcraft adds _daemon_ (584792) at packing time. The controller replaces this
# UID and mounts an empty /home/runner, so runtime directories are created then.
chown 584792:584792 "$prime/home/runner"
chmod 0755 "$prime/home/runner"
