"""Explicit Windows Worker CLI: fixed account sources, no Secret argv/env fallback."""
import sys
from pathlib import Path
from uuid import uuid4
from plm_assistant.entrypoints.audit_worker import create_audit_export_worker,AuditWorkerSettings
from plm_assistant.entrypoints.audit_worker_signals import run_audit_worker_process
from plm_assistant.entrypoints.windows_license_runtime import create_windows_worker_license_services
from plm_assistant.entrypoints.windows_system_actor import create_windows_system_actor
from plm_assistant.modules.platform.infrastructure.bootstrap_config import BootstrapSettings,load_bootstrap_settings
from plm_assistant.modules.platform.infrastructure.windows_database_credential import read_database_url
from plm_assistant.modules.platform.infrastructure.worker_database import create_worker_database_runtime
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.document.infrastructure.local_storage import LocalFileStorage
from plm_assistant.modules.document.infrastructure.audit_export_storage import LocalAuditExportFileStorage


def create_windows_audit_worker(settings):
    if sys.platform!='win32' or type(settings) is not BootstrapSettings:raise RuntimeError('Windows audit worker unavailable')
    database=None
    try:
        database=create_worker_database_runtime(read_database_url())
        license_services=create_windows_worker_license_services(database,settings)
        actor=create_windows_system_actor();actor.assert_current()
        projects=ProjectAuthorizationService(unit_of_work=database.unit_of_work,repository=SqlAlchemyProjectAuthorizationRepository())
        storage=LocalAuditExportFileStorage(LocalFileStorage(settings.data_root))
        loop=create_audit_export_worker(database=database,projects=projects,license_guard=license_services.guard,system_actor=actor,storage=storage,
            settings=AuditWorkerSettings('audit-'+uuid4().hex))
        return database,loop
    except Exception:
        if database is not None:
            try:database.dispose()  # Construction starts no heartbeat or business work.
            except Exception:pass
        raise RuntimeError('Windows audit worker unavailable') from None


def main():
    if sys.platform!='win32' or len(sys.argv) not in (2,3) or (len(sys.argv)==3 and sys.argv[2]!='--once'):
        print('Usage: python -m plm_assistant.entrypoints.worker_windows <bootstrap.yaml> [--once]',file=sys.stderr);return 2
    database=loop=None
    try:
        settings=load_bootstrap_settings(Path(sys.argv[1]).resolve(strict=True))
        database,loop=create_windows_audit_worker(settings)
        result=run_audit_worker_process(loop,max_steps=1 if len(sys.argv)==3 else None)
        with loop.quiescent():database.dispose()
        database=None
        if result.reason=='STOPPED':print('Audit worker stopped after draining known work.')
        elif len(sys.argv)==3 and result.reason=='LIMIT':print('One bounded audit worker step finished; service readiness not asserted.')
        else:raise RuntimeError()
        return 0
    except Exception:
        if database is not None and loop is not None:
            try:
                with loop.quiescent():database.dispose()
            except Exception:pass  # Live heartbeat: do not dispose/kill; non-daemon thread retains ownership.
        print('Windows audit worker unavailable; configuration, credentials or lifecycle rejected.',file=sys.stderr);return 1


if __name__=='__main__':raise SystemExit(main())
