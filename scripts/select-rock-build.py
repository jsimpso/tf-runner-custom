"""Resolve a trusted, tested main build and its immutable artifact IDs."""

import argparse
import json
import os
import re
import subprocess

WORKFLOW = "build-rocks.yaml"
ARTIFACTS = ("tf-runner-ubuntu-rock", "tf-runner-juju-ubuntu-rock")


def github_api(endpoint):
    result = subprocess.run(["gh", "api", endpoint], check=True, capture_output=True, text=True)
    return json.loads(result.stdout)


def select_build(repository, run_id="", api=github_api):
    prefix = f"repos/{repository}"
    if run_id and not re.fullmatch(r"[1-9][0-9]*", run_id):
        raise ValueError("Build run ID must be a positive integer")
    workflow = api(f"{prefix}/actions/workflows/{WORKFLOW}")
    if not run_id:
        runs = api(f"{prefix}/actions/workflows/{WORKFLOW}/runs?branch=main&event=push&status=success&per_page=1")
        if not runs["workflow_runs"]:
            raise ValueError("No successful push build from main found")
        run_id = str(runs["workflow_runs"][0]["id"])
    run = api(f"{prefix}/actions/runs/{run_id}")
    if (run["workflow_id"] != workflow["id"] or run["event"] != "push"
            or run["head_branch"] != "main" or run["status"] != "completed"
            or run["conclusion"] != "success"
            or run["head_repository"]["full_name"].lower() != repository.lower()):
        raise ValueError("Source must be a successful build-rocks.yaml push run from this repository's main")
    sha = run["head_sha"]
    if not re.fullmatch(r"[a-f0-9]{40}", sha):
        raise ValueError("Invalid source commit SHA")
    comparison = api(f"{prefix}/compare/{sha}...main")
    if comparison["status"] not in ("ahead", "identical"):
        raise ValueError("Source commit is not on current main history")
    artifacts = api(f"{prefix}/actions/runs/{run_id}/artifacts?per_page=100")
    if artifacts["total_count"] > 100:
        raise ValueError("Unexpected artifact count; refusing incomplete selection")
    matrix = []
    for name in ARTIFACTS:
        matches = [artifact for artifact in artifacts["artifacts"] if artifact["name"] == name]
        if len(matches) != 1 or matches[0]["expired"] or not matches[0]["size_in_bytes"]:
            raise ValueError(f"Missing, expired, empty or ambiguous artifact: {name}; select another tested run or rebuild")
        matrix.append({"artifact": name, "artifact_id": matches[0]["id"]})
    return {"run_id": run_id, "sha": sha, "matrix": {"include": matrix}}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--run-id", default="")
    args = parser.parse_args()
    selected = select_build(args.repository, args.run_id)
    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
        output.writelines(f"{key}={json.dumps(value) if isinstance(value, dict) else value}\n"
                          for key, value in selected.items())
    with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as summary:
        summary.write(f"Source build: https://github.com/{args.repository}/actions/runs/{selected['run_id']}\n\n"
                      f"Source commit: `{selected['sha']}`\n")
