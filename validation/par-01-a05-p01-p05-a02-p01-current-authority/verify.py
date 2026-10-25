"""Actual upload/PG Parser current User/Project/License rejection at publish."""

from __future__ import annotations

import os
import uuid
from dataclasses import replace
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import SimpleNamespace

from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.application.upload_commit_source import UploadCommitAuditSources
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.audit.infrastructure.upload_commit_source import SqlAlchemyUploadCommitAuditSources
from plm_assistant.modules.auth.infrastructure.current_user_access import SqlAlchemyCurrentUserAccess
from plm_assistant.modules.document.application.parse_job_source import DocumentParseSourceReader
from plm_assistant.modules.document.infrastructure.local_storage import LocalFileStorage
from plm_assistant.modules.document.infrastructure.parse_attempt_repository import SqlAlchemyParseAttemptRepository
from plm_assistant.modules.document.infrastructure.parse_job_source import SqlAlchemyDocumentParseSources
from plm_assistant.modules.document.infrastructure.parse_publish_repository import SqlAlchemyParsePublishRepository
from plm_assistant.modules.document.infrastructure.parse_result_storage import LocalParseResultStorage
from plm_assistant.modules.jobs.infrastructure.lease_repository import SqlAlchemyJobLeaseRepository
from plm_assistant.modules.jobs.infrastructure.parse_enqueue_repository import SqlAlchemyParseJobQueueRepository
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.parser.application.authorized_source import AuthorizedParserInputSource
from plm_assistant.modules.parser.application.current_authority import ParserCurrentAuthority
from plm_assistant.modules.parser.application.prepare_input import ParserInputCommand, ParserInputError, PrepareParserInput
from plm_assistant.modules.parser.application.publish_result import ParserPublishError, PublishParserResult
from plm_assistant.modules.parser.application.start_attempt import StartFirstParseAttempt
from plm_assistant.modules.parser.application.structured_result import ParsedResult
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository


spec = spec_from_file_location("_parser_cancel_fixture",
    Path(__file__).resolve().parents[1] /
    "par-01-a05-p01-p04-p03-p02-cancel-owner" / "verify.py")
fixture = module_from_spec(spec)
spec.loader.exec_module(fixture)
fixture.fixture.PORT = int(os.environ.get("PLM_POC_PG_PORT", "55434"))


class Guard:
    enabled = True

    def require_valid(self, *, trace_id):
        if not self.enabled:
            raise RuntimeLicenseError("LICENSE_OPERATION_DENIED")
        return object()


def exercise(v):
    def extra(v, *, db, client, lease, headers, path, body, snapshot):
        upload, _, _ = v["seed"](v["content"])
        request = replace(v["cmd"], upload_id=upload, trace_id=uuid.uuid4())
        ref = v["worker"].commit(request,
            idempotency_key="synthetic-parser-current-authority")
        claim = lease.claim_next_parse(worker_ref="parser-current-authority",
                                       lease_seconds=30)
        assert claim is not None and claim.job_id == ref.parse_job_id
        command = ParserInputCommand(claim.job_id, claim.fencing_token,
                                     "parser-current-authority")
        queue = SqlAlchemyParseJobQueueRepository()
        leases = SqlAlchemyJobLeaseRepository()
        audit = AuditService(SqlAlchemyAuditRepository())
        guard = Guard()
        authority = ParserCurrentAuthority(users=SqlAlchemyCurrentUserAccess(),
            projects=ProjectAuthorizationService(
                unit_of_work=v["runtime"].unit_of_work,
                repository=SqlAlchemyProjectAuthorizationRepository()),
            license_guard=guard)
        documents = AuthorizedParserInputSource(
            source=DocumentParseSourceReader(
                repository=SqlAlchemyDocumentParseSources(),
                audit_sources=UploadCommitAuditSources(
                    repository=SqlAlchemyUploadCommitAuditSources())),
            authority=authority)
        actor = SimpleNamespace(assert_current=lambda: v["actor"])
        preparer = PrepareParserInput(unit_of_work=v["runtime"].unit_of_work,
            leases=leases, queue=queue, documents=documents,
            storage=LocalFileStorage(v["root"]), audit=audit, system_actor=actor)
        starter = StartFirstParseAttempt(unit_of_work=v["runtime"].unit_of_work,
            leases=leases, queue=queue, documents=documents,
            attempts=SqlAlchemyParseAttemptRepository())
        storage = LocalParseResultStorage(v["root"])
        publisher = PublishParserResult(unit_of_work=v["runtime"].unit_of_work,
            leases=leases, queue=queue, documents=documents, storage=storage,
            results=SqlAlchemyParsePublishRepository(), audit=audit,
            system_actor=actor)
        with preparer.prepare(command) as prepared:
            started = starter.start(command, prepared)
            parsed = ParsedResult(prepared.plan.source.document_version_id,
                prepared.plan.source.content_sha256,
                prepared.plan.parser_profile, prepared.plan.parser_version, ())
            stored = storage.write_once(scope="PROJECT", project_id=v["project"],
                result_ref_id=uuid.uuid4(), content=parsed.canonical_bytes())

            db.execute("UPDATE plm.auth_users SET state='DISABLED' WHERE user_id=%s",
                       (v["actor"],))
            before = snapshot()
            try:
                publisher.publish(command=command, prepared=prepared,
                    started=started, parsed=parsed, stored=stored)
            except ParserPublishError:
                pass
            else:
                raise AssertionError("disabled user published")
            assert snapshot() == before
            assert db.execute("SELECT parse_state FROM plm.doc_parse_records WHERE "
                "job_ref=%s", (command.job_id,)).fetchone()[0] == "RUNNING"
            db.execute("UPDATE plm.auth_users SET state='ENABLED' WHERE user_id=%s",
                       (v["actor"],))

            db.execute("UPDATE plm.prj_project_members SET state='SUSPENDED' WHERE "
                       "project_id=%s AND user_id=%s", (v["project"], v["actor"]))
            try:
                preparer.prepare(command)
            except ParserInputError:
                pass
            else:
                raise AssertionError("suspended member prepared")
            db.execute("UPDATE plm.prj_project_members SET state='ACTIVE' WHERE "
                       "project_id=%s AND user_id=%s", (v["project"], v["actor"]))

            guard.enabled = False
            try:
                publisher.publish(command=command, prepared=prepared,
                    started=started, parsed=parsed, stored=stored)
            except ParserPublishError:
                pass
            else:
                raise AssertionError("invalid License published")
            guard.enabled = True
            result = publisher.publish(command=command, prepared=prepared,
                started=started, parsed=parsed, stored=stored)
            assert result.parse_record_id == started.parse_record_id
        assert db.execute("SELECT state FROM plm.job_jobs WHERE job_id=%s",
                          (command.job_id,)).fetchone()[0] == "SUCCEEDED"
        assert db.execute("SELECT count(*) FROM plm.doc_parse_result_refs WHERE "
                          "parse_record_id=%s", (started.parse_record_id,)).fetchone()[0] == 1
        print("PAR-01-A05-P01-P05-A02-P01: current User/Project/License "
              "rejects late publish; restored authority succeeds PASS")

    fixture.exercise(v, extra=extra)


if __name__ == "__main__":
    fixture.fixture.verify(exercise=exercise)
