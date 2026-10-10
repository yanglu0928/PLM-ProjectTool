from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from audit_caddy_special_sbom_components import special_evidence  # noqa: E402


class CaddySpecialEvidenceTests(unittest.TestCase):
    def test_candidate_identity_rejected_before_evidence_read(self) -> None:
        with patch("audit_caddy_special_sbom_components.verify", side_effect=ValueError("bad ZIP")):
            with self.assertRaisesRegex(ValueError, "bad ZIP"):
                special_evidence(Path("missing.zip"), Path("queue.csv"), Path("vendor.csv"))


if __name__ == "__main__":
    unittest.main()
