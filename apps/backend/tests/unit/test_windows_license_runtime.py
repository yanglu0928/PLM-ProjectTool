from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine

from plm_assistant.entrypoints.windows_license_runtime import (
    ProductionLicenseStartupError, WindowsLicenseServices,
    create_windows_license_services,
)
from plm_assistant.modules.platform.infrastructure.bootstrap_config import BootstrapSettings
from plm_assistant.modules.platform.infrastructure.database import DatabaseRuntime


_MODULE = "plm_assistant.entrypoints.windows_license_runtime"


class WindowsLicenseRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.runtime = DatabaseRuntime(create_engine("sqlite+pysqlite:///:memory:"))
        self.addCleanup(self.runtime.dispose)
        self.settings = BootstrapSettings(
            data_root=Path(self.directory.name), selected_mac="02:11:22:33:44:55",
        )

    def test_invalid_dependencies_or_schema_do_not_assemble(self) -> None:
        with self.assertRaises(ProductionLicenseStartupError):
            create_windows_license_services(None, self.settings)
        with patch(_MODULE + "._schema_current", return_value=False), patch(
            _MODULE + ".PackagedProductKey"
        ) as product:
            with self.assertRaises(ProductionLicenseStartupError):
                create_windows_license_services(self.runtime, self.settings)
            product.assert_not_called()

    def test_missing_product_machine_or_time_key_fails_closed(self) -> None:
        with patch(_MODULE + "._schema_current", return_value=True):
            with self.assertRaises(ProductionLicenseStartupError):
                create_windows_license_services(self.runtime, self.settings)
            with patch(_MODULE + ".PackagedProductKey", return_value=object()), patch(
                _MODULE + ".WindowsSelectedMachine"
            ) as machine:
                machine.return_value.selected_mac.side_effect = RuntimeError("missing local MAC")
                with self.assertRaises(ProductionLicenseStartupError):
                    create_windows_license_services(self.runtime, self.settings)
            with patch(_MODULE + ".PackagedProductKey", return_value=object()), patch(
                _MODULE + ".WindowsSelectedMachine"
            ) as machine, patch(
                _MODULE + ".create_windows_trusted_time_integrity",
                side_effect=RuntimeError("missing Vault key"),
            ):
                machine.return_value.selected_mac.return_value = "02:11:22:33:44:55"
                with self.assertRaises(ProductionLicenseStartupError) as captured:
                    create_windows_license_services(self.runtime, self.settings)
                self.assertNotIn("missing Vault key", str(captured.exception))

    def test_trusted_components_are_wired_without_public_route(self) -> None:
        class Product:
            def product_key_ref(self):
                return "synthetic"

            def resolve_public_key(self, _ref):
                return b"p" * 32

        class Machine:
            def selected_mac(self):
                return "02:11:22:33:44:55"

        class Integrity:
            def verify(self, _record):
                return True

            def sign(self, _record):
                return {"tag": "synthetic"}

        with patch(_MODULE + "._schema_current", return_value=True), patch(
            _MODULE + ".PackagedProductKey", return_value=Product(),
        ), patch(_MODULE + ".WindowsSelectedMachine", return_value=Machine()), patch(
            _MODULE + ".create_windows_trusted_time_integrity", return_value=Integrity(),
        ):
            services = create_windows_license_services(self.runtime, self.settings)
        self.assertIsInstance(services, WindowsLicenseServices)
        self.assertIs(services.guard._validator, services.validator)
        self.assertIs(services.guard._trusted_time, services.trusted_time)


if __name__ == "__main__":
    unittest.main()
