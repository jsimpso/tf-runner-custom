"""Test promotion trust boundaries without contacting GitHub."""

import base64
import copy
import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location("select_rock_build", Path(__file__).parents[1] / "scripts/select-rock-build.py")
selector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(selector)


class SelectRockBuild(unittest.TestCase):
    def setUp(self):
        self.run = {"workflow_id": 7, "event": "push", "head_branch": "main", "status": "completed",
                    "conclusion": "success", "head_repository": {"full_name": "owner/repo"}, "head_sha": "a" * 40}
        self.artifacts = {"total_count": 2, "artifacts": [
            {"name": name, "id": index, "expired": False, "size_in_bytes": 100}
            for index, name in enumerate(selector.ARTIFACTS, 10)
        ]}
        self.calls = []
        self.versions = "TF_VERSION=1.15.5\nRUNNER_VERSION=0.16.3\n"
        self.recipe = "version: '1.15.5-2'\nbase: bare\nbuild-base: ubuntu@24.04\n"

    def api(self, endpoint):
        self.calls.append(endpoint)
        if "/contents/" in endpoint:
            self.assertTrue(endpoint.endswith("?ref=" + "a" * 40))
            text = self.versions if "/versions.env?" in endpoint else self.recipe
            return {"content": base64.b64encode(text.encode()).decode()}
        if endpoint.endswith("/workflows/build-rocks.yaml"):
            return {"id": 7}
        if "/runs?" in endpoint:
            return {"workflow_runs": [{"id": 42}]}
        if "/artifacts?" in endpoint:
            return self.artifacts
        if "/compare/" in endpoint:
            return {"status": "ahead"}
        if endpoint.endswith("/runs/42"):
            return self.run
        raise AssertionError(endpoint)

    def test_latest_successful_main_build(self):
        result = selector.select_build("owner/repo", api=self.api)
        self.assertEqual(result["run_id"], "42")
        self.assertEqual(result["sha"], "a" * 40)
        self.assertEqual([item["artifact_id"] for item in result["matrix"]["include"]], [10, 11])
        for item in result["matrix"]["include"]:
            self.assertEqual(item["release_tag"], "tf-1.15.5_runner-0.16.3_u24.04_r2")
            self.assertEqual(item["rock_version"], "1.15.5-2")
        self.assertTrue(any("branch=main&event=push&status=success" in call for call in self.calls))

    def test_explicit_run_skips_discovery(self):
        selector.select_build("owner/repo", "42", api=self.api)
        self.assertFalse(any("/runs?" in call for call in self.calls))

    def test_invalid_id(self):
        for value in ("0", "-1", "42;echo bad", "abc"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                selector.select_build("owner/repo", value, api=self.api)

    def test_rejects_untrusted_or_untested_runs(self):
        original = copy.deepcopy(self.run)
        for key, value in (("workflow_id", 8), ("event", "pull_request"), ("event", "workflow_dispatch"),
                           ("head_branch", "feature"), ("status", "in_progress"), ("conclusion", "failure"),
                           ("head_repository", {"full_name": "fork/repo"}), ("head_sha", "invalid")):
            with self.subTest(key=key, value=value):
                self.run = {**original, key: value}
                with self.assertRaises(ValueError):
                    selector.select_build("owner/repo", "42", api=self.api)

    def test_rejects_missing_expired_and_duplicate_artifacts(self):
        original = copy.deepcopy(self.artifacts)
        cases = [[], [original["artifacts"][0]], original["artifacts"] * 2,
                 [{**artifact, "expired": True} for artifact in original["artifacts"]],
                 [{**artifact, "size_in_bytes": 0} for artifact in original["artifacts"]]]
        for artifacts in cases:
            with self.subTest(artifacts=artifacts):
                self.artifacts = {"total_count": len(artifacts), "artifacts": artifacts}
                with self.assertRaises(ValueError):
                    selector.select_build("owner/repo", api=self.api)

    def test_rejects_rewritten_main_history(self):
        def api(endpoint):
            return {"status": "diverged"} if "/compare/" in endpoint else self.api(endpoint)
        with self.assertRaises(ValueError):
            selector.select_build("owner/repo", api=api)

    def test_no_successful_run(self):
        def api(endpoint):
            return {"workflow_runs": []} if "/runs?" in endpoint else self.api(endpoint)
        with self.assertRaises(ValueError):
            selector.select_build("owner/repo", api=api)

    def test_historical_verified_runner_pin(self):
        pin = next(iter(selector.LEGACY_RUNNERS))
        self.versions = f"TF_VERSION=1.15.5\nRUNNER_IMAGE={pin}\n"
        result = selector.select_build("owner/repo", api=self.api)
        self.assertIn("runner-0.16.3", result["matrix"]["include"][0]["release_tag"])

    def test_rejects_missing_ambiguous_or_inconsistent_versions(self):
        for versions, recipe in (
            ("TF_VERSION=1.15.5\nRUNNER_IMAGE=unknown\n", self.recipe),
            (self.versions.replace("0.16.3", "invalid"), self.recipe),
            (self.versions + "TF_VERSION=1.15.5\n", self.recipe),
            (self.versions, self.recipe.replace("1.15.5-2", "1.15.4-2")),
            (self.versions, self.recipe.replace("1.15.5-2", "1.15.5-0")),
            (self.versions, self.recipe.replace("ubuntu@24.04", "unknown")),
        ):
            with self.subTest(versions=versions, recipe=recipe):
                self.versions, self.recipe = versions, recipe
                with self.assertRaises(ValueError):
                    selector.select_build("owner/repo", api=self.api)
