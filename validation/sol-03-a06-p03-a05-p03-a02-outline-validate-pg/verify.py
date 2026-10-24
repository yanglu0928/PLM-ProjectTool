"""Disposable Win11/PG proof for Outline VALIDATE Audit and durable replay."""

from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path
from types import SimpleNamespace

import psycopg

from plm_assistant.modules.auth.infrastructure.project_write_access import (
    SqlAlchemyProjectWriteAccess,
)
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import (
    SqlAlchemyIdempotencyReceipts,
)
from plm_assistant.modules.project.application.authorization import (
    ProjectAuthorizationService,
)
from plm_assistant.modules.project.infrastructure.authorization_repository import (
    SqlAlchemyProjectAuthorizationRepository,
)
from plm_assistant.modules.solution.application.outline_version_validation_contract import (
    OutlineVersionValidationFacts,
    ValidateOutlineVersion,
)
from plm_assistant.modules.solution.application.validate_outline_version import (
    OutlineVersionValidationError,
    OutlineVersionValidationService,
)
from plm_assistant.modules.solution.infrastructure.outline_read_repository import (
    SqlAlchemyOutlineReadRepository,
)
from plm_assistant.modules.solution.infrastructure.outline_version_read_repository import (
    SqlAlchemyOutlineVersionReadRepository,
)
from plm_assistant.modules.solution.infrastructure.outline_version_validation_audit_source import (
    SqlAlchemyOutlineVersionValidationAuditSource,
)


ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "outline_create_for_validation",
    ROOT / "validation/sol-03-a04-p03-p03-p05-a02-outline-version-http-pg/verify.py",
)
assert spec is not None and spec.loader is not None
previous = importlib.util.module_from_spec(spec)
spec.loader.exec_module(previous)


def _service(*, runtime, license_guard, audit, current):
    return OutlineVersionValidationService(
        unit_of_work=runtime.unit_of_work,
        access=SqlAlchemyProjectWriteAccess(),
        license_guard=license_guard,
        authorization=ProjectAuthorizationService(
            unit_of_work=runtime.unit_of_work,
            repository=SqlAlchemyProjectAuthorizationRepository(),
        ),
        outlines=SqlAlchemyOutlineReadRepository(),
        versions=SqlAlchemyOutlineVersionReadRepository(),
        current=current, receipts=SqlAlchemyIdempotencyReceipts(),
        audit=audit,
        audit_source=SqlAlchemyOutlineVersionValidationAuditSource(),
    )


def _counts(port, version):
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        audit_count = db.execute(
            "SELECT count(*) FROM plm.aud_events WHERE "
            "action='SOL_OUTLINE_VERSION_VALIDATED' AND target_version_id=%s",
            (version,),
        ).fetchone()[0]
        receipt_count = db.execute(
            "SELECT count(*) FROM plm.plt_idempotency_receipts WHERE "
            "operation='V1_SOL_OUTLINE_VERSION_VALIDATE'",
        ).fetchone()[0]
    return audit_count, receipt_count


def project_created(**context):
    previous.project_created(**context)
    runtime, project, other_project, token, csrf, port = (
        context[name] for name in (
            "runtime", "project", "other_project", "token", "csrf", "port"
        )
    )
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        outline, version = db.execute(
            "SELECT solution_outline_id,solution_outline_version_id "
            "FROM plm.sol_outline_versions WHERE project_id=%s "
            "ORDER BY version_no LIMIT 1", (project,),
        ).fetchone()

    current = SimpleNamespace(
        result=OutlineVersionValidationFacts("PASS", "PASS", "UNAVAILABLE"),
        calls=0,
    )
    def facts(tx, *, command, version):
        assert command.project_id == project
        assert version.solution_outline_version_id == command.solution_outline_version_id
        assert tx.session.in_transaction()
        current.calls += 1
        return current.result
    current.facts = facts
    service = _service(
        runtime=runtime, license_guard=context["license_guard"],
        audit=context["audit"], current=current,
    )
    def cmd(key, *, trace=None, target_project=project):
        return ValidateOutlineVersion(
            token, csrf, trace or uuid.uuid4(), target_project,
            outline, version, key,
        )

    first = service.validate(cmd("outline-pg-validate-0001"))
    assert first.facts.coverage == "UNAVAILABLE" and not first.valid
    assert _counts(port, version) == (1, 1)
    current.result = OutlineVersionValidationFacts("PASS", "PASS", "FAIL")
    replay = service.validate(cmd("outline-pg-validate-0001"))
    assert replay == first and current.calls == 1
    assert _counts(port, version) == (1, 1)
    changed = service.validate(cmd("outline-pg-validate-0002"))
    assert changed.facts.coverage == "FAIL" and current.calls == 2
    assert _counts(port, version) == (2, 2)

    for denied in (
        _service(runtime=runtime, license_guard=previous.DeniedLicense(),
                 audit=context["audit"], current=current),
        service,
    ):
        try:
            denied.validate(cmd("outline-pg-denied-0001",
                                target_project=(other_project if denied is service
                                                else project)))
        except OutlineVersionValidationError:
            pass
        else:
            raise AssertionError("License or cross-project access was accepted")
    assert _counts(port, version) == (2, 2)

    def broken_audit(_tx, _event):
        raise RuntimeError("synthetic Audit failure")
    broken = _service(
        runtime=runtime, license_guard=context["license_guard"],
        audit=SimpleNamespace(append=broken_audit), current=current,
    )
    try:
        broken.validate(cmd("outline-pg-audit-fail-0001"))
    except OutlineVersionValidationError:
        pass
    else:
        raise AssertionError("Audit failure was accepted")
    assert _counts(port, version) == (2, 2)
    print("SOL_03_A06_P03_A05_P03_A02_OUTLINE_VALIDATE_PG_PASS: "
          "real Session/Project/License, Audit/Receipt, replay, new-key "
          "reproof, cross-project and Audit failure rollback")
    return 0


if __name__ == "__main__":
    previous.fixture.main(on_created=project_created)
