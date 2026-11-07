"""Windows Plugin package verification Worker; imports metadata only, never executes plugins."""
from __future__ import annotations

import signal
import sys
import threading
import time
from pathlib import Path
from uuid import uuid4

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text

from plm_assistant.entrypoints.windows_license_runtime import create_windows_worker_license_services
from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.document.infrastructure.local_storage import LocalFileStorage
from plm_assistant.modules.jobs.application.lease import JobLeaseService
from plm_assistant.modules.jobs.infrastructure.lease_repository import SqlAlchemyJobLeaseRepository
from plm_assistant.modules.platform.infrastructure.bootstrap_config import (
    BootstrapSettings, load_bootstrap_settings,
)
from plm_assistant.modules.platform.infrastructure.migration import MIGRATION_PACKAGE
from plm_assistant.modules.platform.infrastructure.runtime_process_identity import (
    register_runtime_process,
)
from plm_assistant.modules.platform.infrastructure.windows_database_credential import read_database_url
from plm_assistant.modules.platform.infrastructure.worker_database import (
    WorkerDatabaseRuntime, create_worker_database_runtime,
)
from plm_assistant.modules.plugin.application.host_compatibility import HostPlatformsPluginCompatibility
from plm_assistant.modules.plugin.application.manifest_parser import PluginManifestParser
from plm_assistant.modules.plugin.application.package_archive_inspector import PluginPackageArchiveInspector
from plm_assistant.modules.plugin.application.package_import_worker import PluginPackageImportWorker
from plm_assistant.modules.plugin.application.package_registration import PluginPackageRegistrationService
from plm_assistant.modules.plugin.application.signature_verifier import PluginPackageSignatureVerifier
from plm_assistant.modules.plugin.infrastructure.package_import_worker_repository import (
    SqlAlchemyPluginPackageImportSource,
)
from plm_assistant.modules.plugin.infrastructure.package_registration_repository import (
    SqlAlchemyPluginPackageRegistrationRepository,
)
from plm_assistant.modules.plugin.infrastructure.packaged_signer_resolver import (
    PackagedPluginSignerResolver,
)


def _current_schema(database: WorkerDatabaseRuntime) -> bool:
    config = Config()
    config.set_main_option("script_location", str(MIGRATION_PACKAGE))
    expected = ScriptDirectory.from_config(config).get_current_head()
    if expected is None:
        return False
    with database.unit_of_work() as transaction:
        rows = transaction.session.execute(
            text("SELECT version_num FROM plm.alembic_version")
        ).scalars().all()
        return rows == [expected]


def create_windows_plugin_package_worker(settings: BootstrapSettings):
    if sys.platform != "win32" or type(settings) is not BootstrapSettings:
        raise RuntimeError("Windows Plugin package worker unavailable")
    database = None
    try:
        database = create_worker_database_runtime(
            read_database_url(), maintenance_admission=True,
        )
        if database.is_ready() is not True or not _current_schema(database):
            raise RuntimeError()
        license_services = create_windows_worker_license_services(database, settings)
        license_services.guard.require_valid(trace_id=uuid4())
        lease_repository = SqlAlchemyJobLeaseRepository()
        registration = PluginPackageRegistrationService(
            unit_of_work=database.unit_of_work,
            inspector=PluginPackageArchiveInspector(
                PluginManifestParser(),
                PluginPackageSignatureVerifier(PackagedPluginSignerResolver()),
            ),
            compatibility=HostPlatformsPluginCompatibility(),
            repository=SqlAlchemyPluginPackageRegistrationRepository(),
            audit=AuditService(SqlAlchemyAuditRepository()),
        )
        file_storage = LocalFileStorage(settings.data_root)
        worker = PluginPackageImportWorker(
            unit_of_work=database.unit_of_work,
            leases=JobLeaseService(
                unit_of_work=database.unit_of_work,
                repository=lease_repository,
            ),
            lease_repository=lease_repository,
            source=SqlAlchemyPluginPackageImportSource(),
            storage=file_storage,
            archive_store=file_storage,
            registration=registration,
            license_guard=license_services.guard,
            worker_ref="plugin-package-" + uuid4().hex,
            lease_seconds=3600,
        )
        return database, worker
    except Exception:
        if database is not None:
            try:
                database.dispose()
            except Exception:
                pass
        raise RuntimeError("Windows Plugin package worker unavailable") from None


def main() -> int:
    if (sys.platform != "win32" or len(sys.argv) not in (2, 3)
            or (len(sys.argv) == 3 and sys.argv[2] != "--once")):
        print(
            "Usage: python -m plm_assistant.entrypoints.plugin_package_worker_windows "
            "<bootstrap.yaml> [--once]",
            file=sys.stderr,
        )
        return 2
    database = worker = None
    try:
        settings = load_bootstrap_settings(Path(sys.argv[1]).resolve(strict=True))
        database, worker = create_windows_plugin_package_worker(settings)
        once = len(sys.argv) == 3
        if once:
            with register_runtime_process("PLUGIN_PACKAGE_WORKER", settings.data_root):
                result = worker.run_once()
            print("One bounded Plugin verification step finished: " + result + ".")
            return 0
        stop = threading.Event()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                signal.signal(sig, lambda *_args: stop.set())
            except (ValueError, OSError):
                pass
        with register_runtime_process("PLUGIN_PACKAGE_WORKER", settings.data_root):
            while not stop.is_set():
                state = worker.run_once()
                if state == "IDLE":
                    stop.wait(1.0)
        print("Plugin package verification worker stopped.")
        return 0
    except Exception:
        print(
            "Windows Plugin package worker unavailable; configuration, credentials, "
            "License, trust or database sources rejected.",
            file=sys.stderr,
        )
        return 1
    finally:
        if database is not None:
            try:
                database.dispose()
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
