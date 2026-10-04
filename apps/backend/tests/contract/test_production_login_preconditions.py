import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from plm_assistant.entrypoints import production_login as prod


class ProductionLoginPreconditionsTests(unittest.TestCase):
    def test_wrong_settings_three_modes_refuse_before_credentials_or_database(self):
        for factory in (prod.create_production_login_app, prod.create_production_platform_app,
                        prod.create_production_platform_write_app):
            for value in (None, object(), {'trusted_origins': ('https://plm.example.test',)}):
                with self.subTest(factory=factory.__name__, value_type=type(value).__name__):
                    with patch.object(prod, 'read_database_url') as credentials, \
                         patch.object(prod, 'create_database_runtime') as runtime:
                        with self.assertRaisesRegex(prod.ProductionLoginStartupError, '^production login unavailable$'):
                            factory(value)
                        credentials.assert_not_called()
                        runtime.assert_not_called()

    def test_actual_empty_migration_directory_refuses_before_uow(self):
        runtime = Mock()
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / 'versions').mkdir()
            with patch.object(prod, 'MIGRATION_PACKAGE', Path(directory)):
                self.assertFalse(prod._schema_current(runtime))
        runtime.unit_of_work.assert_not_called()
