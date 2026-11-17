"""Publishing must be idempotent and must never move release tags."""

import hashlib
import importlib.util
import json
import subprocess
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location("publish_rock", Path(__file__).parents[1] / "scripts/publish-rock.py")
publisher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(publisher)


class PublishRock(unittest.TestCase):
    def setUp(self):
        self.manifest = b'{"schemaVersion":2}'
        self.calls = []
        self.existing = {}
        self.tag = "tf-1.15.5_runner-0.16.3_u24.04_r2"
        self.image = "ghcr.io/owner/runner"

    def skopeo(self, *args):
        self.calls.append(args)
        if args[:2] == ("inspect", "--config"):
            return json.dumps({"config": {"Labels": {"org.opencontainers.image.version": "1.15.5-2"}}}).encode()
        if "copy" in args:
            return b""
        if args[-1].startswith("oci-archive:"):
            return self.manifest
        if args[-1] in self.existing:
            return self.existing[args[-1]]
        raise subprocess.CalledProcessError(1, args, stderr=b"manifest unknown")

    def publish(self):
        return publisher.publish("test.rock", self.image, "a" * 40, self.tag, "1.15.5-2", "auth", self.skopeo)

    def test_publishes_both_tags_preserving_digest(self):
        digest = self.publish()
        self.assertEqual(digest, "sha256:" + hashlib.sha256(self.manifest).hexdigest())
        copies = [call for call in self.calls if "copy" in call]
        self.assertEqual(len(copies), 2)
        self.assertEqual(copies[0][-1], f"docker://{self.image}:{self.tag}")
        self.assertEqual(copies[1][-1], f"docker://{self.image}:sha-{'a' * 40}")
        self.assertTrue(all("--preserve-digests" in call for call in copies))

    def test_existing_identical_tags_are_noop(self):
        self.existing = {f"docker://{self.image}:{tag}": self.manifest for tag in (self.tag, "sha-" + "a" * 40)}
        self.publish()
        self.assertFalse(any("copy" in call for call in self.calls))

    def test_adds_release_tag_without_rewriting_existing_sha(self):
        self.existing[f"docker://{self.image}:sha-{'a' * 40}"] = self.manifest
        self.publish()
        self.assertEqual(len([call for call in self.calls if "copy" in call]), 1)

    def test_conflict_on_either_tag_prevents_all_writes(self):
        for tag in (self.tag, "sha-" + "a" * 40):
            with self.subTest(tag=tag):
                self.existing = {f"docker://{self.image}:{tag}": b"different manifest"}
                self.calls.clear()
                with self.assertRaisesRegex(ValueError, "Refusing to overwrite"):
                    self.publish()
                self.assertFalse(any("copy" in call for call in self.calls))

    def test_inspection_errors_fail_closed(self):
        for message in (b"unauthorized", b"timeout", b"too many requests"):
            def fail(*args, message=message):
                raise subprocess.CalledProcessError(1, args, stderr=message)
            with self.subTest(message=message), self.assertRaises(subprocess.CalledProcessError):
                publisher.existing_digest("docker://example", "auth", fail)

    def test_archive_version_must_match_source(self):
        with self.assertRaisesRegex(ValueError, "Archive version differs"):
            publisher.publish("test.rock", self.image, "a" * 40, self.tag, "1.15.5-3", "auth", self.skopeo)
