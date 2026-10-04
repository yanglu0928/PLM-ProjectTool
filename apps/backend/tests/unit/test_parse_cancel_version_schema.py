from importlib import import_module
from unittest import TestCase

from plm_assistant.modules.jobs.infrastructure.orm import parse_cancel_versions


class ParseCancelVersionSchemaTests(TestCase):
    def test_owned_snapshot_shape_and_revision(self):
        self.assertEqual(set(parse_cancel_versions.c.keys()), {"audit_event_id", "lock_version"})
        self.assertEqual([c.name for c in parse_cancel_versions.primary_key.columns], ["audit_event_id"])
        self.assertEqual(str(parse_cancel_versions.c.lock_version.type), "BIGINT")
        self.assertFalse(parse_cancel_versions.c.lock_version.nullable)
        migration = import_module(
            "plm_assistant.migrations.versions.20260930_0050_parse_cancel_version_snapshot"
        )
        self.assertEqual(migration.down_revision, "20260927_0049")
