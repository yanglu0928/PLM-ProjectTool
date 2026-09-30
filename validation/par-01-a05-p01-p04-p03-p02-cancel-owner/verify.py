"""Actual committed Document upload -> project Job cancel HTTP/PG proof."""

from __future__ import annotations

import hashlib
import os
import uuid
from contextlib import ExitStack
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient
from psycopg import sql

from plm_assistant.entrypoints.api import create_app
from plm_assistant.entrypoints import production_login as production
from plm_assistant.modules.platform.infrastructure.bootstrap_config import BootstrapSettings
from plm_assistant.modules.jobs.api.list_cursor import JobListCursorCodec
from plm_assistant.modules.auth.api.user_list_cursor import UserListCursorCodec
from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.application.upload_commit_source import UploadCommitAuditSources
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.audit.infrastructure.parse_cancel_sources import SqlAlchemyParseCancelAuditSources
from plm_assistant.modules.audit.infrastructure.upload_commit_source import SqlAlchemyUploadCommitAuditSources
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionService
from plm_assistant.modules.auth.infrastructure.project_write_access import SqlAlchemyProjectWriteAccess
from plm_assistant.modules.auth.infrastructure.session_repository import SqlAlchemySessionRepository
from plm_assistant.modules.document.application.parse_job_source import DocumentParseSourceReader
from plm_assistant.modules.document.application.request_parse_cancel import DocumentParseJobCancelOwner
from plm_assistant.modules.document.infrastructure.parse_job_source import SqlAlchemyDocumentParseSources
from plm_assistant.modules.jobs.api.cancel import create_project_job_cancel_router
from plm_assistant.modules.jobs.application.cancel_request import (
    JobCancelError, ProjectJobCancellation, RequestProjectJobCancel,
)
from plm_assistant.modules.jobs.application.lease import JobLeaseService
from plm_assistant.modules.jobs.application.parse_enqueue import ParseJobQueue
from plm_assistant.modules.jobs.infrastructure.lease_repository import SqlAlchemyJobLeaseRepository
from plm_assistant.modules.jobs.infrastructure.parse_cancel_repository import SqlAlchemyParseCancellationRepository
from plm_assistant.modules.jobs.infrastructure.parse_enqueue_repository import SqlAlchemyParseJobQueueRepository
from plm_assistant.modules.jobs.infrastructure.read_repository import SqlAlchemyJobReadRepository
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository


spec = spec_from_file_location(
    "_real_upload_cancel_fixture",
    Path(__file__).resolve().parents[1] / "doc-03-a04-a04-upload-commit" / "verify.py",
)
fixture = module_from_spec(spec)
spec.loader.exec_module(fixture)
fixture.PORT = int(os.environ.get("PLM_POC_PG_PORT", "55434"))
trust_spec = spec_from_file_location(
    "_parse_cancel_composition_trust",
    Path(__file__).resolve().parents[1] / "aud-02-a05-windows-platform" / "verify.py",
)
trust = module_from_spec(trust_spec)
trust_spec.loader.exec_module(trust)


class Guard:
    enabled = True

    def require_valid(self, *, trace_id):
        if not self.enabled:
            raise RuntimeLicenseError("LICENSE_OPERATION_DENIED")
        return object()


def exercise(v, *, extra=None):
    project, actor, runtime, name = v["project"], v["actor"], v["runtime"], v["name"]
    csrf = b"c" * 32
    with fixture.connect(name) as db:
        department = db.execute("INSERT INTO plm.prj_departments(project_id,department_code,"
            "department_code_normalized,name) VALUES (%s,'PC','pc','Parse cancel') "
            "RETURNING department_id", (project,)).fetchone()[0]
        db.execute("INSERT INTO plm.prj_project_members(project_id,user_id,department_id,"
                   "project_role) VALUES (%s,%s,%s,'IMPLEMENTATION_MEMBER')",
                   (project, actor, department))
        other = v["other"]
        db.execute("INSERT INTO plm.prj_project_members(project_id,user_id,department_id,"
                   "project_role) VALUES (%s,%s,%s,'IMPLEMENTATION_MEMBER')",
                   (project, other, department))
        manager = db.execute("INSERT INTO plm.auth_users(username_display,username_normalized) "
                             "VALUES ('Cancel Manager','cancel manager') RETURNING user_id").fetchone()[0]
        db.execute("INSERT INTO plm.prj_project_members(project_id,user_id,department_id,"
                   "project_role) VALUES (%s,%s,%s,'PROJECT_MANAGER')",
                   (project, manager, department))

        def session(user, marker):
            token = bytes([marker]) * 32
            credential = db.execute("INSERT INTO plm.auth_password_credentials(user_id,credential_version,"
                "password_hash,algorithm_id,parameter_set) VALUES (%s,1,'$synthetic$not-login',"
                "'TEST_ONLY','{}'::jsonb) RETURNING password_credential_id", (user,)).fetchone()[0]
            db.execute("UPDATE plm.auth_users SET state='ENABLED',credential_version=1,"
                       "active_password_credential_id=%s WHERE user_id=%s", (credential, user))
            db.execute("INSERT INTO plm.auth_sessions(session_token_digest,csrf_digest,user_id,"
                "credential_version,idle_expires_at,absolute_expires_at) VALUES "
                "(%s,%s,%s,1,statement_timestamp()+interval '15 minutes',"
                "statement_timestamp()+interval '1 hour')",
                (hashlib.sha256(token).digest(), hashlib.sha256(csrf).digest(), user))
            return token

        tokens = {"actor": session(actor, 1), "other": session(other, 2),
                  "manager": session(manager, 3)}
        guard = Guard()
        audit = AuditService(SqlAlchemyAuditRepository())
        sessions = SessionService(unit_of_work=runtime.unit_of_work,
                                  repository=SqlAlchemySessionRepository(),
                                  issue_access=object(), audit=audit)
        queue = ParseJobQueue(SqlAlchemyParseJobQueueRepository())
        cancel_repo = SqlAlchemyParseCancellationRepository()
        sources = DocumentParseSourceReader(
            repository=SqlAlchemyDocumentParseSources(),
            audit_sources=UploadCommitAuditSources(
                repository=SqlAlchemyUploadCommitAuditSources()))
        owners = {("document", "DOCUMENT_PARSE"): DocumentParseJobCancelOwner(
            unit_of_work=runtime.unit_of_work, queue=queue, sources=sources,
            project_access=SqlAlchemyProjectWriteAccess(),
            projects=ProjectAuthorizationService(
                unit_of_work=runtime.unit_of_work,
                repository=SqlAlchemyProjectAuthorizationRepository()),
            license_guard=guard, cancellations=cancel_repo,
            receipts=SqlAlchemyIdempotencyReceipts(),
            audit_sources=SqlAlchemyParseCancelAuditSources(), audit=audit)}
        dispatch = ProjectJobCancellation(
            unit_of_work=runtime.unit_of_work, repository=SqlAlchemyJobReadRepository(),
            sessions=sessions, license_guard=guard, owners=owners)
        origins = LoginOriginPolicy(["https://plm.example.test"])
        app = create_app(job_cancel_router=create_project_job_cancel_router(
            sessions=sessions, cancellations=dispatch, origins=origins))
        tracked = ("job_jobs", "job_leases", "job_attempts", "aud_events",
                   "plt_idempotency_receipts", "job_parse_cancel_versions")

        def snapshot():
            return {table: tuple(db.execute(sql.SQL("SELECT * FROM plm.{} ORDER BY 1")
                .format(sql.Identifier(table)))) for table in tracked}

        def path(job, requested_project=project):
            return f"/api/v1/projects/{requested_project}/jobs/{job}:cancel"

        def headers(marker="actor", version=0, key=None):
            return {"origin": "https://plm.example.test",
                    "cookie": "plm_session=" + tokens[marker].hex(),
                    "x-csrf-token": csrf.hex(), "idempotency-key": key or str(uuid.uuid4()),
                    "if-match": f'"v{version}"'}

        body = {"reason": "Synthetic Parser cancellation"}

        def reject(client, job, h, status, requested_project=project):
            before = snapshot()
            response = client.post(path(job, requested_project), headers=h, json=body)
            assert response.status_code == status, (response.status_code, status, response.text)
            assert snapshot() == before

        with TestClient(app, base_url="https://plm.example.test") as client:
            first_job = v["first"].parse_job_id
            first_headers = headers()
            owner = owners[("document", "DOCUMENT_PARSE")]
            original_receipts = owner._receipts

            class FailAfterReceipt:
                def reserve(self, *args, **kwargs):
                    return original_receipts.reserve(*args, **kwargs)

                def complete(self, *args, **kwargs):
                    original_receipts.complete(*args, **kwargs)
                    raise RuntimeError("synthetic post-receipt failure")

            before_failure = snapshot()
            owner._receipts = FailAfterReceipt()
            try:
                command = RequestProjectJobCancel(
                    first_job, project, tokens["actor"], csrf, uuid.uuid4(),
                    body["reason"], 0)
                try:
                    owner.cancel(command, idempotency_key=str(uuid.uuid4()))
                except JobCancelError:
                    pass
                else:
                    raise AssertionError("post-receipt failure committed")
            finally:
                owner._receipts = original_receipts
            assert snapshot() == before_failure
            reject(client, first_job, first_headers | {"if-match": '"v1"'}, 409)
            reject(client, first_job, headers("other"), 404)
            reject(client, first_job, first_headers, 404, uuid.uuid4())
            reject(client, first_job, first_headers | {"origin": "https://evil.test"}, 403)
            reject(client, first_job, first_headers | {"x-csrf-token": (b"x" * 32).hex()}, 403)
            guard.enabled = False
            try:
                reject(client, first_job, first_headers, 403)
            finally:
                guard.enabled = True
            first = client.post(path(first_job), headers=first_headers, json=body)
            assert first.status_code == 200, first.text
            data = first.json()["data"]
            assert (data["state"], data["etag"], data["changed"]) == (
                "CANCELLED", '"v2"', True)
            before = snapshot()
            replay = client.post(path(first_job), headers=first_headers, json=body)
            assert replay.status_code == 200 and replay.json()["data"] == data
            assert snapshot() == before
            reject(client, first_job, first_headers | {"if-match": '"v2"'}, 409)
            terminal = client.post(path(first_job), headers=headers(version=2), json=body)
            assert terminal.status_code == 200
            assert (terminal.json()["data"]["state"], terminal.json()["data"]["changed"],
                    terminal.headers["etag"]) == ("CANCELLED", False, '"v2"')
            db.execute("UPDATE plm.prj_project_members SET state='SUSPENDED' "
                       "WHERE project_id=%s AND user_id=%s", (project, actor))
            try:
                reject(client, first_job, first_headers, 404)
            finally:
                db.execute("UPDATE plm.prj_project_members SET state='ACTIVE' "
                           "WHERE project_id=%s AND user_id=%s", (project, actor))

            # A ProjectManager may cancel an upload created by another member.
            second_job = v["second"].parse_job_id
            manager_headers = headers("manager")
            result = client.post(path(second_job), headers=manager_headers, json=body)
            assert result.status_code == 200, result.text
            assert result.json()["data"]["state"] == "CANCELLED"

            # The third original upload remains a real source for a RUNNING cancellation.
            lease = JobLeaseService(unit_of_work=runtime.unit_of_work,
                                    repository=SqlAlchemyJobLeaseRepository())
            claim = lease.claim_next_parse(worker_ref="parser-cancel-proof", lease_seconds=30)
            assert claim.job_id == v["recovered"].parse_job_id, claim
            running_headers = headers(version=1)
            running_job = claim.job_id
            with ThreadPoolExecutor(max_workers=2) as pool:
                responses = list(pool.map(lambda _: client.post(
                    path(running_job), headers=running_headers, json=body), range(2)))
            assert all(response.status_code == 200 for response in responses), responses
            first_running = responses[0].json()["data"]
            assert responses[1].json()["data"] == first_running
            assert (first_running["state"], first_running["etag"]) == (
                "CANCEL_REQUESTED", '"v2"')
            assert db.execute("SELECT count(*) FROM plm.aud_events WHERE "
                "action='DOCUMENT_PARSE_CANCEL_REQUESTED' AND target_object_id=%s",
                (running_job,)).fetchone()[0] == 1
            with runtime.unit_of_work() as tx:
                lease_repo = SqlAlchemyJobLeaseRepository()
                lease_repo.acknowledge_parse_cancel(
                    tx, job_id=running_job, fencing_token=claim.fencing_token,
                    worker_ref="parser-cancel-proof")
                tx.commit()
            # This direct Jobs-only step proves immutable HTTP replay version;
            # full Document/Audit Worker acknowledgement was covered in P04-P02.
            before = snapshot()
            replay = client.post(path(running_job), headers=running_headers, json=body)
            assert replay.status_code == 200 and replay.json()["data"] == first_running
            assert snapshot() == before
            retry_upload, _, _ = v["seed"](v["content"])
            retry_command = replace(v["cmd"], upload_id=retry_upload, trace_id=uuid.uuid4())
            retry_job = v["worker"].commit(
                retry_command, idempotency_key="synthetic-parse-cancel-retry-wait")
            retry_claim = lease.claim_next_parse(worker_ref="parser-retry-proof", lease_seconds=30)
            assert retry_claim.job_id == retry_job.parse_job_id
            with runtime.unit_of_work() as tx:
                assert SqlAlchemyJobLeaseRepository().retry_or_fail(
                    tx, job_id=retry_claim.job_id,
                    fencing_token=retry_claim.fencing_token,
                    worker_ref="parser-retry-proof", error_code="PARSER_TEMPORARY",
                    retryable=True, delay_seconds=5) == "RETRY_WAIT"
                tx.commit()
            retry_response = client.post(path(retry_claim.job_id),
                headers=headers(version=2), json=body)
            assert retry_response.status_code == 200, retry_response.text
            assert (retry_response.json()["data"]["state"],
                    retry_response.headers["etag"]) == ("CANCELLED", '"v4"')
            if extra is not None:
                extra(v, db=db, client=client, lease=lease, headers=headers,
                      path=path, body=body, snapshot=snapshot)
            db.execute("UPDATE plm.auth_users SET state='DISABLED' WHERE user_id=%s", (actor,))
            try:
                reject(client, first_job, first_headers, 401)
            finally:
                db.execute("UPDATE plm.auth_users SET state='ENABLED' WHERE user_id=%s", (actor,))
        settings = BootstrapSettings(data_root=v["root"], trusted_origins=("http://localhost",))
        prefix = "plm_assistant.entrypoints.production_login."
        with ExitStack() as stack:
            stack.enter_context(patch(prefix + "read_database_url", return_value=v["url"]))
            stack.enter_context(patch(
                "plm_assistant.entrypoints.windows_license_runtime.create_windows_license_services",
                return_value=SimpleNamespace(guard=guard)))
            for name, codec in (
                ("create_windows_secret_list_cursor_codec", trust.SecretListCursorCodec(b"q" * 32)),
                ("create_windows_project_member_cursor_codec", trust.MemberListCursorCodec(b"m" * 32)),
                ("create_windows_project_department_cursor_codec", trust.DepartmentListCursorCodec(b"d" * 32)),
                ("create_windows_document_list_cursor_codec", trust.DocumentListCursorCodec(b"l" * 32)),
                ("create_windows_document_version_cursor_codec", trust.VersionListCursorCodec(b"v" * 32)),
                ("create_windows_document_parse_cursor_codec", trust.ParseListCursorCodec(b"p" * 32)),
                ("create_windows_user_list_cursor_codec", UserListCursorCodec(b"u" * 32)),
                ("create_windows_job_list_cursor_codec", JobListCursorCodec(b"j" * 32)),
                ("create_windows_audit_cursor_codec", trust.AuditListCursorCodec(b"a" * 32)),
            ):
                stack.enter_context(patch(prefix + name, return_value=codec))
            stack.enter_context(patch(
                "plm_assistant.entrypoints.windows_secret_write.create_windows_secret_write_service",
                return_value=object()))
            stack.enter_context(patch(prefix + "create_windows_document_upload_token_issuer",
                return_value=trust.HmacUploadTokenIssuer(
                    provider=SimpleNamespace(resolve_key=lambda ref: b"u" * 32),
                    key_ref="document-upload-token-v1")))
            production_headers = headers(version=2)
            production_headers["origin"] = "http://localhost"
            for factory, expected in ((production.create_production_platform_app, 405),
                                      (production.create_production_platform_write_app, 200)):
                with TestClient(factory(settings), base_url="http://localhost") as client:
                    response = client.post(path(first_job), headers=production_headers, json=body)
                    assert response.status_code == expected, (response.status_code, expected, response.text)
                    if expected == 200:
                        assert (response.json()["data"]["state"],
                                response.json()["data"]["changed"]) == ("CANCELLED", False)
        print("PAR-01-A05-P01-P04-P03-P02: real committed upload + current Session/"
              "Project/License HTTP, creator/PM, scope denial, immutable replay, "
              "concurrency and Windows write composition PASS")


if __name__ == "__main__":
    fixture.verify(exercise=exercise)
