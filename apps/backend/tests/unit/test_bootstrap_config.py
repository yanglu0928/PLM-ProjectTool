from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from plm_assistant.modules.platform.infrastructure.bootstrap_config import (
    BootstrapConfigurationError,
    BootstrapSettings,
    LogLevel,
    load_bootstrap_settings,
)


class BootstrapConfigTests(unittest.TestCase):
    def test_retrieval_policy_is_exact_nonsecret_opt_in(self):
        policy = {
            "reference": "fts.project.v1", "scope": "PROJECT",
            "rerank_policy_ref": "none.v1",
            "context_policy_ref": "project-documents.v1",
        }
        settings = BootstrapSettings(
            data_root=self.root, rag_retrieval_policies=(policy,),
        )
        self.assertEqual(settings.rag_retrieval_policies, (policy,))
        for invalid in (
            ({**policy, "query_key": "synthetic-secret"},),
            ({**policy, "scope": "GLOBAL"},),
            ({**policy, "reference": "vector.project.v1"},),
            (policy, policy),
        ):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                BootstrapSettings(
                    data_root=self.root, rag_retrieval_policies=invalid,
                )

    def test_password_capacity_default_and_environment_override(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(load_bootstrap_settings(self.yaml_file).password_kdf_slots, 4)
        self.yaml_file.write_text(f'data_root: "{self.root.as_posix()}"\npassword_kdf_slots: 8\n', encoding='utf-8')
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(load_bootstrap_settings(self.yaml_file).password_kdf_slots, 8)
        with patch.dict(os.environ, {'PLM_PASSWORD_KDF_SLOTS': '16'}, clear=True):
            self.assertEqual(load_bootstrap_settings(self.yaml_file).password_kdf_slots, 16)

    def test_password_capacity_rejects_coercion_and_out_of_bounds(self):
        from plm_assistant.modules.platform.infrastructure.bootstrap_config import BootstrapSettings
        for value in (True, False, 4.0, 0, 17, '04', '+4', ' 4', '4 ', '４', None):
            with self.subTest(value=value), patch.dict(os.environ, {}, clear=True):
                with self.assertRaises(ValueError):
                    BootstrapSettings(data_root=self.root, password_kdf_slots=value)
        for value in ('0', '17', '04', '4.0', '+4', ' 4', '４'):
            with self.subTest(value=value), patch.dict(os.environ, {'PLM_PASSWORD_KDF_SLOTS': value}, clear=True):
                with self.assertRaises(BootstrapConfigurationError) as caught:
                    load_bootstrap_settings(self.yaml_file)
                self.assertEqual(str(caught.exception), 'invalid bootstrap configuration')

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        self.yaml_file = self.root / "bootstrap.yaml"
        self.yaml_file.write_text(
            f'data_root: "{self.root.as_posix()}"\n'
            'bind_host: "127.0.0.1"\n'
            "bind_port: 8000\n",
            encoding="utf-8",
        )

    def test_loads_nonsecret_yaml_and_environment_override(self) -> None:
        with patch.dict(os.environ, {"PLM_BIND_PORT": "9001"}, clear=True):
            settings = load_bootstrap_settings(self.yaml_file)
        self.assertEqual(settings.bind_host, "127.0.0.1")
        self.assertEqual(settings.bind_port, 9001)
        self.assertEqual(settings.data_root, self.root)
        self.assertEqual(settings.log_level, LogLevel.INFO)
        self.assertEqual(settings.trusted_origins, ())
        self.assertIsNone(settings.selected_mac)

    def test_selected_mac_is_explicit_nonsecret_setting(self) -> None:
        self.yaml_file.write_text(
            f'data_root: "{self.root.as_posix()}"\n'
            'selected_mac: "02:11:22:33:44:55"\n',
            encoding="utf-8",
        )
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(load_bootstrap_settings(self.yaml_file).selected_mac,
                             "02:11:22:33:44:55")
        with patch.dict(os.environ, {"PLM_SELECTED_MAC": "02-11-22-33-44-55"}, clear=True):
            self.assertEqual(load_bootstrap_settings(self.yaml_file).selected_mac,
                             "02-11-22-33-44-55")
        self.yaml_file.write_text(
            f'data_root: "{self.root.as_posix()}"\nselected_mac: "{"x" * 40}"\n',
            encoding="utf-8",
        )
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(BootstrapConfigurationError):
                load_bootstrap_settings(self.yaml_file)

    def test_explicit_trusted_origins_and_environment_override(self) -> None:
        self.yaml_file.write_text(
            f'data_root: "{self.root.as_posix()}"\n'
            'trusted_origins: ["https://plm.example.test"]\n',
            encoding="utf-8",
        )
        with patch.dict(os.environ, {}, clear=True):
            settings = load_bootstrap_settings(self.yaml_file)
        self.assertEqual(settings.trusted_origins, ("https://plm.example.test",))
        with patch.dict(
            os.environ,
            {"PLM_TRUSTED_ORIGINS": '["https://plm-alt.example.test"]'},
            clear=True,
        ):
            overridden = load_bootstrap_settings(self.yaml_file)
        self.assertEqual(overridden.trusted_origins, ("https://plm-alt.example.test",))

    def test_invalid_trusted_origin_shape_fails_without_leaking_value(self) -> None:
        synthetic = "x" * 257
        cases = (
            f'trusted_origins: ["{synthetic}"]\n',
            'trusted_origins: "https://plm.example.test"\n',
            'trusted_origins: [""]\n',
            "trusted_origins: [" + ", ".join('"https://plm.example.test"' for _ in range(17)) + "]\n",
        )
        with patch.dict(os.environ, {}, clear=True):
            for case in cases:
                with self.subTest(case=case[:32]):
                    self.yaml_file.write_text(
                        f'data_root: "{self.root.as_posix()}"\n' + case,
                        encoding="utf-8",
                    )
                    with self.assertRaises(BootstrapConfigurationError) as captured:
                        load_bootstrap_settings(self.yaml_file)
                    self.assertNotIn(synthetic, str(captured.exception))

    def test_development_dotenv_requires_explicit_file(self) -> None:
        env_file = self.root / ".env"
        env_file.write_text("PLM_LOG_LEVEL=WARNING\n", encoding="utf-8")
        with patch.dict(os.environ, {}, clear=True):
            production = load_bootstrap_settings(self.yaml_file)
            development = load_bootstrap_settings(
                self.yaml_file, development_env_file=env_file
            )
        self.assertEqual(production.log_level, LogLevel.INFO)
        self.assertEqual(development.log_level, LogLevel.WARNING)

    def test_development_dotenv_cannot_supply_secret_field(self) -> None:
        env_file = self.root / ".env"
        synthetic = "synthetic-key-value"
        env_file.write_text(f"PLM_API_KEY={synthetic}\n", encoding="utf-8")
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(BootstrapConfigurationError) as captured:
                load_bootstrap_settings(
                    self.yaml_file, development_env_file=env_file
                )
        self.assertNotIn(synthetic, str(captured.exception))

    def test_unknown_or_sensitive_yaml_key_is_rejected_without_value(self) -> None:
        synthetic = "not-a-real-password"
        self.yaml_file.write_text(
            f'data_root: "{self.root.as_posix()}"\n'
            f'api_key: "{synthetic}"\n',
            encoding="utf-8",
        )
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(BootstrapConfigurationError) as captured:
                load_bootstrap_settings(self.yaml_file)
        self.assertNotIn(synthetic, str(captured.exception))
        self.assertNotIn(str(self.yaml_file), str(captured.exception))

    def test_unknown_prefixed_environment_is_rejected(self) -> None:
        with patch.dict(os.environ, {"PLM_API_KEY": "synthetic-value"}, clear=True):
            with self.assertRaises(BootstrapConfigurationError) as captured:
                load_bootstrap_settings(self.yaml_file)
        self.assertNotIn("synthetic-value", str(captured.exception))

    def test_duplicate_yaml_key_is_rejected(self) -> None:
        self.yaml_file.write_text(
            f'data_root: "{self.root.as_posix()}"\n'
            "bind_port: 8000\nbind_port: 9000\n",
            encoding="utf-8",
        )
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(BootstrapConfigurationError):
                load_bootstrap_settings(self.yaml_file)

    def test_executable_yaml_tag_is_rejected(self) -> None:
        self.yaml_file.write_text(
            f'data_root: "{self.root.as_posix()}"\n'
            "bind_port: !!python/object/apply:os.system ['echo unsafe']\n",
            encoding="utf-8",
        )
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(BootstrapConfigurationError):
                load_bootstrap_settings(self.yaml_file)

    def test_invalid_port_and_relative_path_fail_closed(self) -> None:
        cases = (
            "data_root: ./relative\nbind_port: 8000\n",
            f'data_root: "{self.root.as_posix()}"\nbind_port: 0\n',
        )
        with patch.dict(os.environ, {}, clear=True):
            for case in cases:
                with self.subTest(case=case):
                    self.yaml_file.write_text(case, encoding="utf-8")
                    with self.assertRaises(BootstrapConfigurationError):
                        load_bootstrap_settings(self.yaml_file)

    def test_oversized_file_is_rejected(self) -> None:
        self.yaml_file.write_text("x" * 65_537, encoding="utf-8")
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(BootstrapConfigurationError):
                load_bootstrap_settings(self.yaml_file)


if __name__ == "__main__":
    unittest.main()
