from __future__ import annotations

import unittest

from plm_assistant.modules.platform.infrastructure.orm import (
    APPLICATION_SCHEMA,
    NAMING_CONVENTION,
    Base,
)


class OrmMetadataTests(unittest.TestCase):
    def test_application_schema_is_frozen_plm_schema(self) -> None:
        self.assertEqual(APPLICATION_SCHEMA, "plm")
        self.assertEqual(Base.metadata.schema, "plm")

    def test_constraint_naming_convention_is_complete(self) -> None:
        self.assertEqual(
            set(NAMING_CONVENTION),
            {"ix", "uq", "ck", "fk", "pk"},
        )

    def test_platform_baseline_does_not_create_business_tables(self) -> None:
        self.assertEqual(len(Base.metadata.tables), 0)


if __name__ == "__main__":
    unittest.main()
