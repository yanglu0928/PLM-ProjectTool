import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch
from plm_assistant.entrypoints import production_login as prod
from plm_assistant.modules.platform.infrastructure.bootstrap_config import BootstrapSettings


class ProductionLoginPreconditionsTests(unittest.TestCase):
    def test_twenty_fixed_budget_is_fail_closed_and_nondisclosing(self):
        runtime = MagicMock()
        result = runtime.unit_of_work.return_value.__enter__.return_value.session.execute.return_value
        for maximum, superuser, reserved, accepted in (
            (100, 3, 0, True), (83, 3, 0, True),
            (82, 3, 0, False), (100, 3, 20, False),
        ):
            result.all.return_value = [
                ("max_connections", str(maximum)),
                ("superuser_reserved_connections", str(superuser)),
                ("reserved_connections", str(reserved)),
                ("server_version_num", "180006"),
            ]
            with self.subTest(maximum=maximum, reserved=reserved):
                if accepted:
                    prod._require_twenty_fixed_pool_budget(runtime)
                else:
                    with self.assertRaisesRegex(
                            prod.ProductionLoginStartupError,
                            "^production login unavailable$"):
                        prod._require_twenty_fixed_pool_budget(runtime)
        for bad_rows in (
            [("max_connections", "100")],
            [("max_connections", "not-a-number"),
             ("superuser_reserved_connections", "3"),
             ("reserved_connections", "0"),
             ("server_version_num", "180006")],
            [("max_connections", "100"),
             ("superuser_reserved_connections", "3"),
             ("reserved_connections", "0"),
             ("server_version_num", "170000")],
        ):
            result.all.return_value = bad_rows
            with self.assertRaisesRegex(
                    prod.ProductionLoginStartupError,
                    "^production login unavailable$"):
                prod._require_twenty_fixed_pool_budget(runtime)

    def test_twenty_fixed_startup_selects_pool_and_disposes_when_budget_rejected(self):
        settings = BootstrapSettings(
            data_root=Path.cwd(), trusted_origins=("http://localhost",),
            api_database_pool_profile="TWENTY_FIXED",
        )
        runtime = Mock()
        runtime.is_ready.return_value = True
        with patch.object(prod, "read_database_url", return_value="synthetic-url"), \
                patch.object(prod, "create_database_runtime", return_value=runtime) as create, \
                patch.object(prod, "_schema_current", return_value=True), \
                patch.object(prod, "_require_twenty_fixed_pool_budget",
                             side_effect=prod.ProductionLoginStartupError()) as budget:
            with self.assertRaisesRegex(
                    prod.ProductionLoginStartupError,
                    "^production login unavailable$"):
                prod.create_production_platform_write_app(settings)
        self.assertEqual(create.call_args.args, ("synthetic-url",))
        options = create.call_args.kwargs["options"]
        self.assertEqual((options.pool_size, options.max_overflow), (20, 0))
        budget.assert_called_once_with(runtime)
        runtime.dispose.assert_called_once()

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
