from __future__ import annotations

import unittest

from plm_assistant.modules.platform.infrastructure.orm import Base
from plm_assistant.modules.plugin.infrastructure import orm as plugin_orm


class PluginExecutionSchemaTests(unittest.TestCase):
    def test_plugin_execution_root_and_owned_tables_are_registered(self):
        expected = {"plg_executions", "plg_execution_result_files",
                    "plg_execution_state_events"}
        self.assertTrue(expected.issubset(
            {table.name for table in Base.metadata.tables.values()}))

    def test_execution_foreign_keys_are_project_and_operation_scoped(self):
        execution = plugin_orm.PluginExecutionRow.__table__
        constraints = {item.name for item in execution.constraints if item.name}
        self.assertTrue({
            "fk_plg_executions__project",
            "fk_plg_executions__output_project",
            "fk_plg_executions__context_project",
            "fk_plg_executions__installation_package",
            "fk_plg_executions__manifest_operation",
            "fk_plg_executions__job",
            "uq_plg_executions__project_idempotency",
            "uq_plg_executions__job_attempt",
            "ck_plg_executions__operation",
            "ck_plg_executions__state",
            "ck_plg_executions__result_shape",
        }.issubset(constraints))
        self.assertNotIn("uq_plg_executions__job", constraints)
        self.assertIn(
            "ix_plg_executions__project_state_created",
            {index.name for index in execution.indexes})

    def test_result_files_are_project_bound_path_free_and_immutable(self):
        files = plugin_orm.PluginExecutionResultFileRow.__table__
        constraints = {item.name for item in files.constraints if item.name}
        self.assertIn("fk_plg_exec_result_files__file_project", constraints)
        self.assertIn("ck_plg_exec_result_files__relative_name", constraints)
        self.assertIn("ck_plg_exec_result_files__sha256", constraints)

    def test_state_events_are_append_only_and_sanitized(self):
        events = plugin_orm.PluginExecutionStateEventRow.__table__
        constraints = {item.name for item in events.constraints if item.name}
        self.assertIn("fk_plg_exec_state_events__execution_project", constraints)
        self.assertIn("ck_plg_exec_state_events__to_state", constraints)
        self.assertIn("ck_plg_exec_state_events__reason", constraints)

    def test_schema_has_no_executable_secrets_or_file_content(self):
        forbidden = {"api_key", "private_key", "password_plain", "database_url",
                     "stdout", "traceback", "absolute_path", "file_bytes"}
        for table in (
            plugin_orm.PluginExecutionRow.__table__,
            plugin_orm.PluginExecutionResultFileRow.__table__,
            plugin_orm.PluginExecutionStateEventRow.__table__,
        ):
            self.assertTrue(forbidden.isdisjoint(
                {column.name for column in table.columns}))


if __name__ == "__main__":
    unittest.main()
