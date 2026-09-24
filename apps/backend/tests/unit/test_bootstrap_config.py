from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from plm_assistant.modules.platform.infrastructure.bootstrap_config import (
    BootstrapConfigurationError,
    LogLevel,
    load_bootstrap_settings,
)


class BootstrapConfigTests(unittest.TestCase):
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
