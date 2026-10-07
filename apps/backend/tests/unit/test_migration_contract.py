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
        self.assertEqual(scripts.get_heads(), ["20261008_0128"])
        self.assertEqual(scripts.get_revision('20261008_0128').down_revision,'20261008_0127')
        self.assertEqual(scripts.get_revision('20261008_0127').down_revision,'20261008_0126')
        self.assertEqual(scripts.get_revision('20261008_0126').down_revision,'20261008_0125')
        self.assertEqual(scripts.get_revision('20261008_0125').down_revision,'20261008_0124')
        self.assertEqual(scripts.get_revision('20261008_0124').down_revision,'20261008_0123')
        self.assertEqual(scripts.get_revision('20261008_0123').down_revision,'20261008_0122')
        self.assertEqual(scripts.get_revision('20261008_0122').down_revision,'20261007_0121')
        self.assertEqual(scripts.get_revision('20261007_0121').down_revision,'20261007_0120')
        self.assertEqual(scripts.get_revision('20261007_0120').down_revision,'20261007_0119')
        self.assertEqual(scripts.get_revision('20261007_0118').down_revision,'20261007_0117')
        self.assertEqual(scripts.get_revision('20261007_0117').down_revision,'20261007_0116')
        self.assertEqual(scripts.get_revision('20261007_0116').down_revision,'20261007_0115')
        self.assertEqual(scripts.get_revision('20261007_0115').down_revision,'20261007_0114')
        self.assertEqual(scripts.get_revision('20261007_0114').down_revision,'20261007_0113')
        self.assertEqual(scripts.get_revision('20261007_0113').down_revision,'20261007_0112')
        self.assertEqual(scripts.get_revision('20261007_0112').down_revision,'20261007_0111')
        self.assertEqual(scripts.get_revision('20261007_0111').down_revision,'20261007_0110')
        self.assertEqual(scripts.get_revision('20261007_0109').down_revision,'20261006_0108')
        self.assertEqual(scripts.get_revision('20261006_0107').down_revision,'20261006_0106')
        self.assertEqual(scripts.get_revision('20261006_0106').down_revision,'20261006_0105')
        self.assertEqual(scripts.get_revision('20261006_0105').down_revision,'20261006_0104')
        self.assertEqual(scripts.get_revision('20261006_0104').down_revision,'20261006_0103')
        self.assertEqual(scripts.get_revision('20261006_0103').down_revision,'20261005_0102')
        self.assertEqual(scripts.get_revision('20261005_0102').down_revision,'20261005_0101')
        self.assertEqual(scripts.get_revision('20261005_0100').down_revision,'20261005_0099')
        self.assertEqual(scripts.get_revision('20261005_0099').down_revision,'20261005_0098')
        self.assertEqual(scripts.get_revision('20261005_0098').down_revision,'20261005_0097')
        self.assertEqual(scripts.get_revision('20261005_0097').down_revision,'20261005_0096')
        self.assertEqual(scripts.get_revision('20261005_0096').down_revision,'20261005_0095')
        self.assertEqual(scripts.get_revision('20261005_0094').down_revision,'20261005_0093')
        self.assertEqual(scripts.get_revision('20261005_0093').down_revision,'20261005_0092')
        self.assertEqual(scripts.get_revision('20261005_0092').down_revision,'20261005_0091')
        self.assertEqual(scripts.get_revision('20261005_0091').down_revision,'20261004_0090')
        self.assertEqual(scripts.get_revision('20261004_0089').down_revision,'20261004_0088')
        self.assertEqual(scripts.get_revision('20261004_0088').down_revision,'20261004_0087')
        self.assertEqual(scripts.get_revision('20261004_0087').down_revision,'20261004_0086')
        self.assertEqual(scripts.get_revision('20261004_0086').down_revision,'20261004_0085')
        self.assertEqual(scripts.get_revision('20261004_0085').down_revision,'20261004_0084')
        self.assertEqual(scripts.get_revision('20261004_0084').down_revision,'20261004_0083')
        self.assertEqual(scripts.get_revision('20261004_0083').down_revision,'20261004_0082')
        self.assertEqual(scripts.get_revision('20261004_0082').down_revision,'20261004_0081')
        self.assertEqual(scripts.get_revision('20261004_0081').down_revision,'20261004_0080')
        self.assertEqual(scripts.get_revision('20261004_0080').down_revision,'20261004_0079')
        self.assertEqual(scripts.get_revision('20261004_0079').down_revision,'20261004_0078')
        self.assertEqual(scripts.get_revision('20261004_0078').down_revision,'20261004_0077')
        self.assertEqual(scripts.get_revision('20261004_0077').down_revision,'20261004_0076')
        self.assertEqual(scripts.get_revision('20261004_0076').down_revision,'20261003_0075')
        self.assertEqual(scripts.get_revision('20261003_0075').down_revision,'20261003_0074')
        self.assertEqual(scripts.get_revision('20261003_0074').down_revision,'20261003_0073')
        self.assertEqual(scripts.get_revision('20261003_0073').down_revision,'20261003_0072')
        self.assertEqual(scripts.get_revision('20261003_0072').down_revision,'20261003_0071')
        self.assertEqual(scripts.get_revision('20261003_0071').down_revision,'20261003_0070')
        self.assertEqual(scripts.get_revision('20261003_0070').down_revision,'20261003_0069')
        self.assertEqual(scripts.get_revision('20261003_0069').down_revision,'20261003_0068')
        self.assertEqual(scripts.get_revision('20261003_0068').down_revision,'20261002_0067')
        self.assertEqual(scripts.get_revision('20261002_0064').down_revision,'20261002_0063')
        self.assertEqual(scripts.get_revision('20261002_0063').down_revision,'20261002_0062')
        self.assertEqual(scripts.get_revision('20261002_0062').down_revision,'20261002_0061')
        self.assertEqual(scripts.get_revision('20261002_0061').down_revision,'20261002_0060')
        self.assertEqual(scripts.get_revision('20261002_0060').down_revision,'20261002_0059')
        self.assertEqual(scripts.get_revision('20261002_0059').down_revision,'20261002_0058')
        self.assertEqual(scripts.get_revision('20261002_0058').down_revision,'20261002_0057')
        self.assertEqual(scripts.get_revision('20261002_0057').down_revision,'20261002_0056')
        self.assertEqual(scripts.get_revision('20261002_0056').down_revision,'20261002_0055')
        self.assertEqual(scripts.get_revision('20261002_0055').down_revision,'20261002_0054')
        self.assertEqual(scripts.get_revision('20261002_0054').down_revision,'20261002_0053')
        self.assertEqual(scripts.get_revision('20261002_0053').down_revision,'20261001_0052')
        self.assertEqual(scripts.get_revision('20261001_0052').down_revision,'20260930_0051')
        self.assertEqual(scripts.get_revision('20260930_0051').down_revision,'20260930_0050')
        self.assertEqual(scripts.get_revision('20260930_0050').down_revision,'20260927_0049')
        self.assertEqual(scripts.get_revision('20260927_0049').down_revision,'20260927_0048')
        self.assertEqual(scripts.get_revision('20260927_0048').down_revision,'20260927_0047')
        self.assertEqual(scripts.get_revision('20260927_0047').down_revision,'20260927_0046')
        self.assertEqual(scripts.get_revision('20260927_0046').down_revision,'20260927_0045')
        self.assertEqual(scripts.get_revision('20260927_0045').down_revision,'20260927_0044')
        self.assertEqual(scripts.get_revision('20260927_0044').down_revision,'20260927_0043')
        self.assertEqual(scripts.get_revision('20260927_0043').down_revision,'20260926_0042')
        self.assertEqual(scripts.get_revision("20260926_0042").down_revision,"20260926_0041")
        self.assertEqual(scripts.get_revision("20260926_0041").down_revision,"20260926_0040")
        self.assertEqual(scripts.get_revision("20260926_0040").down_revision,"20260926_0039")
        self.assertEqual(scripts.get_revision("20260926_0039").down_revision,"20260926_0038")
        self.assertEqual(scripts.get_revision("20260926_0036").down_revision,"20260926_0035")
        self.assertEqual(scripts.get_revision("20260926_0035").down_revision, "20260926_0034")
        self.assertEqual(scripts.get_revision("20260926_0034").down_revision, "20260926_0033")
        self.assertEqual(scripts.get_revision("20260926_0033").down_revision, "20260926_0032")
        self.assertEqual(scripts.get_revision("20260926_0032").down_revision, "20260926_0031")
        self.assertEqual(scripts.get_revision("20260926_0031").down_revision, "20260926_0030")
        self.assertEqual(scripts.get_revision("20260926_0030").down_revision, "20260926_0029")
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
        self.assertEqual(scripts.get_revision("20260925_0020").down_revision, "20260925_0019")
        self.assertEqual(scripts.get_revision("20260925_0021").down_revision, "20260925_0020")
        self.assertEqual(scripts.get_revision("20260925_0022").down_revision, "20260925_0021")
        self.assertEqual(scripts.get_revision("20260925_0023").down_revision, "20260925_0022")
        self.assertEqual(scripts.get_revision("20260925_0024").down_revision, "20260925_0023")
        self.assertEqual(scripts.get_revision("20260926_0025").down_revision, "20260925_0024")
        self.assertEqual(scripts.get_revision("20260926_0026").down_revision, "20260926_0025")
        self.assertEqual(scripts.get_revision("20260926_0027").down_revision, "20260926_0026")
        self.assertEqual(scripts.get_revision("20260926_0028").down_revision, "20260926_0027")
        self.assertEqual(scripts.get_revision("20260926_0029").down_revision, "20260926_0028")

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
