"""Authorized, audited, idempotent validation of one immutable PlanVersion."""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import Protocol

from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.domain.audit_event import AuditEventDraft
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.platform.application.idempotency import (
    IdempotencyError, IdempotencyResult, IdempotencyScope,
    canonical_payload_fingerprint, validate_idempotency_key,
)
from plm_assistant.modules.project.application.authorization import (
    ProjectAuthorizationError, ProjectAuthorizationService,
)

from .create_plan_version import PlanVersionCreateService
from .create_plan_version import (
    PlanVersionCreateError, PlanVersionSourceProofError,
)
from .plan_version_input import (
    FixedVersionRef, PlanExclusionInput, RequirementVersionRef,
    parse_plan_version_draft,
)
from .prove_approved_solution_input import (
    ApprovedSolutionInputProof, ApprovedSolutionInputProofError,
)
from .read_plan_version import PlanVersionSnapshotView
from .validate_plan_version_contract import (
    PlanVersionValidationReport, PlanVersionValidationSnapshot,
    evaluate_plan_version,
)


_OPERATION = "V1_PLAN_VERSION_VALIDATE"
_REPORT_REF = "V1_PLAN_VERSION_VALIDATION_REPORT"


class PlanVersionValidationError(RuntimeError):
    def __init__(self, code: str = "PLAN_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class ValidatePlanVersion:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID
    plan_id: uuid.UUID
    plan_version_id: uuid.UUID
    idempotency_key: str = field(repr=False)


class AccessPort(Protocol):
    def authenticated_user(self, transaction: object, *, session_token: bytes,
                           csrf_token: bytes, now: datetime) -> uuid.UUID | None: ...


class LicensePort(Protocol):
    def require_valid(self, *, trace_id: uuid.UUID) -> object: ...


class SnapshotPort(Protocol):
    def get_current(self, transaction: object, *, project_id: uuid.UUID,
                    plan_id: uuid.UUID, plan_version_id: uuid.UUID
                    ) -> PlanVersionSnapshotView | None: ...


class ResultPort(Protocol):
    def get(self, transaction: object, *, audit_event_id: uuid.UUID,
            actor_id: uuid.UUID, project_id: uuid.UUID, plan_id: uuid.UUID,
            plan_version_id: uuid.UUID,
            snapshot_fingerprint: bytes) -> PlanVersionValidationReport | None: ...

    def save(self, transaction: object, *, audit_event_id: uuid.UUID,
             snapshot: PlanVersionValidationSnapshot,
             snapshot_fingerprint: bytes,
             report: PlanVersionValidationReport) -> None: ...


class SolutionProofPort(Protocol):
    def prove(self, transaction: object, *, command: object
              ) -> ApprovedSolutionInputProof: ...


class SourceProofPort(Protocol):
    def validate(self, transaction: object, *, project_id: uuid.UUID,
                 draft: object, solution: ApprovedSolutionInputProof) -> None: ...


class ReceiptPort(Protocol):
    def reserve(self, transaction: object, *, scope: IdempotencyScope,
                request_fingerprint: bytes) -> IdempotencyResult | None: ...
    def complete(self, transaction: object, *, scope: IdempotencyScope,
                 result: IdempotencyResult) -> None: ...


class PlanVersionValidationService:
    def __init__(self, *, unit_of_work: Callable[[], object], access: AccessPort,
                 license_guard: LicensePort,
                 authorization: ProjectAuthorizationService,
                 snapshots: SnapshotPort, results: ResultPort,
                 solution_proof: SolutionProofPort, source_proofs: SourceProofPort,
                 receipts: ReceiptPort, audit: AuditService,
                 clock: Callable[[], datetime] | None = None) -> None:
        if any(value is None for value in (
                unit_of_work, access, license_guard, authorization, snapshots,
                results, solution_proof, source_proofs, receipts, audit)):
            raise ValueError("PlanVersion validation dependencies are required")
        self._uow, self._access, self._guard = unit_of_work, access, license_guard
        self._authorization, self._snapshots, self._results = authorization, snapshots, results
        self._solution_proof, self._source_proofs = solution_proof, source_proofs
        self._receipts, self._audit = receipts, audit
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def validate(self, command: ValidatePlanVersion) -> PlanVersionValidationReport:
        if (type(command) is not ValidatePlanVersion
                or type(command.session_token) is not bytes or len(command.session_token) != 32
                or type(command.csrf_token) is not bytes or len(command.csrf_token) != 32
                or any(type(value) is not uuid.UUID or value.int == 0 for value in (
                    command.trace_id, command.project_id, command.plan_id,
                    command.plan_version_id))):
            raise PlanVersionValidationError("VALIDATION_FAILED")
        try:
            validate_idempotency_key(command.idempotency_key)
            request_fingerprint = canonical_payload_fingerprint({
                "project_id": str(command.project_id),
                "plan_id": str(command.plan_id),
                "plan_version_id": str(command.plan_version_id),
                "body": None,
            })
            self._guard.require_valid(trace_id=command.trace_id)
            with self._uow() as tx:
                now = self._now()
                actor = self._actor(tx, command, now)
                self._authorize(tx, actor, command.project_id)
                snapshot_view = self._snapshots.get_current(
                    tx, project_id=command.project_id, plan_id=command.plan_id,
                    plan_version_id=command.plan_version_id)
                snapshot, fingerprint = self._snapshot(snapshot_view, command)
                scope = IdempotencyScope.from_key(
                    actor_id=actor, project_id=command.project_id,
                    operation=_OPERATION, key=command.idempotency_key)
                replay = self._receipts.reserve(
                    tx, scope=scope, request_fingerprint=request_fingerprint)
                if replay is not None:
                    if replay.ref_type != _REPORT_REF or replay.status_code != 200:
                        raise PlanVersionValidationError()
                    report = self._results.get(
                        tx, audit_event_id=replay.ref_id, actor_id=actor,
                        project_id=command.project_id, plan_id=command.plan_id,
                        plan_version_id=command.plan_version_id,
                        snapshot_fingerprint=fingerprint)
                    if type(report) is not PlanVersionValidationReport:
                        raise PlanVersionValidationError()
                    tx.commit()
                    return report

                report = self._evaluate(tx, command, snapshot)
                reason = "VALIDATION_PASSED" if report.valid else "VALIDATION_BLOCKED"
                audit_id = self._audit.append(tx, AuditEventDraft(
                    trace_id=command.trace_id, event_scope="PROJECT",
                    target_project_id=command.project_id, actor_type="USER",
                    actor_id=actor, original_actor_id=None, actor_hint_digest=None,
                    action="PLAN_VERSION_VALIDATED", outcome="SUCCESS",
                    target_owner_module="plan", target_object_type="PLN-02",
                    target_object_id=command.plan_version_id,
                    target_version_id=command.plan_version_id,
                    reason_code=reason, before_state=snapshot.version_state,
                    after_state=snapshot.version_state,
                ))
                self._results.save(
                    tx, audit_event_id=audit_id, snapshot=snapshot,
                    snapshot_fingerprint=fingerprint, report=report)
                self._receipts.complete(tx, scope=scope, result=IdempotencyResult(
                    _REPORT_REF, audit_id, 200))
                tx.commit()
                return report
        except PlanVersionValidationError:
            raise
        except RuntimeLicenseError:
            raise PlanVersionValidationError("LICENSE_OPERATION_DENIED") from None
        except ProjectAuthorizationError as error:
            raise PlanVersionValidationError(error.code) from None
        except IdempotencyError as error:
            raise PlanVersionValidationError(error.code) from None
        except Exception:
            raise PlanVersionValidationError() from None

    def _evaluate(self, transaction: object, command: ValidatePlanVersion,
                  snapshot: PlanVersionValidationSnapshot) -> PlanVersionValidationReport:
        outline_refs = tuple(ref for ref in snapshot.draft.approved_solution_refs
                             if ref.resource_kind == "OUTLINE")
        if len(outline_refs) != 1:
            return self._source_unavailable(snapshot)
        outline = outline_refs[0]
        try:
            from plm_assistant.modules.solution.application.outline_version_validation_contract import (
                OutlineCurrentFactQuery,
            )
            proof = self._solution_proof.prove(transaction, command=OutlineCurrentFactQuery(
                command.session_token, command.trace_id, command.project_id,
                outline.resource_id, outline.version_id))
            if type(proof) is not ApprovedSolutionInputProof:
                return self._source_unavailable(snapshot)
            try:
                PlanVersionCreateService._validate_solution_refs(
                    command.project_id, snapshot.draft, proof)
            except PlanVersionCreateError:
                return self._evaluate_against_snapshot(
                    snapshot, source_issue="APPROVED_SOURCE_MISMATCH")
            try:
                self._source_proofs.validate(
                    transaction, project_id=command.project_id,
                    draft=snapshot.draft, solution=proof)
            except PlanVersionSourceProofError:
                return self._evaluate_against_snapshot(
                    snapshot, source_issue="APPROVED_SOURCE_UNAVAILABLE")
            current_solutions = {
                FixedVersionRef("OUTLINE", proof.outline_id, proof.outline_version_id),
                *(FixedVersionRef("SECTION", item.section_id, item.section_version_id)
                  for item in proof.sections),
            }
            for section in proof.sections:
                for qualified in section.qualified_specs:
                    ref = qualified.ref
                    current_solutions.add(FixedVersionRef(
                        "STRUCTURED_SPEC", ref.structured_solution_spec_id,
                        ref.structured_solution_spec_id,
                        ref.spec_series_id, ref.spec_type))
            current_requirements = tuple(RequirementVersionRef(
                item.requirement_id, item.requirement_version_id)
                for item in proof.requirement_refs)
            report = evaluate_plan_version(
                snapshot, source_requirement_refs=current_requirements,
                source_solution_refs=tuple(sorted(current_solutions,
                    key=lambda item: (item.resource_kind, str(item.resource_id),
                                      str(item.version_id), str(item.spec_series_id),
                                      item.spec_type or ""))),
                checked_at=self._now())
            return report
        except ApprovedSolutionInputProofError:
            return self._evaluate_against_snapshot(
                snapshot, source_issue="APPROVED_SOURCE_UNAVAILABLE")

    def _evaluate_against_snapshot(self, snapshot: PlanVersionValidationSnapshot,
                                   *, source_issue: str
                                   ) -> PlanVersionValidationReport:
        req_refs = {ref for item in snapshot.draft.wbs_items for ref in item.requirement_refs}
        req_refs.update(RequirementVersionRef(item.resource_id, item.version_id)
                        for item in snapshot.draft.exclusions
                        if item.target_kind == "REQUIREMENT_VERSION")
        report = evaluate_plan_version(
            snapshot, source_requirement_refs=tuple(sorted(
                req_refs, key=lambda item: (str(item.requirement_id),
                                             str(item.requirement_version_id)))),
            source_solution_refs=snapshot.draft.approved_solution_refs,
            checked_at=self._now())
        issues = tuple(sorted((*report.blocking_issues, source_issue)))
        return replace(report, valid=False, blocking_issues=issues)

    def _source_unavailable(self, snapshot: PlanVersionValidationSnapshot
                            ) -> PlanVersionValidationReport:
        return self._evaluate_against_snapshot(
            snapshot, source_issue="APPROVED_SOURCE_UNAVAILABLE")

    def _snapshot(self, value: object, command: ValidatePlanVersion
                  ) -> tuple[PlanVersionValidationSnapshot, bytes]:
        if (type(value) is not PlanVersionSnapshotView
                or value.project_id != command.project_id
                or value.plan_id != command.plan_id
                or value.plan_version_id != command.plan_version_id
                or type(value.version_no) is not int or value.version_no < 1
                or type(value.snapshot) is not dict):
            raise PlanVersionValidationError("RESOURCE_NOT_FOUND")
        try:
            parsed = parse_plan_version_draft(
                value.snapshot, project_id=command.project_id, plan_id=command.plan_id)
            PlanVersionCreateService._validate_codes(parsed.input)
            encoded = json.dumps(
                value.snapshot, ensure_ascii=False, sort_keys=True,
                separators=(",", ":"), allow_nan=False).encode("utf-8")
            if len(encoded) > 8_000_000:
                raise ValueError()
            fingerprint = hashlib.sha256(encoded).digest()
            snapshot = PlanVersionValidationSnapshot(
                value.project_id, value.plan_id, value.plan_version_id,
                value.version_no, value.version_state, fingerprint, parsed.input)
            return snapshot, fingerprint
        except Exception:
            raise PlanVersionValidationError("PLAN_UNAVAILABLE") from None

    def _actor(self, tx: object, command: ValidatePlanVersion,
               now: datetime) -> uuid.UUID:
        actor = self._access.authenticated_user(
            tx, session_token=command.session_token,
            csrf_token=command.csrf_token, now=now)
        if type(actor) is not uuid.UUID or actor.int == 0:
            raise PlanVersionValidationError("AUTH_ACCESS_DENIED")
        return actor

    def _authorize(self, tx: object, actor: uuid.UUID,
                   project_id: uuid.UUID) -> object:
        value = self._authorization.require_in_transaction(
            tx, user_id=actor, project_id=project_id,
            operation="PLAN_VERSION_VALIDATE")
        if (value.user_id != actor or value.project_id != project_id
                or value.operation != "PLAN_VERSION_VALIDATE"):
            raise PlanVersionValidationError("RESOURCE_NOT_FOUND")
        return value

    def _now(self) -> datetime:
        now = self._clock()
        if type(now) is not datetime or now.tzinfo is None or now.utcoffset() is None:
            raise PlanVersionValidationError()
        return now.astimezone(timezone.utc)
