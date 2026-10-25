from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from audit_go_stdlib_source_input import audit, inspect_source  # noqa: E402


class GoStdlibSourceInputTests(unittest.TestCase):
    def test_missing_or_wrong_size_source_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "size differs"):
            inspect_source(Path("missing.src.tar.gz"))

    def test_bad_candidate_rejected_before_source(self) -> None:
        with patch("audit_go_stdlib_source_input.verify", side_effect=ValueError("bad candidate")):
            with patch("audit_go_stdlib_source_input.inspect_source") as source:
                with self.assertRaisesRegex(ValueError, "bad candidate"):
                    audit(Path("missing.zip"), Path("missing.src.tar.gz"))
                source.assert_not_called()


if __name__ == "__main__":
    unittest.main()
