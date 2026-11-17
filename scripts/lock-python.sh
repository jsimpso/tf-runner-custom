#!/bin/bash
# Regenerate, do not hand-edit the PyPI lockfiles. Requires uv on the host.
set -euo pipefail
repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd "$repo"
for profile in common ubuntu build; do
  uv pip compile "rocks/python/$profile.in" \
    --python-version 3.14 --python-platform x86_64-manylinux_2_40 \
    --generate-hashes --no-annotate \
    --output-file "rocks/python/$profile.txt"
done
