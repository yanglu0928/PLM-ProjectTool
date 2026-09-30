"""Windows Parser Worker CLI with fixed current-account trust sources."""

import os
import sys
from pathlib import Path
from uuid import uuid4

from plm_assistant.entrypoints.parser_worker import ParserWorkerSettings, create_parser_worker
from plm_assistant.entrypoints.parser_worker_signals import run_parser_worker_process
from plm_assistant.entrypoints.windows_license_runtime import create_windows_worker_license_services
from plm_assistant.entrypoints.windows_system_actor import create_windows_system_actor
from plm_assistant.modules.parser.infrastructure.paddle_ocr import OfflinePaddleOcr
from plm_assistant.modules.platform.infrastructure.bootstrap_config import (
    BootstrapSettings, load_bootstrap_settings,
)
from plm_assistant.modules.platform.infrastructure.windows_database_credential import read_database_url
from plm_assistant.modules.platform.infrastructure.worker_database import create_worker_database_runtime
from plm_assistant.modules.platform.infrastructure.runtime_process_identity import register_runtime_process
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository


def create_windows_parser_worker(settings: BootstrapSettings):
    if sys.platform != "win32" or type(settings) is not BootstrapSettings:
        raise RuntimeError("Windows Parser worker unavailable")
    if any(value is None for value in (
            settings.parser_ocr_detection_model_dir,
            settings.parser_ocr_recognition_model_dir,
            settings.parser_ocr_model_fingerprint)):
        raise RuntimeError("Windows Parser worker unavailable")
    database = None
    try:
        database = create_worker_database_runtime(read_database_url(),
            maintenance_admission=True)
        license_services = create_windows_worker_license_services(database, settings)
        actor = create_windows_system_actor()
        actor.assert_current()
        projects = ProjectAuthorizationService(unit_of_work=database.unit_of_work,
            repository=SqlAlchemyProjectAuthorizationRepository())
        # This is a process-local SDK safety switch, not a secret source.
        os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"
        engine = OfflinePaddleOcr(
            detection_model_dir=settings.parser_ocr_detection_model_dir,
            recognition_model_dir=settings.parser_ocr_recognition_model_dir,
            expected_model_fingerprint=settings.parser_ocr_model_fingerprint)
        loop = create_parser_worker(database=database, projects=projects,
            license_guard=license_services.guard, system_actor=actor,
            data_root=settings.data_root, ocr_engine=engine,
            settings=ParserWorkerSettings("parser-" + uuid4().hex),
            maintenance_admission=database.maintenance_admission)
        return database, loop
    except Exception:
        if database is not None:
            try:
                database.dispose()  # No heartbeat or business work yet.
            except Exception:
                pass
        raise RuntimeError("Windows Parser worker unavailable") from None


def main():
    if (sys.platform != "win32" or len(sys.argv) not in (2, 3)
            or len(sys.argv) == 3 and sys.argv[2] != "--once"):
        print("Usage: python -m plm_assistant.entrypoints.parser_worker_windows "
              "<bootstrap.yaml> [--once]", file=sys.stderr)
        return 2
    database = loop = None
    try:
        settings = load_bootstrap_settings(Path(sys.argv[1]).resolve(strict=True))
        database, loop = create_windows_parser_worker(settings)
        with register_runtime_process("PARSER_WORKER", settings.data_root):
            result = run_parser_worker_process(loop,
                max_cycles=1 if len(sys.argv) == 3 else None)
            with loop.quiescent():
                database.dispose()
            database = None
        if result.reason == "STOPPED":
            print("Parser worker stopped after draining known work.")
        elif len(sys.argv) == 3 and result.reason == "LIMIT":
            print("One bounded Parser worker cycle finished; service readiness not asserted.")
        else:
            raise RuntimeError()
        return 0
    except Exception:
        if database is not None and loop is not None:
            try:
                with loop.quiescent():
                    database.dispose()
            except Exception:
                pass  # A live task owns the runtime; never force-dispose it.
        print("Windows Parser worker unavailable; configuration, credentials "
              "or lifecycle rejected.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
