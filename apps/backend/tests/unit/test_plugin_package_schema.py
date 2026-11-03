from __future__ import annotations

import unittest

from plm_assistant.modules.platform.infrastructure.orm import Base
from plm_assistant.modules.plugin.infrastructure import orm as plugin_orm


class PluginPackageSchemaTests(unittest.TestCase):
    def test_plugin_package_roots_and_owned_tables_are_registered(self):
        self.assertEqual(
            {
                "plg_packages",
                "plg_manifest_operations",
                "plg_manifest_dependencies",
                "plg_package_verifications",
                "plg_package_import_stagings",
            },
            {table.name for table in Base.metadata.tables.values() if table.name.startswith("plg_")},
        )

    def test_plugin_package_schema_excludes_plaintext_secret_fields(self):
        forbidden = {
            "api_key",
            "private_key",
            "password_plain",
            "session_token",
            "database_url",
        }
        for table in (
            plugin_orm.PluginPackageRow.__table__,
            plugin_orm.PluginManifestOperationRow.__table__,
            plugin_orm.PluginManifestDependencyRow.__table__,
            plugin_orm.PluginPackageVerificationRow.__table__,
        ):
            self.assertTrue(forbidden.isdisjoint({column.name for column in table.columns}))

    def test_package_has_version_identity_hash_and_closed_state_constraints(self):
        table = plugin_orm.PluginPackageRow.__table__
        constraints = {item.name for item in table.constraints if item.name}
        self.assertIn("uq_plg_packages__plugin_version", constraints)
        self.assertIn("ck_plg_packages__hash", constraints)
        self.assertIn("ck_plg_packages__manifest", constraints)
        self.assertIn("ck_plg_packages__state", constraints)


if __name__ == "__main__":
    unittest.main()
