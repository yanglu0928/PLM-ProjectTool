from __future__ import annotations

import unittest

from plm_assistant.modules.platform.infrastructure.orm import (
    APPLICATION_SCHEMA,
    NAMING_CONVENTION,
    Base,
)
from plm_assistant.modules.platform.infrastructure import configuration_orm  # noqa: F401
from plm_assistant.modules.audit.infrastructure import audit_orm  # noqa: F401
from plm_assistant.modules.auth.infrastructure import user_orm  # noqa: F401
from plm_assistant.modules.auth.infrastructure import session_orm  # noqa: F401
from plm_assistant.modules.license.infrastructure import installation_orm  # noqa: F401
from plm_assistant.modules.license.infrastructure import validation_orm  # noqa: F401


class OrmMetadataTests(unittest.TestCase):
    def test_application_schema_is_frozen_plm_schema(self) -> None:
        self.assertEqual(APPLICATION_SCHEMA, "plm")
        self.assertEqual(Base.metadata.schema, "plm")

    def test_constraint_naming_convention_is_complete(self) -> None:
        self.assertEqual(
            set(NAMING_CONVENTION),
            {"ix", "uq", "ck", "fk", "pk"},
        )

    def test_platform_audit_auth_and_license_tables_are_registered(self) -> None:
        self.assertEqual(set(Base.metadata.tables), {"plm.plt_system_configurations", "plm.plt_configuration_versions", "plm.plt_configuration_command_receipts", "plm.aud_events", "plm.auth_users", "plm.auth_password_credentials", "plm.auth_sessions", "plm.lic_installations", "plm.lic_installation_documents", "plm.lic_validation_events", "plm.lic_validation_states"})


if __name__ == "__main__":
    unittest.main()
