"""Real accepted export/current authority/Lease/files/result/Audit/Job publication.

License trust is synthetic. SystemActor uses an actual unique temporary Windows
Vault reference via fixed production-reference mapping; no formal material used.
"""
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor
from threading import Event, local
from datetime import datetime, timedelta, timezone
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4
import ctypes, hashlib, secrets, time
from ctypes import wintypes
from psycopg import sql
from sqlalchemy import text

from plm_assistant.modules.audit.application.worker_publish import AuditExportWorkerPublish
from plm_assistant.modules.audit.infrastructure.export_result_repository import SqlAlchemyAuditExportResults
from plm_assistant.modules.document.infrastructure.audit_export_metadata import SqlAlchemyAuditExportFileMetadata
from plm_assistant.modules.jobs.application.audit_export_complete import AuditExportJobCompletion
from plm_assistant.entrypoints.windows_system_actor import create_windows_system_actor
from plm_assistant.modules.platform.infrastructure.windows_system_actor import WORKER_SYSTEM_ACTOR_KEY_REF
from plm_assistant.modules.platform.infrastructure.windows_secret_key_provider import WindowsSecretKeyProvider
from plm_assistant.modules.platform.infrastructure.windows_secret_key_lifecycle import provision_new

load = spec_from_file_location('_pub_fixture', Path(__file__).resolve().parents[1] / 'aud-03-a06-a04-p03-a04-p02-file-render' / 'verify.py')
f = module_from_spec(load); load.loader.exec_module(f)
p, w, a = f.p, f.w, f.a
base = f.f


def main():
    name, runtime = 'publication_' + uuid4().hex[:12], None
    ref = 'publication-actor-test-' + uuid4().hex
    target = 'PLMProjectTool/SecretKey/' + ref
    vault = WindowsSecretKeyProvider()
    lib = ctypes.WinDLL('Advapi32', use_last_error=True)
    lib.CredDeleteW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD]
    lib.CredDeleteW.restype = wintypes.BOOL
    assert vault.resolve_key(ref) is None
    class SourceMapping:
        def resolve_key(self, requested):
            assert requested == WORKER_SYSTEM_ACTOR_KEY_REF
            return vault.resolve_key(ref)

    with base.schema.connect('postgres') as admin, TemporaryDirectory(prefix='PLM-真实发布-') as folder:
        admin.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
        try:
            provision_new(key_ref=ref, backup_path=Path(folder) / 'synthetic-backup.json', passphrase=secrets.token_urlsafe(48), provider=vault)
            system_actor = create_windows_system_actor(resolver=SourceMapping())
            identity = system_actor.assert_current()
            url = a.URL.create('postgresql+psycopg', username='poc_admin', host='127.0.0.1', port=55432, database=name)
            a.command.upgrade(a.create_migration_config(url), 'head'); runtime = a.create_database_runtime(url)
            with base.schema.connect(name) as db:
                tokens = [bytes([i+1])*32 for i in range(2)]
                users = [base.auth.user(db, f'Synthetic publication {i}', token, 'DEPLOYMENT_ADMIN' if i else 'NONE') for i, token in enumerate(tokens)]
                project = base.schema.insert(db, 'prj_projects', dict(project_code='PUB', project_code_normalized='pub', name='Synthetic publication', created_by=users[0]), 'project_id')
                dept = base.schema.insert(db, 'prj_departments', dict(project_id=project, department_code='D', department_code_normalized='d', name='Synthetic publication'), 'department_id')
                base.schema.insert(db, 'prj_project_members', dict(project_id=project, user_id=users[0], department_id=dept, project_role='PROJECT_MANAGER'), 'project_member_id')
                projects = a.ProjectAuthorizationService(unit_of_work=runtime.unit_of_work, repository=a.SqlAlchemyProjectAuthorizationRepository())
                guard = base.auth.Guard(); repo = a.SqlAlchemyAuditExportSubmitRepository()
                queue = a.AuditExportJobQueue(a.SqlAlchemyAuditExportJobQueueRepository())
                audit = a.AuditService(a.SqlAlchemyAuditRepository())
                submit = a.AuditExportSubmitService(unit_of_work=runtime.unit_of_work, authorization=a.AuditExportSubmitAuthorization(project_access=a.SqlAlchemyProjectWriteAccess(), deployment_access=a.SqlAlchemyLicenseImportAccess(), projects=projects, license_guard=guard), repository=repo, receipts=a.SqlAlchemyIdempotencyReceipts(), queue=queue, audit=audit)
                lease_repo = w.SqlAlchemyJobLeaseRepository()
                leases = w.JobLeaseService(unit_of_work=runtime.unit_of_work, repository=lease_repo)
                class Active:
                    def __init__(self): self._local = local()
                    def __getitem__(self, key): return getattr(self._local, 'count', 0)
                    def __setitem__(self, key, value): self._local.count = value
                active = Active()
                @contextmanager
                def uow():
                    with runtime.unit_of_work() as tx:
                        active[0] += 1
                        try: yield tx
                        finally: active[0] -= 1
                file_root = (Path(folder)/'files').resolve(); file_root.mkdir()
                actual = f.LocalAuditExportFileStorage(f.LocalFileStorage(file_root))
                class Storage:
                    on_promote = None
                    def staging_sink(self, c):
                        assert active[0] == 0
                        return actual.staging_sink(c)
                    def verify_staged(self, c):
                        assert active[0] == 0
                        return actual.verify_staged(c)
                    def promote(self, c):
                        assert active[0] == 0
                        value = actual.promote(c)
                        if self.on_promote: self.on_promote()
                        return value
                storage = Storage()
                deps = dict(unit_of_work=uow, repository=repo, authority=w.AuditExportCurrentAuthority(users=w.SqlAlchemyCurrentUserAccess(), projects=projects, license_guard=guard), queue=queue, leases=w.JobLeaseCheckpoint(repository=lease_repo), captures=w.SqlAlchemyAuditCaptureRepository(), plans=p.SqlAlchemyAuditRenderPlans(), source=f.SqlAlchemyAuditExportRenderSource(), storage=storage)
                files, results = SqlAlchemyAuditExportFileMetadata(), SqlAlchemyAuditExportResults()
                completion = AuditExportJobCompletion(queue=queue, leases=lease_repo)
                worker = AuditExportWorkerPublish(files=files, results=results, completion=completion, audit=audit, system_actor=system_actor, **deps)
                def prepare(scope='PROJECT', count=3, seconds=60):
                    now, source_trace = datetime.now(timezone.utc), uuid4()
                    index = 0 if scope == 'PROJECT' else 1
                    spec = a.AuditExportSpec(scope, project if index == 0 else None, 'PROJECT_GOVERNANCE' if index == 0 else 'SECURITY_REVIEW', now-timedelta(hours=1), now+timedelta(hours=1), action='SYNTHETIC_PUBLICATION', trace_id=source_trace)
                    accepted = submit.submit_idempotent(a.AuditExportSubmitAuthorizationRequest(tokens[index], base.auth.CSRF, uuid4(), spec), idempotency_key=str(uuid4()))
                    with runtime.unit_of_work() as tx:
                        for _ in range(count):
                            audit.append(tx, w.AuditEventDraft(trace_id=source_trace, event_scope=scope, target_project_id=spec.project_id, actor_type='USER', actor_id=users[index], original_actor_id=None, actor_hint_digest=None, action='SYNTHETIC_PUBLICATION', outcome='SUCCESS'))
                        tx.commit()
                    claim = leases.claim_next(worker_ref='publisher-real', lease_seconds=seconds)
                    assert claim.job_id == accepted.job_id
                    c = w.AuditExportCaptureCommand(accepted.intent.export_id, accepted.job_id, claim.fencing_token, 'publisher-real')
                    worker.capture(c)
                    return accepted, c, worker.render(c)
                def row(c):
                    return db.execute('SELECT state FROM plm.job_jobs WHERE job_id=%s', (c.job_id,)).fetchone()[0]
                def reject(c, staged, code):
                    try: worker.publish(c, staged)
                    except w.AuditExportWorkerError as exc: assert exc.code == code, (exc.code, code)
                    else: raise AssertionError('invalid publication succeeded')
                    assert not db.execute('SELECT 1 FROM plm.aud_export_results WHERE export_id=%s', (c.export_id,)).fetchone()
                    assert not db.execute("SELECT 1 FROM plm.aud_events WHERE action='AUDIT_EXPORT_PUBLISHED' AND target_object_id=%s", (c.job_id,)).fetchone()
                    assert row(c) != 'SUCCEEDED' and active[0] == 0
                    metadata = db.execute('SELECT file_state,lock_version FROM plm.doc_file_objects WHERE file_object_id=%s', (staged.context.plan.file_id,)).fetchone()
                    assert metadata in (None, ('STAGED', 0))
                for scope in ('PROJECT', 'DEPLOYMENT'):
                    for count in (0, 260):
                        accepted, c, staged = prepare(scope, count)
                        result = worker.publish(c, staged)
                        assert result.file_sha256 == staged.content.sha256 and result.manifest_bytes == staged.rendered.manifest_bytes
                        assert actual.inspect(staged.content) == 'FINAL_VERIFIED' and row(c) == 'SUCCEEDED'
                        path = file_root / f._locators(staged.content.coordinate)[1]
                        data = path.read_bytes()
                        assert len(data.splitlines()) == count and hashlib.sha256(data).digest() == result.file_sha256
                        publication = db.execute("SELECT actor_type,actor_id,original_actor_id,trace_id,reason_code FROM plm.aud_events WHERE audit_event_id=%s", (result.publish_audit_event_id,)).fetchone()
                        assert publication == ('SYSTEM', identity, accepted.intent.actor_id, accepted.intent.trace_id, accepted.intent.spec.purpose)
                        assert db.execute('SELECT file_state,lock_version FROM plm.doc_file_objects WHERE file_object_id=%s', (result.file_id,)).fetchone() == ('AVAILABLE', 1)
                        with runtime.unit_of_work() as tx: assert results.get(tx, export_id=c.export_id) == result
                # Physical promotion callbacks mutate real current facts OUTSIDE the Owner UOW.
                accepted, c, staged = prepare()
                storage.on_promote = lambda: db.execute("UPDATE plm.auth_users SET state='DISABLED',lock_version=lock_version+1 WHERE user_id=%s", (users[0],))
                reject(c, staged, 'AUTH_ACCESS_DENIED')
                db.execute("UPDATE plm.auth_users SET state='ENABLED',lock_version=lock_version+1 WHERE user_id=%s", (users[0],)); storage.on_promote = None
                accepted, c, staged = prepare()
                canceller = w.AuditExportCancellation(repository=w.SqlAlchemyAuditExportCancellationRepository())
                def cancel():
                    assert active[0] == 0
                    with runtime.unit_of_work() as tx:
                        canceller.request_cancel(tx, target=w.AuditExportCancellationTarget(submit._queue_request(accepted.intent), w.AuditExportJobRef(accepted.job_id, accepted.event_id)), requested_by=users[0], reason='Synthetic publication cancellation'); tx.commit()
                storage.on_promote = cancel; reject(c, staged, 'STALE_LEASE'); assert row(c) == 'CANCEL_REQUESTED'; storage.on_promote = None
                accepted, c, staged = prepare(seconds=2)
                storage.on_promote = lambda: time.sleep(2.05)
                reject(c, staged, 'STALE_LEASE'); storage.on_promote = None
                with runtime.unit_of_work() as tx:
                    target_ref = w.AuditExportCancellationTarget(submit._queue_request(accepted.intent), w.AuditExportJobRef(accepted.job_id, accepted.event_id))
                    canceller.request_cancel(tx, target=target_ref, requested_by=users[0], reason='Synthetic expired fixture retirement')
                    canceller.recover_expired_cancel(tx, target=target_ref); tx.commit()
                # After-write failures at every owned database publication boundary.
                for attribute, operation in (('_files', 'mark_available'), ('_audit', 'append'), ('_results', 'record'), ('_completion', 'complete_current')):
                    accepted, c, staged = prepare()
                    original = getattr(worker, attribute)
                    class FailAfter:
                        def __getattr__(self, method):
                            function = getattr(original, method)
                            if method != operation: return function
                            def fail(*args, **kwargs):
                                function(*args, **kwargs)
                                raise RuntimeError('synthetic postwrite failure')
                            return fail
                    setattr(worker, attribute, FailAfter())
                    reject(c, staged, 'AUDIT_UNAVAILABLE')
                    setattr(worker, attribute, original)
                    assert row(c) == 'RUNNING' and actual.inspect(staged.content) == 'FINAL_VERIFIED'
                    assert not db.execute("SELECT 1 FROM plm.doc_file_state_events WHERE file_object_id=%s AND to_state='AVAILABLE'", (staged.context.plan.file_id,)).fetchone()
                accepted, c, staged = prepare()
                storage.on_promote = lambda: setattr(guard, 'enabled', False)
                reject(c, staged, 'LICENSE_OPERATION_DENIED'); guard.enabled = True; storage.on_promote = None
                # Actual lock competition, not timing-only invocation order.
                def waiting(pid):
                    until = time.monotonic() + 8
                    while time.monotonic() < until:
                        if pid and db.execute("SELECT wait_event_type FROM pg_stat_activity WHERE pid=%s", (pid[0],)).fetchone() == ('Lock',): return
                        time.sleep(.03)
                    raise AssertionError('expected actual database lock wait')
                accepted, c, staged = prepare()
                cancel_target = w.AuditExportCancellationTarget(submit._queue_request(accepted.intent), w.AuditExportJobRef(accepted.job_id, accepted.event_id))
                ready, release, pub_pid = Event(), Event(), []
                def cancel_first():
                    with runtime.unit_of_work() as tx:
                        value = canceller.request_cancel(tx, target=cancel_target, requested_by=users[0], reason='Synthetic cancel-first lock competition')
                        ready.set(); assert release.wait(8); tx.commit(); return value
                original_authority = worker._authority
                class ObserveAuthority:
                    def assert_current(self, tx, **kwargs):
                        if not pub_pid: pub_pid.append(tx.session.execute(text('SELECT pg_backend_pid()')).scalar_one())
                        return original_authority.assert_current(tx, **kwargs)
                worker._authority = ObserveAuthority()
                with ThreadPoolExecutor(max_workers=2) as pool:
                    first = pool.submit(cancel_first); assert ready.wait(8)
                    second = pool.submit(worker.publish, c, staged)
                    try: waiting(pub_pid)
                    finally: release.set()
                    assert first.result().state == 'CANCEL_REQUESTED'
                    try: second.result()
                    except w.AuditExportWorkerError as exc: assert exc.code == 'STALE_LEASE'
                    else: raise AssertionError('cancel-first publication committed')
                worker._authority = original_authority
                assert actual.inspect(staged.content) == 'STAGE_ONLY'
                assert not db.execute('SELECT 1 FROM plm.aud_export_results WHERE export_id=%s', (c.export_id,)).fetchone()
                accepted, c, staged = prepare()
                cancel_target = w.AuditExportCancellationTarget(submit._queue_request(accepted.intent), w.AuditExportJobRef(accepted.job_id, accepted.event_id))
                ready, release, cancel_pid = Event(), Event(), []
                class HoldCompletion:
                    def complete_current(self, *args, **kwargs):
                        value = completion.complete_current(*args, **kwargs)
                        ready.set(); assert release.wait(8); return value
                worker._completion = HoldCompletion()
                def cancel_after_completion():
                    with runtime.unit_of_work() as tx:
                        cancel_pid.append(tx.session.execute(text('SELECT pg_backend_pid()')).scalar_one())
                        value = canceller.request_cancel(tx, target=cancel_target, requested_by=users[0], reason='Synthetic publish-first lock competition')
                        tx.commit(); return value
                with ThreadPoolExecutor(max_workers=2) as pool:
                    first = pool.submit(worker.publish, c, staged); assert ready.wait(8)
                    second = pool.submit(cancel_after_completion)
                    try: waiting(cancel_pid)
                    finally: release.set()
                    published = first.result(); cancelled = second.result()
                    assert cancelled.state == 'SUCCEEDED' and cancelled.changed is False
                    assert published.export_id == c.export_id and row(c) == 'SUCCEEDED'
                worker._completion = completion
                accepted, c, staged = prepare()
                def remove_identity(): assert lib.CredDeleteW(target, 1, 0)
                storage.on_promote = remove_identity
                reject(c, staged, 'SYSTEM_ACTOR_UNAVAILABLE')
            print('P03-A04-P03 PASS: real accepted dualScope empty/260-row file publication with current User/PM/Admin/Lease, actual temporary Vault SystemActor, true File AVAILABLE+immutable Result+publication Audit+Job SUCCEEDED; file hash/promotion outside UOW; revoke/cancel/expiry/License/identity loss and postwrite File/Audit/result/completion failures never commit success; real cancel-first/publish-first lock waits, no undo of committed success. License synthetic; recovery/replay/HTTP/heartbeat/production account/Server2025/Debian/release remain unverified.')
        finally:
            lib.CredDeleteW(target, 1, 0)
            if runtime: runtime.dispose()
            admin.execute('SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()', (name,))
            admin.execute(sql.SQL('DROP DATABASE {}').format(sql.Identifier(name)))


if __name__ == '__main__': main()
