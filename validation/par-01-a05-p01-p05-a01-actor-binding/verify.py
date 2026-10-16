"""Real PG proof: controlled Parser identity change before commit rolls back."""

from __future__ import annotations

import os
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import SimpleNamespace

from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.document.infrastructure.parse_cancel_repository import SqlAlchemyParseCancelRepository
from plm_assistant.modules.jobs.infrastructure.lease_repository import SqlAlchemyJobLeaseRepository
from plm_assistant.modules.jobs.infrastructure.parse_enqueue_repository import SqlAlchemyParseJobQueueRepository
from plm_assistant.modules.parser.application.cancel_attempt import (
    AcknowledgeParserCancel, ParserCancellationError,
)


spec = spec_from_file_location("_parser_recovery_fixture",
    Path(__file__).resolve().parents[1] /
    "par-01-a05-p01-p04-p03-p03-expired-recovery" / "verify.py")
previous = module_from_spec(spec)
spec.loader.exec_module(previous)
previous.owner.fixture.PORT = int(os.environ.get("PLM_POC_PG_PORT", "55434"))


def exercise(v):
    def after(v, *, db, client, lease, service, headers, path, body,
              snapshot, create, system_actor):
        command = create("actor-binding", with_record=True)
        original = system_actor.assert_current()
        actor = SimpleNamespace(assert_current=lambda: original)
        real_audit = AuditService(SqlAlchemyAuditRepository())

        class ChangingAudit:
            def append(self, tx, event):
                result = real_audit.append(tx, event)
                actor.assert_current = lambda: v["other"]
                return result

        cancellation = AcknowledgeParserCancel(
            unit_of_work=v["runtime"].unit_of_work,
            leases=SqlAlchemyJobLeaseRepository(),
            queue=SqlAlchemyParseJobQueueRepository(),
            documents=SqlAlchemyParseCancelRepository(),
            audit=ChangingAudit(), system_actor=actor)
        before = snapshot()
        before_record = tuple(db.execute("SELECT * FROM plm.doc_parse_records "
            "WHERE job_ref=%s", (command.job_id,)))
        try:
            cancellation.acknowledge(command=command, started=None)
        except ParserCancellationError:
            pass
        else:
            raise AssertionError("changed identity committed")
        assert snapshot() == before
        assert tuple(db.execute("SELECT * FROM plm.doc_parse_records WHERE "
            "job_ref=%s", (command.job_id,))) == before_record

        actor.assert_current = lambda: original
        cancellation._audit = real_audit
        result = cancellation.acknowledge(command=command, started=None)
        assert result.parse_record_id is not None
        assert db.execute("SELECT state FROM plm.job_jobs WHERE job_id=%s",
                          (command.job_id,)).fetchone()[0] == "CANCELLED"
        assert db.execute("SELECT parse_state FROM plm.doc_parse_records WHERE "
                          "job_ref=%s", (command.job_id,)).fetchone()[0] == "CANCELLED"
        print("PAR-01-A05-P01-P05-A01: controlled identity change after Audit "
              "rolled back Document/Audit/Jobs; restored source committed PASS")

    previous.exercise(v, after=after)


if __name__ == "__main__":
    previous.owner.fixture.verify(exercise=exercise)
