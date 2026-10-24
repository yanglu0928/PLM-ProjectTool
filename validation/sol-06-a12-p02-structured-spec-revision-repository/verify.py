"""Win11 disposable PG proof for locked SOL-06 revision persistence."""

from __future__ import annotations

import importlib.util
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from threading import Barrier

import psycopg


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "sol06_repository_for_revision",
    ROOT / "validation/sol-06-a09-p02-structured-spec-repository/verify.py")
assert SPEC and SPEC.loader
prior = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prior)


def on_revision(*, port, runtime, project, other_project, manager, token,
                first, second, repository, sources, draft, **_unused) -> None:
    with runtime.unit_of_work() as transaction:
        current = repository.revision_base(
            transaction, project_id=project,
            spec_id=second.structured_solution_spec_id)
        stale = repository.revision_base(
            transaction, project_id=project,
            spec_id=first.structured_solution_spec_id)
        assert repository.revision_base(
            transaction, project_id=other_project,
            spec_id=second.structured_solution_spec_id) is None
        assert current.latest_version_ref == second.structured_solution_spec_id
        assert current.version_no == current.latest_version_no == 2
        assert current.version_state == "DRAFT"
        assert stale.latest_version_ref == second.structured_solution_spec_id
        assert stale.latest_version_no == 2 and stale.version_no == 1
        transaction.commit()

    barrier = Barrier(2)

    def revise_once() -> str:
        barrier.wait(timeout=10)
        with runtime.unit_of_work() as transaction:
            base = repository.revision_base(
                transaction, project_id=project,
                spec_id=second.structured_solution_spec_id)
            if base.latest_version_ref != second.structured_solution_spec_id:
                return "VERSION_CONFLICT"
            value = replace(
                draft, spec_series_id=base.spec_series_id,
                supersedes_version_ref=base.structured_solution_spec_id)
            proof = sources.prove(
                transaction, session_token=token,
                trace_id=uuid.uuid4(), draft=value)
            result = repository.revise(
                transaction, base=base, version_id=uuid.uuid4(),
                actor_id=manager, proof=proof)
            transaction.commit()
            return f"CREATED:{result.version_no}:{result.structured_solution_spec_id}"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = sorted(task.result() for task in (
            pool.submit(revise_once), pool.submit(revise_once)))
    assert sum(value.startswith("CREATED:3:") for value in outcomes) == 1, outcomes
    assert outcomes.count("VERSION_CONFLICT") == 1, outcomes
    created_id = uuid.UUID(next(
        value.rsplit(":", 1)[1] for value in outcomes
        if value.startswith("CREATED:")))
    with runtime.unit_of_work() as transaction:
        latest = repository.revision_base(
            transaction, project_id=project, spec_id=created_id)
        assert latest.latest_version_ref == created_id
        assert latest.version_no == latest.latest_version_no == 3
        replay = repository.first_result(
            transaction, version_id=created_id, project_id=project)
        assert replay is not None and replay.version_no == 3
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        assert db.execute(
            "SELECT count(*) FROM plm.sol_structured_specs WHERE spec_series_id=%s",
            (first.spec_series_id,)).fetchone()[0] == 3
        assert db.execute(
            "SELECT count(*) FROM plm.sol_spec_payloads WHERE spec_series_id=%s",
            (first.spec_series_id,)).fetchone()[0] == 3
        assert db.execute(
            "SELECT count(*) FROM plm.sol_spec_requirement_refs WHERE spec_series_id=%s",
            (first.spec_series_id,)).fetchone()[0] == 3
        assert db.execute(
            "SELECT count(*) FROM plm.sol_spec_section_refs WHERE spec_series_id=%s",
            (first.spec_series_id,)).fetchone()[0] == 3
    print("SOL_06_A12_P02_REVISION_REPOSITORY_PG_PASS: locked latest/base, "
          "cross-project hidden, one of two concurrent revisions, complete v3")


if __name__ == "__main__":
    prior.prior.prior.main(on_created=lambda **kwargs: prior.prior.on_created(
        **kwargs, on_http=lambda **created: prior.on_created(
            **created, on_http=on_revision)))
