"""Actual PG18/committed synthetic upload through the explicit Parser Worker factory."""

from __future__ import annotations

import os
import uuid
import pymupdf
from dataclasses import replace
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import SimpleNamespace

from plm_assistant.entrypoints.parser_worker import ParserWorkerSettings, create_parser_worker
from plm_assistant.modules.parser.infrastructure.paddle_ocr import OfflinePaddleOcr
from plm_assistant.modules.platform.infrastructure.worker_database import (
    WorkerDatabaseLimits, WorkerDatabaseRuntime,
)
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository


spec = spec_from_file_location("_parser_composition_fixture",
    Path(__file__).resolve().parents[1] /
    "par-01-a05-p01-p04-p03-p02-cancel-owner" / "verify.py")
fixture = module_from_spec(spec)
spec.loader.exec_module(fixture)
fixture.fixture.PORT = int(os.environ.get("PLM_POC_PG_PORT", "55434"))


class Guard:
    enabled = True

    def require_valid(self, *, trace_id):
        if not self.enabled:
            raise RuntimeError("synthetic License disabled")
        return object()


def exercise(v):
    def extra(v, *, db, client, lease, headers, path, body, snapshot):
        with pymupdf.open() as document:
            document.new_page().insert_text((72, 72), "Synthetic Parser worker composition")
            content = document.tobytes()
        upload, _, _ = v["seed"](content)
        request = replace(v["cmd"], upload_id=upload, trace_id=uuid.uuid4(),
                          max_bytes=len(content))
        ref = v["worker"].commit(request,
            idempotency_key="synthetic-parser-composition")
        runtime = WorkerDatabaseRuntime(runtime=v["runtime"],
                                        limits=WorkerDatabaseLimits())
        guard = Guard()
        actor = SimpleNamespace(assert_current=lambda: v["actor"])
        projects = ProjectAuthorizationService(
            unit_of_work=runtime.unit_of_work,
            repository=SqlAlchemyProjectAuthorizationRepository())
        engine = object.__new__(OfflinePaddleOcr)  # Text-only; no OCR result asserted.
        engine.model_fingerprint = "a" * 64
        loop = create_parser_worker(database=runtime, projects=projects,
            license_guard=guard, system_actor=actor, data_root=v["root"],
            ocr_engine=engine, settings=ParserWorkerSettings("parser-composition"))
        result = loop.run(max_cycles=1)
        if result.published != 1:
            print("Job diagnostic:", db.execute(
                "SELECT j.state,a.error_code FROM plm.job_jobs j LEFT JOIN "
                "plm.job_attempts a ON a.job_id=j.job_id WHERE j.job_id=%s",
                (ref.parse_job_id,)).fetchall())
        assert (result.reason, result.cycles, result.published) == ("LIMIT", 1, 1), result
        assert db.execute("SELECT state FROM plm.job_jobs WHERE job_id=%s",
            (ref.parse_job_id,)).fetchone()[0] == "SUCCEEDED"
        assert db.execute("SELECT count(*) FROM plm.doc_parse_result_refs WHERE "
            "parse_record_id=(SELECT parse_record_id FROM plm.doc_parse_records "
            "WHERE job_ref=%s)", (ref.parse_job_id,)).fetchone()[0] == 1
        with loop.quiescent():
            pass
        print("PAR-01-A05-P01-P05-A02-P03-A01: actual PG18/committed "
              "synthetic text upload -> explicit worker composition -> "
              "unique published ParseResult PASS")

    fixture.exercise(v, extra=extra)


if __name__ == "__main__":
    fixture.fixture.verify(exercise=exercise)
