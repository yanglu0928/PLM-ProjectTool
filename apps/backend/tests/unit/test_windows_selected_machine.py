from __future__ import annotations

import sys
import unittest
from unittest.mock import patch

from plm_assistant.modules.license.infrastructure.windows_selected_machine import (
    SelectedMachineUnavailable, WindowsSelectedMachine, windows_local_macs,
)


class WindowsSelectedMachineTests(unittest.TestCase):
    def test_matches_local_choice_and_refuses_config_only_claim(self) -> None:
        local = frozenset({"02:11:22:33:44:55"})
        self.assertEqual(
            WindowsSelectedMachine("02-11-22-33-44-55",
                                   enumerate_macs=lambda: local).selected_mac(),
            "02:11:22:33:44:55",
        )
        for chosen in (None, "", "02:11:22:33:44:56", "not-a-mac"):
            with self.subTest(chosen=chosen):
                with self.assertRaises(SelectedMachineUnavailable):
                    WindowsSelectedMachine(
                        chosen, enumerate_macs=lambda: local,
                    ).selected_mac()

    def test_enumeration_failure_fails_closed(self) -> None:
        def broken() -> frozenset[str]:
            raise OSError("synthetic private adapter detail")

        with self.assertRaises(SelectedMachineUnavailable) as captured:
            WindowsSelectedMachine("02:11:22:33:44:55",
                                   enumerate_macs=broken).selected_mac()
        self.assertNotIn("synthetic private adapter detail", str(captured.exception))
        with patch(
            "plm_assistant.modules.license.infrastructure.windows_selected_machine.sys.platform",
            "linux",
        ):
            with self.assertRaises(SelectedMachineUnavailable):
                windows_local_macs()

    @unittest.skipUnless(sys.platform == "win32", "Windows IP Helper only")
    def test_real_windows_adapter_choice(self) -> None:
        local = windows_local_macs()
        self.assertTrue(local)
        selected = sorted(local)[0]
        self.assertEqual(WindowsSelectedMachine(selected).selected_mac(), selected)
        absent = next(
            candidate for candidate in (
                "02:00:00:00:00:01", "02:00:00:00:00:02", "02:00:00:00:00:03",
            ) if candidate not in local
        )
        with self.assertRaises(SelectedMachineUnavailable):
            WindowsSelectedMachine(absent).selected_mac()


if __name__ == "__main__":
    unittest.main()
