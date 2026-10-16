"""Real PG/HTTP expiry hints and one-step Parser recovery sweep."""

from __future__ import annotations

import os
import time
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

from plm_assistant.modules.jobs.application.parse_cancel_scan import (
    ExpiredParserCancelCandidate, ExpiredParserCancelCandidates,
)
from plm_assistant.modules.jobs.infrastructure.parse_cancel_scan_repository import (
    SqlAlchemyParserCancelScanRepository,
)
from plm_assistant.modules.parser.application.cancel_attempt import ParserCancellationError
from plm_assistant.modules.parser.application.sweep_expired_cancel import ParserExpiredCancelSweep


spec = spec_from_file_location("_expired_cancel_fixture",
    Path(__file__).resolve().parents[1] /
    "par-01-a05-p01-p04-p03-p03-expired-recovery" / "verify.py")
previous = module_from_spec(spec)
spec.loader.exec_module(previous)
previous.owner.fixture.PORT = int(os.environ.get("PLM_POC_PG_PORT", "55434"))


def exercise(v):
    def after(v, *, db, client, lease, service, headers, path, body,
              snapshot, create, system_actor):
        candidates = ExpiredParserCancelCandidates(
            repository=SqlAlchemyParserCancelScanRepository())
        first, second = create("scan-first"), create("scan-second", with_record=True)
        with v["runtime"].unit_of_work() as tx:
            assert candidates.scan_next(tx) is None
        before = snapshot()
        sweep = ParserExpiredCancelSweep(unit_of_work=v["runtime"].unit_of_work,
            candidates=candidates, recovery=service, system_actor=system_actor)
        assert sweep.run_next().kind == "IDLE"
        assert snapshot() == before
        time.sleep(6.5)
        with v["runtime"].unit_of_work() as tx:
            a = candidates.scan_next(tx)
            b = candidates.scan_next(tx, after=a.cursor)
            assert type(a) is ExpiredParserCancelCandidate
            assert type(b) is ExpiredParserCancelCandidate
            assert {a.cursor.job_id, b.cursor.job_id} == {first.job_id, second.job_id}
            assert a.cursor.expired_at <= b.cursor.expired_at
            assert candidates.scan_next(tx, after=b.cursor) is None
        original = system_actor.assert_current

        def unavailable():
            raise RuntimeError("synthetic Vault outage")

        system_actor.assert_current = unavailable
        before = snapshot()
        try:
            sweep.run_next()
        except ParserCancellationError as exc:
            assert exc.code == "SYSTEM_ACTOR_UNAVAILABLE", exc.code
        else:
            raise AssertionError("missing actor scanned")
        finally:
            system_actor.assert_current = original
        assert snapshot() == before

        # A lost acknowledgement after commit must be verified, not re-executed.
        class LostReceipt:
            _system_actor = system_actor

            def recover(self, *, command):
                service.recover(command=command)
                raise RuntimeError("synthetic lost commit acknowledgement")

            def verify_committed(self, *, command):
                return service.verify_committed(command=command)

        sweep = ParserExpiredCancelSweep(unit_of_work=v["runtime"].unit_of_work,
            candidates=candidates, recovery=LostReceipt(), system_actor=system_actor)
        one = sweep.run_next()
        assert one.kind == "RECOVERED" and one.job_id == a.cursor.job_id
        two = sweep.run_next()
        assert two.kind == "RECOVERED" and two.job_id == b.cursor.job_id
        assert sweep.run_next().kind == "IDLE"
        for command in (first, second):
            assert service.verify_committed(command=command).job_id == command.job_id
            assert db.execute("SELECT count(*) FROM plm.aud_events WHERE "
                "action='DOCUMENT_PARSE_CANCEL_RECOVERED' AND target_object_id=%s",
                (command.job_id,)).fetchone()[0] == 1
        assert db.execute("SELECT parse_state FROM plm.doc_parse_records WHERE "
            "job_ref=%s", (second.job_id,)).fetchone()[0] == "CANCELLED"
        print("PAR-01-A05-P01-P04-P03-P04: actual PG expiry scan, ordered "
              "two-job sweep, actor outage, lost receipt and no duplicate PASS")

    previous.exercise(v, after=after)


if __name__ == "__main__":
    previous.owner.fixture.verify(exercise=exercise)
