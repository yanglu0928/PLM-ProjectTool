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
                "plg_installations",
                "plg_enabled_operations",
                "plg_runtime_validations",
                "plg_enabled_operation_history",
                "plg_disable_results",
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
            plugin_orm.PluginPackageImportStagingRow.__table__,
            plugin_orm.PluginInstallationRow.__table__,
            plugin_orm.PluginEnabledOperationRow.__table__,
            plugin_orm.PluginRuntimeValidationRow.__table__,
            plugin_orm.PluginEnabledOperationHistoryRow.__table__,
            plugin_orm.PluginInstallationDisableResultRow.__table__,
        ):
            self.assertTrue(forbidden.isdisjoint({column.name for column in table.columns}))

    def test_installation_persistence_constraints(self):
        installation = plugin_orm.PluginInstallationRow.__table__
        operation = plugin_orm.PluginEnabledOperationRow.__table__
        validation = plugin_orm.PluginRuntimeValidationRow.__table__
        install_constraints = {item.name for item in installation.constraints if item.name}
        self.assertIn("fk_plg_installations__package_plugin", install_constraints)
        self.assertIn("ck_plg_installations__state", install_constraints)
        self.assertIn("ck_plg_installations__enabled_state_actor", install_constraints)
        op_constraints = {item.name for item in operation.constraints if item.name}
        self.assertIn("fk_plg_enabled_operations__installation_package", op_constraints)
        self.assertIn("fk_plg_enabled_operations__manifest_operation", op_constraints)
        self.assertIn("uq_plg_enabled_operations__plugin_operation", {i.name for i in operation.indexes})
        validation_constraints = {item.name for item in validation.constraints if item.name}
        disable_result = plugin_orm.PluginInstallationDisableResultRow.__table__
        disable_constraints = {item.name for item in disable_result.constraints if item.name}
        self.assertIn("fk_plg_disable_results__installation", disable_constraints)
        self.assertIn("ck_plg_disable_results__result_version", disable_constraints)
        history = plugin_orm.PluginEnabledOperationHistoryRow.__table__
        history_constraints = {item.name for item in history.constraints if item.name}
        self.assertIn("fk_plg_enabled_operation_history__audit_event", history_constraints)
        self.assertIn("fk_plg_enabled_operation_history__manifest_operation", history_constraints)
        self.assertIn("fk_plg_runtime_validations__installation", validation_constraints)
        self.assertIn("ck_plg_runtime_validations__state", validation_constraints)

    def test_package_has_version_identity_hash_and_closed_state_constraints(self):
        table = plugin_orm.PluginPackageRow.__table__
        constraints = {item.name for item in table.constraints if item.name}
        self.assertIn("uq_plg_packages__plugin_version", constraints)
        self.assertIn("ck_plg_packages__hash", constraints)
        self.assertIn("ck_plg_packages__manifest", constraints)
        self.assertIn("ck_plg_packages__state", constraints)


if __name__ == "__main__":
    unittest.main()
