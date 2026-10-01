"""Guard tests for the disposable Jobs database runner."""

import sys
import tempfile
import unittest
from pathlib import Path

from verify import PREFIX, _safe_run_dir, verify


class RunnerGuards(unittest.TestCase):
    def test_only_own_direct_child_may_be_removed(self):
        with tempfile.TemporaryDirectory(prefix="plm-job-runner-test-") as folder:
            root = Path(folder)
            own = root / f"{PREFIX}specific"
            own.mkdir()
            foreign = root / "unrelated"
            foreign.mkdir()
            nested = own / f"{PREFIX}nested"
            nested.mkdir()
            self.assertTrue(_safe_run_dir(own, root))
            self.assertFalse(_safe_run_dir(root, root))
            self.assertFalse(_safe_run_dir(foreign, root))
            self.assertFalse(_safe_run_dir(nested, root))

    def test_missing_pg_binary_fails_before_start(self):
        with tempfile.TemporaryDirectory(prefix="plm-job-runner-test-") as folder:
            root = Path(folder)
            repo = Path(__file__).resolve().parents[2]
            with self.assertRaisesRegex(ValueError, "PG18 and Python executables required"):
                verify(repo=repo, pg_bin=root, python=Path(sys.executable), temp_root=root)
            self.assertEqual(list(root.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
