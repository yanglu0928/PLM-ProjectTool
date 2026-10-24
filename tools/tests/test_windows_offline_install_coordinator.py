from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from windows_offline_install_coordinator import coordinate  # noqa: E402


class CoordinatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.paths = tuple(Path(name) for name in ("candidate.zip", "source.zip", "stage", "layout"))
        self.readiness = {"release_eligible": False, "install_authorized": False,
                          "blocker_codes": ["FORMAL_PRODUCT_PUBLIC_KEY_NOT_PACKAGED"],
                          "verified_layout_file_count": 21115}

    def test_assess_is_read_only_and_reports_blockers(self) -> None:
        with patch("windows_offline_install_coordinator.preflight", return_value=self.readiness):
            with patch("windows_offline_install_coordinator.rehearse") as placement:
                report = coordinate("assess", *self.paths)
                placement.assert_not_called()
        self.assertEqual(report["status"], "FORMAL_INSTALL_ASSESSMENT_BLOCKED")
        self.assertEqual(report["blocker_codes"], self.readiness["blocker_codes"])

    def test_install_refuses_even_if_tooling_is_present(self) -> None:
        with patch("windows_offline_install_coordinator.preflight", return_value=self.readiness):
            with patch("windows_offline_install_coordinator.rehearse") as placement:
                report = coordinate("install", *self.paths)
                placement.assert_not_called()
        self.assertEqual(report["status"], "FORMAL_INSTALL_REFUSED")
        self.assertFalse(report["formal_root_written"])

    def test_rehearsal_allows_only_independent_temp_placement_and_postcheck(self) -> None:
        placed = {"target_file_count": 21115, "mapping_sha256": "mapping",
                  "candidate_sha256": "candidate"}
        with patch("windows_offline_install_coordinator.preflight", return_value=self.readiness):
            with patch("windows_offline_install_coordinator.rehearse", return_value=placed) as placement:
                with patch("windows_offline_install_coordinator.verify_layout",
                           return_value={"file_count": 21115, "mapping_sha256": "mapping"}) as verifier:
                    report = coordinate("rehearse", *self.paths, target=Path("isolated"))
                    placement.assert_called_once()
                    verifier.assert_called_once()
        self.assertEqual(report["target_file_count"], 21115)
        self.assertFalse(report["release_eligible"])
        self.assertEqual(report["formal_blocker_codes"], self.readiness["blocker_codes"])

    def test_postcheck_mismatch_fails_closed(self) -> None:
        with patch("windows_offline_install_coordinator.preflight", return_value=self.readiness):
            with patch("windows_offline_install_coordinator.rehearse",
                       return_value={"target_file_count": 21115, "mapping_sha256": "a"}):
                with patch("windows_offline_install_coordinator.verify_layout",
                           return_value={"file_count": 21114, "mapping_sha256": "a"}):
                    with self.assertRaisesRegex(ValueError, "post-publication"):
                        coordinate("rehearse", *self.paths, target=Path("isolated"))

    def test_unverified_preflight_stops_before_placement(self) -> None:
        with patch("windows_offline_install_coordinator.preflight", side_effect=ValueError("bad")):
            with patch("windows_offline_install_coordinator.rehearse") as placement:
                with self.assertRaisesRegex(ValueError, "bad"):
                    coordinate("rehearse", *self.paths, target=Path("isolated"))
                placement.assert_not_called()

    def test_clearance_claim_cannot_turn_on_formal_install(self) -> None:
        with patch("windows_offline_install_coordinator.preflight",
                   return_value={**self.readiness, "install_authorized": True}):
            with self.assertRaisesRegex(ValueError, "cannot be inferred"):
                coordinate("install", *self.paths)


if __name__ == "__main__":
    unittest.main()
