"""Verify that all state owners resolve inside this app's state directory."""
import os
import subprocess
import unittest
from unittest.mock import patch
from runtime import ROOT, SOURCE, STATE, environment


class IsolationTests(unittest.TestCase):
    def test_overrides_inherited_strata_state(self):
        with patch.dict(os.environ, {"STRATA_SETTINGS_FILE": "C:/existing/settings.json",
                                     "STRATA_PROFILE_DIR": "C:/existing/profiles"}):
            env = environment()
        for key in ("STRATA_HOME", "STRATA_SETTINGS_FILE", "STRATA_PROFILE_DIR",
                    "STRATA_COMPONENTS_DIR", "STRATA_RUNTIME_DIR", "STRATA_DESKTOP_DATA_DIR",
                    "STRATA_TUNE_DIR", "STRATA_TIMESKIP_DIR"):
            path = __import__("pathlib").Path(env[key])
            self.assertTrue(path == STATE or STATE in path.parents, key)
        self.assertEqual(env["STRATA_WORKSPACE"], str(ROOT))

    def test_control_runtime_and_components_resolve_to_isolated_paths(self):
        # Exercise upstream path resolution, not just our environment dictionary.
        code = (
            "from strata_control.runtime import runtime_dir; "
            "print(runtime_dir())"
        )
        result = subprocess.run([__import__("sys").executable, "-X", "utf8", "-c", code],
                                cwd=SOURCE, env=environment(), capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), str(STATE / "runtime"))

    def test_control_launch_logs_use_same_state_root(self):
        result = subprocess.run([__import__("sys").executable, "-X", "utf8", "-c",
            "from strata_control.paths import state_base; print(state_base())"],
            cwd=SOURCE, env=environment(), capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), str(STATE))


if __name__ == "__main__":
    unittest.main()
