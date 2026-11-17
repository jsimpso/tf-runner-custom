"""Fast tests for Rock recipes; container behavior is tested after packing."""

import os
import pathlib
import re
import subprocess
import tempfile
import unittest

import yaml

import entrypoint_smoke

ROOT = pathlib.Path(__file__).resolve().parents[1]


class RockContracts(unittest.TestCase):
    def test_prime_preserves_public_trust_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary)
            for relative in ("usr/bin", "etc/ssl/certs", "usr/local/share/ca-certificates",
                             "usr/local/lib/python3.14/dist-packages/certifi", "tools"):
                (root / relative).mkdir(parents=True)
            bundle = root / "etc/ssl/certs/ca-certificates.crt"
            bundle.write_text("public certificate\n")
            (root / "usr/local/share/ca-certificates/hermitcrab-mirror-ca.crt").write_text("mirror certificate\n")
            certifi = root / "usr/local/lib/python3.14/dist-packages/certifi/cacert.pem"
            certifi.write_text("PyPI certificates\n")
            record = certifi.parent.parent / "certifi-1.dist-info/RECORD"
            record.parent.mkdir()
            record.write_text("certifi/cacert.pem,old-hash,18\ncertifi-1.dist-info/RECORD,,\n")
            # Account ownership changes are tested in containers, not on the host.
            chown = root / "tools/chown"
            chown.write_text("#!/bin/sh\nexit 0\n")
            chown.chmod(0o755)
            env = {**os.environ, "CRAFT_PRIME": str(root), "PATH": str(root / "tools") + ":" + os.environ["PATH"]}
            for _ in range(2):
                subprocess.run(["bash", str(ROOT / "scripts/prime-runner.sh")], env=env, check=True)
            self.assertEqual(bundle.read_text(), "public certificate\nmirror certificate\n")
            self.assertEqual(os.readlink(certifi), "/etc/ssl/certs/ca-certificates.crt")
            self.assertRegex(record.read_text(), r"certifi/cacert.pem,sha256=[\w-]+,38")
            self.assertEqual(os.readlink(root / "usr/bin/python3"), "python3.14")
            self.assertEqual((root / "etc/ldap/ldap.conf").read_text(),
                             "TLS_CACERT /etc/ssl/certs/ca-certificates.crt\n")
            self.assertEqual((root / "etc/passwd").read_text().count("runner:x:"), 1)

    def test_pull_does_not_copy_previous_builds(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary)
            (root / "scripts").mkdir()
            (root / "scripts/start-runner.sh").write_text("build input\n")
            (root / "rocks").mkdir()
            (root / "rocks/versions.env").write_text("TF_VERSION=1.15.5\n")
            (root / "rocks/python").mkdir()
            (root / "rocks/python/common.txt").write_text("dependency lock\n")
            (root / "LICENSE").write_text("license\n")
            for project_name in ("tf-runner-ubuntu", "tf-runner-juju-ubuntu"):
                (root / project_name).mkdir()
                (root / project_name / "hermitcrab-mirror-ca.crt").write_text("test cert\n")
                project = root / "rocks" / project_name
                (project / "parts/runner/src").mkdir(parents=True)
                (project / "parts/runner/src/old-build").write_text("do not copy\n")
            for project_name in ("tf-runner-ubuntu", "tf-runner-juju-ubuntu"):
                recipe = yaml.safe_load((ROOT / "rocks" / project_name / "rockcraft.yaml").read_text())
                for part in ("runner", "python-clients"):
                    destination = root / (project_name + "-" + part + "-pulled")
                    env = {**os.environ, "CRAFT_PROJECT_DIR": str(root / "rocks" / project_name),
                           "CRAFT_PART_SRC": str(destination)}
                    subprocess.run(["bash", "-euc", recipe["parts"][part]["override-pull"]],
                                   env=env, check=True)
                    self.assertTrue((destination / "scripts/start-runner.sh").exists())
                    required = "rocks/versions.env" if part == "runner" else "rocks/python/common.txt"
                    self.assertTrue((destination / required).exists())
                    self.assertFalse((destination / "rocks" / project_name).exists())

    def test_python_locks_have_hashes_and_consistent_versions(self):
        versions = {}
        for profile in ("common", "ubuntu", "build"):
            content = (ROOT / "rocks/python" / (profile + ".txt")).read_text()
            entries = content.replace("\\\n", "").splitlines()
            pins = {}
            for entry in entries:
                if not entry or entry.startswith("#"):
                    continue
                match = re.match(r"([\w.-]+)==([^\s;]+)", entry)
                self.assertIsNotNone(match, entry)
                self.assertRegex(entry, r"--hash=sha256:[a-f0-9]{64}")
                pins[match[1].lower().replace("_", "-")] = match[2]
            self.assertTrue(pins)
            versions[profile] = pins
        for name, version in versions["common"].items():
            self.assertEqual(versions["ubuntu"][name], version, name)
        self.assertNotIn("launchpadlib", versions["common"])
        self.assertIn("setuptools", versions["build"])
        self.assertIn("launchpadlib", versions["ubuntu"])

    def test_binary_inputs_are_pinned(self):
        values = {}
        for line in (ROOT / "rocks/versions.env").read_text().splitlines():
            if line and not line.startswith("#"):
                key, value = line.split("=", 1)
                values[key] = value
        self.assertRegex(values["RUNNER_IMAGE"], r"^ghcr\.io/flux-iac/tf-runner@sha256:[a-f0-9]{64}$")
        for key in ("TF_SHA256", "JUJU_SHA256"):
            self.assertRegex(values[key], r"^[a-f0-9]{64}$")
        for project in (ROOT / "rocks").glob("*/rockcraft.yaml"):
            recipe = yaml.safe_load(project.read_text())
            self.assertTrue(recipe["version"].startswith(values["TF_VERSION"] + "-"))

    def test_wrapper_forwards_arguments_and_creates_runtime_directories(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary)
            runner = root / "tf-runner"
            runner.write_text('#!/bin/sh\nprintf "%s\\n" "$@"\n')
            runner.chmod(0o755)
            script = (ROOT / "scripts/start-runner.sh").read_text()
            script = script.replace("/usr/local/bin/tf-runner", str(runner))
            arguments = ["--grpc-port", "30001", "--tls-secret-name", "with spaces", "--grpc-max-message-size", "4"]
            home = root / "home with spaces"
            env = {**os.environ, "HOME": str(home), "TF_PLUGIN_CACHE_DIR": str(home / "cache")}
            result = subprocess.run(
                ["sh", "-c", script, "start-runner", *arguments],
                env=env, capture_output=True, text=True, check=True,
            )
            lines = result.stdout.splitlines()
            self.assertEqual(lines, arguments)
            self.assertTrue((home / "cache").is_dir())
            self.assertTrue((home / ".local/share/juju").is_dir())

    def test_smoke_reads_the_pinned_runner_version(self):
        with tempfile.TemporaryDirectory() as temporary:
            versions = pathlib.Path(temporary) / "versions.env"
            versions.write_text("# comment\nRUNNER_VERSION=0.16.3\nRUNNER_IMAGE=example@sha256:0\n")
            self.assertEqual(entrypoint_smoke.recipe_runner_version(versions), (0, 16, 3))
            versions.write_text("RUNNER_IMAGE=example@sha256:0\n")
            with self.assertRaisesRegex(ValueError, "No RUNNER_VERSION"):
                entrypoint_smoke.recipe_runner_version(versions)
        self.assertIsInstance(entrypoint_smoke.recipe_runner_version(), tuple)

    def test_smoke_expects_idle_sigterm_exit_from_v0_17(self):
        self.assertFalse(entrypoint_smoke.idle_runner_exits_on_sigterm((0, 16, 3)))
        self.assertTrue(entrypoint_smoke.idle_runner_exits_on_sigterm((0, 17, 0)))
        self.assertTrue(entrypoint_smoke.idle_runner_exits_on_sigterm((1, 0, 0)))

    def test_runtime_and_entrypoint(self):
        for name in ("tf-runner-ubuntu", "tf-runner-juju-ubuntu"):
            with self.subTest(project=name):
                project = yaml.safe_load((ROOT / "rocks" / name / "rockcraft.yaml").read_text())
                self.assertEqual(project["base"], "bare")
                self.assertEqual(project["build-base"], "ubuntu@26.04")
                self.assertEqual(project["platforms"], {"amd64": None})
                self.assertEqual(project["run-user"], "_daemon_")
                self.assertNotIn("entrypoint-command", project)
                self.assertEqual(project["entrypoint-service"], "tf-runner")
                self.assertEqual(project["environment"]["PEBBLE"], "/tmp/pebble")
                self.assertEqual(project["environment"]["PEBBLE_COPY_ONCE"], "/var/lib/pebble/default")
                self.assertEqual(project["environment"]["PEBBLE_VERBOSE"], "1")
                self.assertEqual(project["services"]["tf-runner"]["command"], "/usr/local/bin/start-runner [ ]")
                self.assertEqual(project["services"]["tf-runner"]["kill-delay"], "1h")
                packages = project["parts"]["runtime"]["stage-packages"]
                self.assertTrue(all("_" in package for package in packages))
                for required in ("base-files_chisel", "bash_bins", "dash_bins", "git_http-support",
                                 "openssh-client_config", "python3.14_standard", "libldap2_libs"):
                    self.assertIn(required, packages)
                python_part = project["parts"]["python-clients"]
                self.assertNotIn("stage-packages", python_part)
                self.assertIn("libldap2-dev", python_part["build-packages"])
                self.assertEqual(set(project["parts"]["runner"]["after"]), {"runtime", "python-clients"})

    def test_python_version_matches_the_sliced_interpreter(self):
        # The Ubuntu base decides the interpreter; scripts and locks must follow it.
        versions = set()
        for project in (ROOT / "rocks").glob("*/rockcraft.yaml"):
            packages = yaml.safe_load(project.read_text())["parts"]["runtime"]["stage-packages"]
            versions |= {re.fullmatch(r"python(3\.\d+)_standard", package)[1]
                         for package in packages if re.fullmatch(r"python3\.\d+_standard", package)}
        self.assertEqual(len(versions), 1, versions)
        (version,) = versions
        for script in ("scripts/stage-python.sh", "scripts/prime-runner.sh"):
            found = set(re.findall(r"python(3\.\d+)", (ROOT / script).read_text()))
            self.assertEqual(found, {version}, script)
        self.assertIn(f"--python-version {version} ", (ROOT / "scripts/lock-python.sh").read_text())
        for lock in ("common", "ubuntu", "build"):
            header = (ROOT / "rocks/python" / (lock + ".txt")).read_text().splitlines()[1]
            self.assertIn(f"--python-version {version} ", header, lock)

    def test_candidate_publication_is_opt_in(self):
        workflow = yaml.safe_load((ROOT / ".github/workflows/build-rocks.yaml").read_text())
        self.assertNotIn("publish", workflow["jobs"])
        self.assertEqual(workflow["jobs"]["build"]["permissions"], {"contents": "read"})
        upload = next(step for step in workflow["jobs"]["build"]["steps"] if step.get("name") == "Save tested Rock")
        self.assertEqual(upload["with"]["compression-level"], 0)
        self.assertIn("3 || 14", upload["with"]["retention-days"])
        workflow = yaml.safe_load((ROOT / ".github/workflows/publish-rocks.yaml").read_text())
        # PyYAML's YAML 1.1 parser interprets the GitHub 'on' key as True.
        triggers = workflow.get("on", workflow.get(True))
        self.assertEqual(set(triggers), {"workflow_dispatch"})
        self.assertEqual(triggers["workflow_dispatch"]["inputs"]["build_run_id"]["default"], "")
        self.assertIn("refs/heads/main", workflow["jobs"]["select"]["if"])
        self.assertNotIn("packages", workflow["jobs"]["select"]["permissions"])
        publish = workflow["jobs"]["publish"]
        self.assertEqual(publish["needs"], "select")
        checkout = next(step for step in publish["steps"] if "checkout@" in step.get("uses", ""))
        self.assertEqual(checkout["with"]["ref"], "${{ github.sha }}")
        self.assertFalse(checkout["with"]["persist-credentials"])
        download = next(step for step in publish["steps"] if "download-artifact@" in step.get("uses", ""))["with"]
        self.assertIn("artifact_id", download["artifact-ids"])
        self.assertIn("run_id", download["run-id"])

    def test_managed_build_mounts_shared_repository_inputs(self):
        workflow = yaml.safe_load((ROOT / ".github/workflows/build-rocks.yaml").read_text())
        pack = next(step for step in workflow["jobs"]["build"]["steps"] if step.get("id") == "pack")
        self.assertEqual(pack["env"]["ROCKCRAFT_EXPERIMENTAL_MONOREPO"], "1")
        self.assertEqual(pack["with"]["path"], "rocks/${{ matrix.project }}")
        for project in (ROOT / "rocks").glob("*/rockcraft.yaml"):
            recipe = yaml.safe_load(project.read_text())
            for name in ("runner", "python-clients"):
                self.assertEqual(recipe["parts"][name]["source"], "../..")


if __name__ == "__main__":
    unittest.main()
