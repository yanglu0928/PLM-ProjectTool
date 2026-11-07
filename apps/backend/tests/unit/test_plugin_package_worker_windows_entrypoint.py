"""Windows Plugin package Worker entrypoint remains importable and platform-gated."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from plm_assistant.entrypoints.plugin_package_worker_windows import (
    create_windows_plugin_package_worker,
)


class WindowsPluginPackageWorkerEntrypointTests(unittest.TestCase):
    def test_composition_root_rejects_non_windows_before_construction(self):
        with patch(
            "plm_assistant.entrypoints.plugin_package_worker_windows.sys.platform",
            "linux",
        ):
            with self.assertRaisesRegex(
                RuntimeError, "Windows Plugin package worker unavailable",
            ):
                create_windows_plugin_package_worker(object())


if __name__ == "__main__":
    unittest.main()
