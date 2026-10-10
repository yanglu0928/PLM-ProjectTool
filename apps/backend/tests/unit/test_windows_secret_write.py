from __future__ import annotations

import unittest
from unittest.mock import patch

from sqlalchemy import create_engine

from plm_assistant.entrypoints.windows_secret_write import (
    SECRET_MASTER_KEY_REF, ProductionSecretWriteStartupError,
    create_windows_secret_write_service,
)
from plm_assistant.modules.platform.application.secret_write import SecretWriteService
from plm_assistant.modules.platform.infrastructure.database import DatabaseRuntime


class WindowsSecretWriteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.runtime = DatabaseRuntime(create_engine("sqlite://"))
        self.addCleanup(self.runtime.dispose)

    def test_missing_or_wrong_length_key_fails_closed(self) -> None:
        for key in (None, b"short"):
            with self.subTest(key=key), patch(
                "plm_assistant.entrypoints.windows_secret_write.WindowsSecretKeyProvider"
            ) as provider:
                provider.return_value.resolve_key.return_value = key
                with self.assertRaises(ProductionSecretWriteStartupError):
                    create_windows_secret_write_service(self.runtime, license_guard=object())
                provider.return_value.resolve_key.assert_called_once_with(SECRET_MASTER_KEY_REF)

    def test_fixed_vault_ref_and_no_configuration_key(self) -> None:
        with patch("plm_assistant.entrypoints.windows_secret_write.WindowsSecretKeyProvider") as provider:
            provider.return_value.resolve_key.return_value = b"s" * 32
            service = create_windows_secret_write_service(self.runtime, license_guard=object())
        self.assertIsInstance(service, SecretWriteService)
        provider.return_value.resolve_key.assert_called_once_with("secret-master-v1")


if __name__ == "__main__":
    unittest.main()
