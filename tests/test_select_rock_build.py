"""Test promotion trust boundaries without contacting GitHub."""

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

    def api(self, endpoint):
        self.calls.append(endpoint)
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
