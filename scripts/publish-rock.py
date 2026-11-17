"""Publish immutable release and source-SHA tags from a tested OCI archive."""

import argparse
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path


def command(*args):
    return subprocess.run(["skopeo", *args], check=True, capture_output=True).stdout


def existing_digest(reference, authfile, run=command):
    try:
        manifest = run("inspect", "--authfile", authfile, "--raw", reference)
    except subprocess.CalledProcessError as error:
        # Authentication, network and rate-limit errors must not be interpreted
        # as absence. Only an explicit registry 'not found' permits a new tag.
        detail = (error.stderr or b"").decode(errors="replace").lower()
        if "manifest unknown" in detail or "name unknown" in detail:
            return None
        raise
    return "sha256:" + hashlib.sha256(manifest).hexdigest()


def publish(archive, image, commit, tag, rock_version, authfile, run=command):
    if not re.fullmatch(r"[a-f0-9]{40}", commit):
        raise ValueError("Invalid source SHA")
    if not re.fullmatch(r"tf-\d+\.\d+\.\d+_runner-\d+\.\d+\.\d+_u\d{2}\.\d{2}_r[1-9]\d*", tag):
        raise ValueError("Invalid release tag")
    source = f"oci-archive:{archive}"
    config = json.loads(run("inspect", "--config", source))
    if config["config"]["Labels"].get("org.opencontainers.image.version") != rock_version:
        raise ValueError("Archive version differs from selected build recipe")
    manifest = run("inspect", "--raw", source)
    digest = "sha256:" + hashlib.sha256(manifest).hexdigest()
    targets = [f"docker://{image}:{name}" for name in (tag, f"sha-{commit}")]
    # Preflight both tags before writing either one. Existing SHA tags are also
    # protected: rebuilding the same commit does not imply identical contents.
    present = {target: existing_digest(target, authfile, run) for target in targets}
    for target, current in present.items():
        if current is not None and current != digest:
            raise ValueError(f"Refusing to overwrite {target}: existing {current}, candidate {digest}; bump the Rock revision")
    for target, current in present.items():
        if current is None:
            run("--insecure-policy", "copy", "--authfile", authfile, "--preserve-digests", source, target)
    return digest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts", default="artifacts")
    args = parser.parse_args()
    archives = list(Path(args.artifacts).rglob("*.rock"))
    if len(archives) != 1:
        raise ValueError("Expected exactly one tested Rock archive")
    image = f"ghcr.io/{os.environ['OWNER'].lower()}/{os.environ['ARTIFACT']}"
    digest = publish(archives[0], image, os.environ["COMMIT"], os.environ["RELEASE_TAG"],
                     os.environ["ROCK_VERSION"], os.environ["REGISTRY_AUTH_FILE"])
    with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as summary:
        summary.write(f"Image: `{image}:{os.environ['RELEASE_TAG']}@{digest}`\n\n"
                      f"Source tag: `sha-{os.environ['COMMIT']}`\n\n"
                      f"Source: https://github.com/{os.environ['REPOSITORY']}/actions/runs/{os.environ['SOURCE_RUN']}\n")
