"""Real PostgreSQL/HTTP Parser expired cancellation and rollback proof."""

from __future__ import annotations

import os
import time
import uuid
from dataclasses import replace
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import SimpleNamespace

from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.application.upload_commit_source import UploadCommitAuditSources
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.audit.infrastructure.parse_cancel_sources import SqlAlchemyParseCancelAuditSources
from plm_assistant.modules.audit.infrastructure.upload_commit_source import SqlAlchemyUploadCommitAuditSources
from plm_assistant.modules.document.application.parse_job_source import DocumentParseSourceReader
from plm_assistant.modules.document.application.parse_attempt import DocumentParseAttemptRequest
from plm_assistant.modules.document.infrastructure.parse_cancel_repository import SqlAlchemyParseCancelRepository
from plm_assistant.modules.document.infrastructure.parse_attempt_repository import SqlAlchemyParseAttemptRepository
from plm_assistant.modules.document.infrastructure.parse_job_source import SqlAlchemyDocumentParseSources
from plm_assistant.modules.jobs.infrastructure.lease_repository import SqlAlchemyJobLeaseRepository
from plm_assistant.modules.jobs.infrastructure.parse_enqueue_repository import SqlAlchemyParseJobQueueRepository
from plm_assistant.modules.parser.application.cancel_attempt import ParserCancellationError
from plm_assistant.modules.parser.application.prepare_input import ParserInputCommand
from plm_assistant.modules.parser.application.recover_expired_cancel import RecoverExpiredParserCancel


spec = spec_from_file_location("_parser_cancel_owner_fixture",
    Path(__file__).resolve().parents[1] /
    "par-01-a05-p01-p04-p03-p02-cancel-owner" / "verify.py")
owner = module_from_spec(spec)
spec.loader.exec_module(owner)
owner.fixture.PORT = int(os.environ.get("PLM_POC_PG_PORT", "55434"))


def exercise(v, *, after=None):
    def extra(v, *, db, client, lease, headers, path, body, snapshot):
        leases = SqlAlchemyJobLeaseRepository()
        audit = AuditService(SqlAlchemyAuditRepository())
        system = SimpleNamespace(assert_current=lambda: v["actor"])
        sources = DocumentParseSourceReader(
            repository=SqlAlchemyDocumentParseSources(),
            audit_sources=UploadCommitAuditSources(
                repository=SqlAlchemyUploadCommitAuditSources()))
        repo = SqlAlchemyParseCancelAuditSources()
        service = RecoverExpiredParserCancel(unit_of_work=v["runtime"].unit_of_work,
            leases=leases, queue=SqlAlchemyParseJobQueueRepository(),
            sources=sources, cancellations=repo,
            documents=SqlAlchemyParseCancelRepository(), audit=audit,
            system_actor=system)

        def create(marker, *, with_record=False):
            upload, _, _ = v["seed"](v["content"])
            request = replace(v["cmd"], upload_id=upload, trace_id=uuid.uuid4())
            ref = v["worker"].commit(request,
                idempotency_key="synthetic-parser-expired-" + marker)
            claim = lease.claim_next_parse(worker_ref="expired-" + marker,
                                           lease_seconds=6)
            assert claim is not None and claim.job_id == ref.parse_job_id
            if with_record:
                version = uuid.UUID(claim.payload_refs["document_version_id"])
                digest, size, mime = db.execute("SELECT content_sha256,size_bytes,"
                    "detected_mime FROM plm.doc_document_versions WHERE "
                    "document_version_id=%s", (version,)).fetchone()
                with v["runtime"].unit_of_work() as tx:
                    SqlAlchemyParseAttemptRepository().start_first(tx,
                        job_id=claim.job_id,
                        request=DocumentParseAttemptRequest(version, bytes(digest),
                            size, mime, "PDF_TEXT_THEN_OCR", "1"),
                        scope="PROJECT", project_id=v["project"])
                    tx.commit()
            response = client.post(path(claim.job_id), headers=headers(version=1), json=body)
            assert response.status_code == 200, response.text
            assert response.json()["data"]["state"] == "CANCEL_REQUESTED"
            return ParserInputCommand(claim.job_id, claim.fencing_token,
                                      "expired-" + marker)

        command = create("one")
        before = snapshot()
        try:
            service.recover(command=command)
        except ParserCancellationError as exc:
            assert exc.code == "STALE_LEASE", exc.code
        else:
            raise AssertionError("live cancellation recovered")
        assert snapshot() == before
        time.sleep(6.5)
        before = snapshot()
        foreign = ParserInputCommand(command.job_id, command.fencing_token, "foreign")
        for rejected in (foreign, ParserInputCommand(command.job_id,
                                                      command.fencing_token + 1,
                                                      command.worker_ref)):
            try:
                service.recover(command=rejected)
            except ParserCancellationError as exc:
                assert exc.code == "STALE_LEASE", exc.code
            else:
                raise AssertionError("wrong generation recovered")
        assert snapshot() == before

        class FailAudit:
            def append(self, tx, event):
                raise RuntimeError("synthetic audit outage")

        service._audit = FailAudit()
        try:
            service.recover(command=command)
        except ParserCancellationError:
            pass
        else:
            raise AssertionError("audit outage committed")
        assert snapshot() == before
        service._audit = audit
        result = service.recover(command=command)
        assert result.job_id == command.job_id and result.parse_record_id is None
        committed = snapshot()
        assert service.verify_committed(command=command) == result
        assert snapshot() == committed
        running = create("running", with_record=True)
        time.sleep(6.5)
        original = service._leases

        class FailAfterDocument:
            def __getattr__(self, name):
                return getattr(original, name)

            def recover_expired_parse_cancel(self, *args, **kwargs):
                raise RuntimeError("synthetic last-step failure")

        service._leases = FailAfterDocument()
        before = snapshot()
        before_record = tuple(db.execute("SELECT * FROM plm.doc_parse_records "
            "WHERE job_ref=%s", (running.job_id,)))
        try:
            service.recover(command=running)
        except ParserCancellationError:
            pass
        else:
            raise AssertionError("last-step failure committed")
        assert snapshot() == before
        assert tuple(db.execute("SELECT * FROM plm.doc_parse_records WHERE "
            "job_ref=%s", (running.job_id,))) == before_record
        service._leases = original
        result = service.recover(command=running)
        assert result.parse_record_id is not None
        assert service.verify_committed(command=running) == result
        assert db.execute("SELECT parse_state FROM plm.doc_parse_records WHERE "
                          "job_ref=%s", (running.job_id,)).fetchone()[0] == "CANCELLED"
        assert db.execute("SELECT state FROM plm.job_jobs WHERE job_id=%s",
                          (command.job_id,)).fetchone()[0] == "CANCELLED"
        assert db.execute("SELECT state FROM plm.job_leases WHERE job_id=%s AND "
                          "fencing_token=%s", (command.job_id,
                          command.fencing_token)).fetchone()[0] == "EXPIRED"
        assert db.execute("SELECT count(*) FROM plm.aud_events WHERE "
                          "action='DOCUMENT_PARSE_CANCEL_RECOVERED' AND "
                          "target_object_id=%s", (command.job_id,)).fetchone()[0] == 1
        before_replay = snapshot()
        try:
            service.recover(command=command)
        except ParserCancellationError as exc:
            assert exc.code == "STALE_LEASE", exc.code
        else:
            raise AssertionError("terminal recovery replay wrote again")
        assert snapshot() == before_replay
        print("PAR-01-A05-P01-P04-P03-P03: actual expiry, foreign/fence denial, "
              "Audit/last-step rollback, with/without ParseRecord recovery, "
              "read-only receipt and replay PASS")
        if after is not None:
            after(v, db=db, client=client, lease=lease, service=service,
                  headers=headers, path=path, body=body, snapshot=snapshot,
                  create=create, system_actor=system)

    owner.exercise(v, extra=extra)


if __name__ == "__main__":
    owner.fixture.verify(exercise=exercise)
