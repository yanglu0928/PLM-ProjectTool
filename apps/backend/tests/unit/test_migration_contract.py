from __future__ import annotations

import importlib
import io
import unittest
from pathlib import Path

from alembic import command
from alembic.script import ScriptDirectory
from sqlalchemy.engine import URL

from plm_assistant.modules.platform.infrastructure.migration import (
    create_migration_config,
)


class MigrationContractTests(unittest.TestCase):
    def test_configuration_revision_follows_platform_baseline(self) -> None:
        scripts = ScriptDirectory.from_config(
            create_migration_config(
                "postgresql+psycopg://app@127.0.0.1/plm"
            )
        )
        self.assertEqual(scripts.get_heads(), ["20260925_0019"])
        revision = scripts.get_revision("20260924_0001")
        self.assertIsNone(revision.down_revision)
        self.assertEqual(scripts.get_revision("20260924_0002").down_revision, "20260924_0001")
        self.assertEqual(scripts.get_revision("20260924_0003").down_revision, "20260924_0002")
        self.assertEqual(scripts.get_revision("20260924_0004").down_revision, "20260924_0003")
        self.assertEqual(scripts.get_revision("20260924_0005").down_revision, "20260924_0004")
        self.assertEqual(scripts.get_revision("20260924_0006").down_revision, "20260924_0005")
        self.assertEqual(scripts.get_revision("20260924_0007").down_revision, "20260924_0006")
        self.assertEqual(scripts.get_revision("20260924_0008").down_revision, "20260924_0007")
        self.assertEqual(scripts.get_revision("20260924_0009").down_revision, "20260924_0008")
        self.assertEqual(scripts.get_revision("20260924_0010").down_revision, "20260924_0009")
        self.assertEqual(scripts.get_revision("20260924_0011").down_revision, "20260924_0010")
        self.assertEqual(scripts.get_revision("20260925_0012").down_revision, "20260924_0011")
        self.assertEqual(scripts.get_revision("20260925_0013").down_revision, "20260925_0012")
        self.assertEqual(scripts.get_revision("20260925_0014").down_revision, "20260925_0013")
        self.assertEqual(scripts.get_revision("20260925_0015").down_revision, "20260925_0014")
        self.assertEqual(scripts.get_revision("20260925_0016").down_revision, "20260925_0015")
        self.assertEqual(scripts.get_revision("20260925_0017").down_revision, "20260925_0016")
        self.assertEqual(scripts.get_revision("20260925_0018").down_revision, "20260925_0017")
        self.assertEqual(scripts.get_revision("20260925_0019").down_revision, "20260925_0018")

    def test_config_keeps_database_url_out_of_main_options(self) -> None:
        secret = "migration-secret-must-not-leak"
        config = create_migration_config(
            URL.create(
                "postgresql+psycopg",
                username="migration_owner",
                password=secret,
                host="127.0.0.1",
                database="plm",
            )
        )
        self.assertEqual(config.get_main_option("sqlalchemy.url"), None)
        self.assertNotIn(secret, repr(config.attributes["database_url"]))

    def test_baseline_revision_is_pgvector_only(self) -> None:
        revision = importlib.import_module(
            "plm_assistant.migrations.versions."
            "20260924_0001_platform_database_baseline"
        )
        self.assertEqual(revision.PGVECTOR_VERSION, "0.8.6")
        source = revision.__file__
        self.assertIsNotNone(source)
        content = Path(source).read_text(encoding="utf-8")
        self.assertNotIn("create_table", content)
        self.assertNotIn("schema_contract", content)

    def test_offline_sql_does_not_render_password(self) -> None:
        secret = "offline-secret-must-not-leak"
        config = create_migration_config(
            URL.create(
                "postgresql+psycopg",
                username="migration_owner",
                password=secret,
                host="127.0.0.1",
                database="plm",
            )
        )
        output = io.StringIO()
        config.output_buffer = output
        command.upgrade(config, "head", sql=True)
        self.assertNotIn(secret, output.getvalue())


if __name__ == "__main__":
    unittest.main()
