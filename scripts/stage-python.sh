#!/bin/bash
# Build-only pip installs a fully hash-locked dependency set. Neither pip nor
# its build venv is included in the Rock. Keep dist-info and bundled licenses.
set -euo pipefail
profile=${1:?Usage: stage-python.sh ubuntu|juju}
case "$profile" in ubuntu) lock=ubuntu ;; juju) lock=common ;; *) exit 2 ;; esac
install_dir=${CRAFT_PART_INSTALL:?}
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
python3 -m venv "$work/build"
"$work/build/bin/pip" install --require-hashes -r rocks/python/build.txt
site_dir="$install_dir/usr/local/lib/python3.12/dist-packages"
# A changed lock can remove packages; do not retain stale files on a rebuild.
if [ -d "$site_dir" ]; then rm -rf "${site_dir:?}"; fi
"$work/build/bin/pip" install --require-hashes --no-build-isolation --no-compile --no-cache-dir \
  --target "$site_dir" -r "rocks/python/$lock.txt"

# --target puts console scripts in dist-packages/bin, with a temporary build
# interpreter in their shebang. Place them on PATH and use the sliced Python.
mkdir -p "$install_dir/usr/local/bin"
for script in "$site_dir"/bin/*; do
  [ -f "$script" ] || continue
  sed '1s|^#!.*python.*$|#!/usr/bin/python3.12|' "$script" \
    > "$install_dir/usr/local/bin/$(basename "$script")"
  chmod 0755 "$install_dir/usr/local/bin/$(basename "$script")"
done
# Match RECORD paths and hashes to relocated scripts and rewritten shebangs.
python3 - "$site_dir" "$install_dir/usr/local/bin" <<'PY'
import base64
import csv
import hashlib
import io
import os
from pathlib import Path
import sys
site, scripts = map(Path, sys.argv[1:])
for record in site.glob("*.dist-info/RECORD"):
    rows = list(csv.reader(io.StringIO(record.read_text())))
    for row in rows:
        original = Path(row[0])
        script = scripts / original.name
        if original.parent.name == "bin" and script.is_file():
            content = script.read_bytes()
            digest = base64.urlsafe_b64encode(hashlib.sha256(content).digest()).rstrip(b"=").decode()
            row[:] = [os.path.relpath(script, site), "sha256=" + digest, str(len(content))]
    output = io.StringIO()
    csv.writer(output).writerows(rows)
    record.write_text(output.getvalue())
PY
if [ -d "$site_dir/bin" ]; then rm -rf "${site_dir:?}/bin"; fi
# Store the dependency inventory used for this build alongside Python metadata.
install -D -m 0644 "rocks/python/$lock.txt" "$install_dir/usr/share/tf-runner/python-requirements.txt"
