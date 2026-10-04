"""Parser factory startup sources must be explicit and bounded."""

import tempfile
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from plm_assistant.entrypoints.parser_worker import ParserWorkerSettings, create_parser_worker
from plm_assistant.modules.parser.infrastructure.paddle_ocr import OfflinePaddleOcr
from plm_assistant.modules.platform.infrastructure.worker_database import WorkerDatabaseRuntime


class ParserWorkerCompositionTests(unittest.TestCase):
    def test_settings_reject_unsafe_coordinates(self):
        for arguments in (
            {"worker_ref": "bad worker"},
            {"worker_ref": "parser", "lease_seconds": 3},
            {"worker_ref": "parser", "heartbeat_seconds": 21},
            {"worker_ref": "parser", "poll_seconds": float("nan")},
        ):
            with self.subTest(arguments=arguments), self.assertRaises(ValueError):
                ParserWorkerSettings(**arguments)

    def test_missing_or_stale_startup_sources_fail_closed(self):
        runtime = object.__new__(WorkerDatabaseRuntime)
        projects = SimpleNamespace(require_in_transaction=lambda *a, **kw: None)
        license_guard = SimpleNamespace(require_valid=lambda **kw: object())
        actor = SimpleNamespace(assert_current=uuid.uuid4)
        engine = object.__new__(OfflinePaddleOcr)
        engine.model_fingerprint = "a" * 64
        with tempfile.TemporaryDirectory() as root:
            args = dict(database=runtime, projects=projects,
                license_guard=license_guard, system_actor=actor,
                data_root=Path(root), ocr_engine=engine,
                settings=ParserWorkerSettings("parser-test"))
            with self.assertRaises(ValueError):
                create_parser_worker(**{**args, "ocr_engine": None})
            with self.assertRaises(ValueError):
                create_parser_worker(**{**args, "ocr_engine":
                    SimpleNamespace(model_fingerprint="invalid", recognize=lambda image: ())})
            engine.model_fingerprint = "invalid"
            with self.assertRaises(ValueError):
                create_parser_worker(**args)
            engine.model_fingerprint = "a" * 64
            with patch.object(WorkerDatabaseRuntime, "is_ready", return_value=False):
                with self.assertRaisesRegex(RuntimeError, "startup sources rejected"):
                    create_parser_worker(**args)
            with patch.object(WorkerDatabaseRuntime, "is_ready", return_value=True), \
                 patch("plm_assistant.entrypoints.parser_worker._current_schema",
                       return_value=False):
                with self.assertRaisesRegex(RuntimeError, "startup sources rejected"):
                    create_parser_worker(**args)


if __name__ == "__main__":
    unittest.main()
