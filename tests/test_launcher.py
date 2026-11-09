import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

RUNNER = Path(__file__).resolve().parents[1] / "integrations/codex/scripts/run.py"


class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="learning brain launcher ")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.env = dict(os.environ, XDG_CONFIG_HOME=str(self.root))
        self.env.pop("LEARNING_BRAIN_CONFIG", None)
        self.registration = self.root / "learning-brain/runtime.json"
        self.registration.parent.mkdir()

    def run_launcher(self, *args):
        return subprocess.run(
            [sys.executable, str(RUNNER), *args], env=self.env, capture_output=True, text=True
        )

    def register(self):
        executable = self.root / "fake cli"
        executable.write_text(
            f"#!{sys.executable}\nimport json,sys\nprint(json.dumps(sys.argv[1:]))\n"
        )
        executable.chmod(0o700)
        config = self.root / "config file.toml"
        config.write_text("# synthetic config\n")
        self.registration.write_text(
            json.dumps({"schema_version": 1, "executable": str(executable), "config": str(config)})
        )
        return config

    def test_runtime_is_resolved_without_learning_brain_on_path(self):
        config = self.register()
        self.env["PATH"] = "/nonexistent"
        result = self.run_launcher("context", "--topic", "topic with spaces")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            json.loads(result.stdout),
            ["--config", str(config), "context", "--topic", "topic with spaces"],
        )

    def test_missing_registration_has_actionable_error(self):
        result = self.run_launcher("doctor")
        self.assertEqual(result.returncode, 2)
        self.assertIn("registration", json.loads(result.stderr))

    def test_missing_runtime_is_not_silently_replaced(self):
        self.registration.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "executable": str(self.root / "missing"),
                    "config": str(self.root / "missing.toml"),
                }
            )
        )
        result = self.run_launcher("doctor")
        self.assertEqual(result.returncode, 2)
        self.assertIn("runtime executable", json.loads(result.stderr)["error"])

    def test_explicit_config_override_is_preserved(self):
        self.register()
        override = self.root / "override.toml"
        override.write_text("# explicit synthetic config")
        self.env["LEARNING_BRAIN_CONFIG"] = str(override)
        result = self.run_launcher("doctor")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)[:2], ["--config", str(override)])
