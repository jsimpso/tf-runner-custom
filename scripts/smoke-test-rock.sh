#!/bin/bash
# Test a locally loaded Rock with the controller's security and volume contract.
set -euo pipefail
image=${1:?Usage: smoke-test-rock.sh IMAGE ubuntu|juju}
profile=${2:?Usage: smoke-test-rock.sh IMAGE ubuntu|juju}
case "$profile" in ubuntu|juju) ;; *) exit 2 ;; esac
engine=${CONTAINER_ENGINE:-docker}
security=(--rm --read-only --user '65532:65532' --cap-drop ALL
  --security-opt no-new-privileges
  --tmpfs '/tmp:rw,nosuid,nodev,mode=1777'
  --tmpfs '/home/runner:rw,nosuid,nodev,uid=65532,gid=65532,mode=0700')

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
# Exercise the REAL entrypoint with a running mTLS server, at both runtime UIDs.
python3 "$script_dir/../tests/entrypoint_smoke.py" --engine "$engine" "$image"

# Feed the test over stdin: no bind mount or writable root is needed.
"$engine" run -i "${security[@]}" -e "RUNNER_PROFILE=$profile" \
  --entrypoint /bin/bash "$image" -s < "$script_dir/../tests/runtime-smoke.sh"
