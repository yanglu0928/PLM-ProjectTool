"""Win11 disposable PG proof for fixed SOL-06 validation sources."""

from __future__ import annotations

import importlib.util
import uuid
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from pathlib import Path
from threading import Event

from plm_assistant.modules.solution.infrastructure.structured_spec_validation_repository import (
    SqlAlchemyStructuredSpecValidationRepository,
)


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "sol06_repository_for_validation",
    ROOT / "validation/sol-06-a09-p02-structured-spec-repository/verify.py")
assert SPEC and SPEC.loader
prior = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prior)


def on_validation(*, runtime, project, other_project, first, second,
                  repository, **_unused) -> None:
    validations = SqlAlchemyStructuredSpecValidationRepository()
    with runtime.unit_of_work() as transaction:
        historical = validations.lock_source(
            transaction, project_id=project,
            spec_id=first.structured_solution_spec_id)
        current = validations.lock_source(
            transaction, project_id=project,
            spec_id=second.structured_solution_spec_id)
        assert validations.lock_source(
            transaction, project_id=other_project,
            spec_id=first.structured_solution_spec_id) is None
        assert historical is not None and current is not None
        assert historical.snapshot.version_no == 1
        assert historical.snapshot.spec_series_id == first.spec_series_id
        assert historical.draft.spec_series_id is None
        assert historical.draft.supersedes_version_ref is None
        assert not historical.is_current_version
        assert historical.latest_version_ref == second.structured_solution_spec_id
        assert historical.latest_version_no == 2
        assert current.snapshot.version_no == 2 and current.is_current_version
        assert current.draft.spec_series_id == first.spec_series_id
        assert (current.draft.supersedes_version_ref
                == first.structured_solution_spec_id)
        assert current.draft.payload() == first.payload()
        assert current.draft.requirement_refs == first.requirement_refs
        assert current.draft.section_refs == first.section_refs
        assert current.draft.evidence_ids == first.evidence_ids

        # A second validation may share the series lock while the first
        # observation remains open.
        def shared_read():
            with runtime.unit_of_work() as nested:
                value = validations.lock_source(
                    nested, project_id=project,
                    spec_id=second.structured_solution_spec_id)
                nested.commit()
                return value

        with ThreadPoolExecutor(max_workers=1) as pool:
            shared = pool.submit(shared_read).result(timeout=10)
        assert shared is not None and shared.is_current_version

        # CREATE/REVISE use the same namespace with an exclusive lock. It must
        # wait until this validation observation transaction is committed.
        started = Event()

        def exclusive_revision_read():
            with runtime.unit_of_work() as nested:
                started.set()
                value = repository.revision_base(
                    nested, project_id=project,
                    spec_id=second.structured_solution_spec_id)
                nested.commit()
                return value

        pool = ThreadPoolExecutor(max_workers=1)
        writer = pool.submit(exclusive_revision_read)
        assert started.wait(timeout=5)
        try:
            writer.result(timeout=0.5)
        except TimeoutError:
            pass
        else:
            raise AssertionError("exclusive revision lock crossed validation")
        transaction.commit()
        base = writer.result(timeout=10)
        pool.shutdown(wait=True)
        assert base.latest_version_ref == second.structured_solution_spec_id
        assert base.version_no == base.latest_version_no == 2

    print("SOL_06_A13_P03_VALIDATION_REPOSITORY_PG_PASS: fixed v1/v2, "
          "historical/current identity, cross-project hidden, concurrent shared "
          "validation and exclusive revision serialization")


if __name__ == "__main__":
    prior.prior.prior.main(on_created=lambda **kwargs: prior.prior.on_created(
        **kwargs, on_http=lambda **created: prior.on_created(
            **created, on_http=on_validation)))
