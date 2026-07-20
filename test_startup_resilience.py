import os
import subprocess
import sys
import tempfile
import textwrap
import unittest


PROJECT_DIR = os.path.dirname(__file__)


class StartupResilienceTests(unittest.TestCase):
    def test_friday_import_survives_pywhatkit_import_failure(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            package_dir = os.path.join(temp_dir, "pywhatkit")
            os.makedirs(package_dir)
            with open(os.path.join(package_dir, "__init__.py"), "w", encoding="utf-8") as f:
                f.write("raise RuntimeError('simulated pywhatkit internet check failure')\n")

            env = os.environ.copy()
            env["PYTHONPATH"] = temp_dir + os.pathsep + env.get("PYTHONPATH", "")
            script = textwrap.dedent(
                """
                import friday
                print("IMPORT_OK", friday.pywhatkit is None)
                """
            )
            result = subprocess.run(
                [sys.executable, "-c", script],
                cwd=PROJECT_DIR,
                env=env,
                text=True,
                capture_output=True,
                timeout=20,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("IMPORT_OK True", result.stdout)


if __name__ == "__main__":
    unittest.main()
