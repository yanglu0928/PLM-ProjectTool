"""Windows 11 disposable PG18 proof for authorized SOL-06 revision service."""

from __future__ import annotations

import importlib.util
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path

import psycopg

from plm_assistant.modules.solution.application.revise_structured_spec import (
    ReviseStructuredSpec, StructuredSpecReviseError,
    StructuredSpecReviseService,
)


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "sol06_create_for_revision_service",
    ROOT / "validation/sol-06-a09-p03-structured-spec-create/verify.py")
assert SPEC and SPEC.loader
prior = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prior)


class _DeniedLicense:
    def require_valid(self, **_kwargs):
        from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
        raise RuntimeLicenseError("denied")


class _BrokenAudit:
    def append(self, *_args, **_kwargs):
        raise RuntimeError("audit down")


def rejects(code, operation):
    try:
        operation()
    except StructuredSpecReviseError as error:
        assert error.code == code, (code, error.code)
    else:
        raise AssertionError("expected " + code)


def on_revision(*, port, runtime, audit, license_guard, project, other_project,
                manager, token, csrf, member_token, member_csrf, sources,
                dependencies, draft, first, second, **_unused):
    args = {
        **dependencies, "license_guard": license_guard,
        "sources": sources, "audit": audit,
    }
    service = StructuredSpecReviseService(**args)
    body = replace(draft, spec_series_id=None, supersedes_version_ref=None)
    command = ReviseStructuredSpec(
        token, csrf, uuid.uuid4(), project,
        second.structured_solution_spec_id, body, "r" * 16)
    rejects("AUTH_ACCESS_DENIED", lambda: service.revise(replace(
        command, csrf_token=b"x" * 32)))
    cross_body = replace(body, project_id=other_project)
    rejects("RESOURCE_NOT_FOUND", lambda: service.revise(replace(
        command, project_id=other_project, draft=cross_body,
        idempotency_key="x" * 16)))
    denied = StructuredSpecReviseService(
        **{**args, "license_guard": _DeniedLicense()})
    rejects("LICENSE_OPERATION_DENIED", lambda: denied.revise(command))

    third = service.revise(command)
    assert third.version_no == 3
    assert third.spec_series_id == first.spec_series_id
    assert third.supersedes_version_ref == second.structured_solution_spec_id
    assert service.revise(replace(command, trace_id=uuid.uuid4())) == third
    rejects("CONFLICT_IDEMPOTENCY", lambda: service.revise(replace(
        command, draft=replace(body, payload={**body.payload, "scope": "changed"}))))

    broken = StructuredSpecReviseService(**{**args, "audit": _BrokenAudit()})
    broken_command = replace(
        command, spec_id=third.structured_solution_spec_id,
        idempotency_key="f" * 16)
    rejects("SOLUTION_UNAVAILABLE", lambda: broken.revise(broken_command))

    parallel = replace(
        command, spec_id=third.structured_solution_spec_id,
        idempotency_key="p" * 16)
    with ThreadPoolExecutor(max_workers=2) as pool:
        same_results = tuple(pool.map(service.revise, (parallel, parallel)))
    assert same_results[0] == same_results[1]
    fourth = same_results[0]
    assert fourth.version_no == 4
    assert service.revise(replace(command, trace_id=uuid.uuid4())) == third

    different = (
        replace(command, spec_id=fourth.structured_solution_spec_id,
                idempotency_key="d" * 16),
        replace(command, spec_id=fourth.structured_solution_spec_id,
                idempotency_key="e" * 16),
    )
    with ThreadPoolExecutor(max_workers=2) as pool:
        tasks = tuple(pool.submit(service.revise, item) for item in different)
    outcomes = []
    for task in tasks:
        try:
            outcomes.append(task.result())
        except StructuredSpecReviseError as error:
            outcomes.append(error.code)
    created = [item for item in outcomes if not isinstance(item, str)]
    assert len(created) == 1 and created[0].version_no == 5, outcomes
    assert outcomes.count("VERSION_CONFLICT") == 1, outcomes
    fifth = created[0]
    rejects("VERSION_CONFLICT", lambda: service.revise(replace(
        command, idempotency_key="s" * 16)))
    rejects("SOURCE_UNAVAILABLE", lambda: service.revise(replace(
        command, spec_id=fifth.structured_solution_spec_id,
        draft=replace(body, artifact_ids=(uuid.uuid4(),)),
        idempotency_key="a" * 16)))
    sixth = service.revise(ReviseStructuredSpec(
        member_token, member_csrf, uuid.uuid4(), project,
        fifth.structured_solution_spec_id, body, "m" * 16))
    assert sixth.version_no == 6 and sixth.created_by != manager

    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        assert db.execute(
            "SELECT count(*) FROM plm.sol_structured_specs WHERE spec_series_id=%s",
            (first.spec_series_id,)).fetchone()[0] == 6
        assert db.execute(
            "SELECT count(*) FROM plm.plt_idempotency_receipts "
            "WHERE operation='V1_SOL_STRUCTURED_SPEC_REVISE'").fetchone()[0] == 4
        assert db.execute(
            "SELECT count(*) FROM plm.aud_events "
            "WHERE action='SOL_STRUCTURED_SPEC_REVISED'").fetchone()[0] == 4
        assert db.execute(
            "SELECT count(*) FROM plm.sol_spec_payloads WHERE spec_series_id=%s",
            (first.spec_series_id,)).fetchone()[0] == 6
    print("SOL_06_A12_P03_REVISION_SERVICE_PG_PASS: current auth/license/source "
          "reproof, exact replay after later revision, same/different-key concurrency, "
          "member role, audit rollback, four receipts and audits")


if __name__ == "__main__":
    prior.prior.prior.main(on_created=lambda **kwargs: prior.prior.on_created(
        **kwargs, on_http=lambda **created: prior.on_created(
            **created, on_http=on_revision)))
