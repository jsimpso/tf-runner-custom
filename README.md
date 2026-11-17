# tf-runner-custom

Custom Terraform runners for tofu-controller. The existing Dockerfiles and
publishing workflows remain unchanged while the Rockcraft candidates are tested.

## Candidate Ubuntu Rocks

Two amd64 recipes are provided:

| Project | Terraform | Juju | Additional Python client |
| --- | --- | --- | --- |
| `rocks/tf-runner-ubuntu` | 1.15.5 | No | Launchpad |
| `rocks/tf-runner-juju-ubuntu` | 1.15.5 | 3.6.27 | — |

Both include boto3, python-ldap, hvac, OpenStack clients, Git, SSH, curl, jq and
shell utilities used by infrastructure modules. Build-only tools and development
headers are not staged; the smoke test rejects package managers, pip, editors
and compilers. Upstream runner and binary download pins are recorded in
`rocks/versions.env`. Ubuntu runtime packages receive updates from the Noble
archive, so rebuilding may produce a different digest even without a version bump.

### Chiselled runtime and locked Python clients

The `runtime` part uses only official Ubuntu 24.04 Chisel slices on `base: bare`.
It includes the shell/network tools, Git's separate HTTPS helper, Python 3.12
standard library and native LDAP/SASL libraries. `base-files_chisel` explicitly
requests a Chisel manifest under `/var/lib/chisel`; the smoke suite checks that
the manifest is retained. Scanner support for this inventory varies by tool.

The third-party Python clients do not have upstream Noble slices. They are
installed separately from hash-locked PyPI artifacts under
`/usr/local/lib/python3.12/dist-packages`, retaining distribution metadata and
licenses. `python-ldap` is compiled against Ubuntu libraries in the build
environment only. Console-script shebangs use the sliced interpreter, not the
temporary build venv. This is a **chiselled Ubuntu runtime plus Python application
dependencies**, not a claim that every third-party file came from Chisel.
Console-script RECORD paths and hashes are updated for their relocation.

The existing boto3, hvac, OpenStack client/SDK and Launchpad client APIs remain
pinned; python-ldap moves to 3.4.8. Other dependencies are locked after resolution.
PyPI packages do not receive Ubuntu's security backports, so cryptography,
requests use maintained versions rather than copying older DEB version numbers.
Wheel exists only in the build venv; pbr also declares setuptools as a runtime
metadata dependency, so a maintained version is retained there. CI audits runtime
and build locks for known Python vulnerabilities.
This audit does not cover the Go binaries or replace whole-image scanning.

Inputs and generated locks are under `rocks/python/`. With `uv` installed,
regenerate them using `bash scripts/lock-python.sh`; review dependency changes and
rerun both container suites. Build tools are separately hash-locked, and pip
enforces hashes with build isolation disabled. Do not strip `.dist-info/RECORD`
or other inventory metadata to save space.

The earlier bare-DEB baseline was approximately 187 MiB (Ubuntu) / 233 MiB
(Juju) uncompressed. Its version was `1.15.5-1`; the chiselled candidate is
`1.15.5-2`. Compare inventories, sizes and compatibility before promotion.
The runner needs shell execution; a shell-free image would not be compatible.

Local validation with Rockcraft 1.21.2 (amd64, 2026-11-07):

| Variant | Bare-DEB baseline | Chiselled candidate | Reduction |
| --- | ---: | ---: | ---: |
| Ubuntu | 187 MiB | 128 MiB | 32% |
| Juju + Ubuntu | 233 MiB | 173 MiB | 26% |

Both candidates passed the container smoke suite. Seven unit tests and static
checks passed, and the locked Python runtime/build dependency audit reported no
known vulnerabilities. This is not a whole-image security audit or proof of full
controller/cloud reconciliation.

### Runtime contract

The tofu-controller v0.16.3 runner pod passes `--grpc-port`, `--tls-secret-name`
and `--grpc-max-message-size` as OCI arguments. It runs as UID 65532, drops all
capabilities and mounts writable `/tmp` and `/home/runner` on a read-only root.

The native `entrypoint-service` binds controller arguments to the `tf-runner`
service. `PEBBLE=/tmp/pebble` and `PEBBLE_COPY_ONCE` copy the immutable Pebble layer
to writable `/tmp`. The service runs `scripts/start-runner.sh`, which creates the
plugin/Juju directories in the mounted home and executes `tf-runner` with those
arguments. Pebble remains the supervisor; the `.rock` archive is not rewritten
after packing. Rockcraft warns about binding OCI arguments to an entrypoint service;
obtain any required Canonical registry approval before moving publication there.

Rockcraft supports `_daemon_` (UID 584792) as its non-root OCI default user. The
recipe uses that for standalone runs, while the controller overrides it to 65532.
A `runner` account with UID/GID 65532 is also included for SSH/account lookups.
`HOME` is explicitly `/home/runner` in both cases.

Both recipes preserve the public Hermitcrab mirror CA from the corresponding
Docker build context and combine it with the Ubuntu trust bundle at build time.
PyPI certifi is deliberately pointed at that augmented Ubuntu bundle, matching
the baseline's distro behavior. Its RECORD entry is updated for the substitution.
Native LDAP is also configured to use the augmented Ubuntu CA bundle.

### Build and test locally

Install Rockcraft using `sudo snap install rockcraft --classic`, with a working
LXD build provider. Rockcraft 1.21+ monorepo support is required to mount the Git
root (including shared scripts, locks and certificates) in the managed builder;
without it only the recipe directory is visible. Run from each project directory:

```bash
cd rocks/tf-runner-ubuntu
ROCKCRAFT_EXPERIMENTAL_MONOREPO=1 rockcraft pack
sudo rockcraft.skopeo --insecure-policy copy \
  oci-archive:tf-runner-ubuntu-rock_1.15.5-2_amd64.rock \
  docker-daemon:tf-runner-ubuntu-rock:test
cd ../..
bash scripts/smoke-test-rock.sh tf-runner-ubuntu-rock:test ubuntu
```

Repeat for `tf-runner-juju-ubuntu`, using profile `juju`. Set
`CONTAINER_ENGINE=podman` when testing a candidate loaded into Podman's store.
Rootless Podman needs a subordinate UID/GID range covering 584792 for the Rock's
default user; otherwise use rootful Docker/Podman without changing your host mapping.

The smoke suite starts the actual entrypoint against a loopback mock Kubernetes
Secret API, establishes an mTLS/HTTP2 handshake at the configured gRPC port, and
checks shutdown at both runtime UIDs. It also checks read-only execution, Python
imports (including native LDAP), tools and versions, the mirror CA, and an offline
Terraform init/plan/apply/destroy with `local-exec`. Only dummy, ephemeral TLS
credentials are used. The test requires host networking on Linux.
It does **not** establish full controller reconciliation or access to live clouds.
Before promoting a digest, use a disposable controller environment to exercise
those paths and representative external-data/provisioner modules as well.

Fast tests, without packing:

```bash
python3 -m venv /tmp/tf-runner-tests
/tmp/tf-runner-tests/bin/pip install -r tests/requirements.txt
/tmp/tf-runner-tests/bin/python -m unittest discover -s tests -v
shellcheck -x scripts/*.sh
```

### GitHub Actions and GHCR

`build-rocks.yaml` builds and smoke-tests both recipes on relevant PRs and pushes,
and uploads the tested `.rock` files as workflow artifacts. PR artifacts are kept
for 3 days; main/manual build artifacts for 14 days. OCI archives are uploaded
without extra ZIP compression. This policy applies to new uploads, not existing
artifacts. The build workflow never has package-write permissions.

Publication is **opt-in and does not rebuild**. Run `publish-rocks.yaml` on `main`:

```bash
# Publish the latest successful push build from main.
gh workflow run publish-rocks.yaml --ref main

# Or promote a particular tested main push build.
gh workflow run publish-rocks.yaml --ref main -f build_run_id=43995318317
```

The optional run ID defaults to the newest successful `build-rocks.yaml` push
run from `main`. Selection is resolved once for both images. The selector checks
the repository, workflow, event, branch, successful completion, current main
ancestry and both unexpired artifacts before granting publication to either job.
PR and manual build runs are not eligible. Missing/expired artifacts fail clearly;
there is no silent fallback to an older run. Choose another eligible run explicitly
or trigger a fresh main push build. Downloads use immutable artifact IDs with a
read-only Actions token. Publishing jobs do not check out or execute source code
from the selected build; they only copy the saved OCI archives into GHCR.

Both variants receive a readable tag such as
`tf-1.15.5_runner-0.16.3_u24.04_r2`, plus the existing `sha-<source-commit>` tag.
Terraform and runner versions come from `rocks/versions.env` at the selected
build's SHA; Ubuntu comes from the recipe's build-base and `r2` from its
`version: 1.15.5-2`. No Juju version is included. Historical builds without
`RUNNER_VERSION` are supported only for the explicitly verified legacy runner
digest, not inferred from current main. Archive version labels must match the
selected recipe. The publisher checks both tags before copying and refuses to
replace either with a different digest; an identical digest is an idempotent no-op.
If image contents change without a Terraform, runner or Ubuntu version change,
increment the Rock revision in **both recipes**. Never reuse a release tag for a
different build. The workflow serializes its own publishes, but GHCR does not
enforce immutability against other clients, so do not manually move these tags.

Image tags use **source build metadata**, not the publishing workflow commit.
The job summary records the source run, tags and published image digest. The OCI
manifest digest is preserved during copying. Publishing is serialized; each image
is a separate job, so a failed publication can leave one image published. Rerun
against the same source run to complete the pair.

Candidate packages are published to:

* `ghcr.io/<repository-owner>/tf-runner-ubuntu-rock:tf-1.15.5_runner-0.16.3_u24.04_r2`
* `ghcr.io/<repository-owner>/tf-runner-juju-ubuntu-rock:tf-1.15.5_runner-0.16.3_u24.04_r2`

Today the owner is `jsimpso`; repository transfer to Canonical is deferred until
the images are proven. The workflow prints each manifest digest for downstream
pinning. Existing Docker package names and tags are never overwritten. Verify GHCR
package visibility/pull permissions before testing from a cluster.

Do not change production Flux image references until controller compatibility is
verified. Retain the old image digests for rollback, and separate the subsequent
repository transfer and production rollout from this candidate work.
