"""Opt-in PROJECT Review read boundary for the frozen API v1 path."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from plm_assistant.modules.auth.api.login_origin_policy import (
    LoginOriginError, LoginOriginPolicy,
)
from plm_assistant.modules.auth.api.session import _session_cookie
from plm_assistant.modules.capability.api.commands import _canonical_uuid, _instant
from plm_assistant.modules.platform.application.errors import ApplicationError
from plm_assistant.modules.review.application.read_service import (
    AuthorizedReviewRead, ReviewReadError, ReviewReadQuery, ReviewReadService,
)
from plm_assistant.modules.review.application.read_snapshot import (
    FixedReviewRoundSnapshot, ReviewIdentitySnapshot,
)


def _failure(code: str) -> ApplicationError:
    return ApplicationError({
        "AUTH_ACCESS_DENIED": "AUTH_SESSION_EXPIRED",
        "RESOURCE_NOT_FOUND": "RESOURCE_NOT_FOUND",
        "LICENSE_OPERATION_DENIED": "LICENSE_OPERATION_DENIED",
        "VALIDATION_FAILED": "VALIDATION_FAILED",
    }.get(code, "SYSTEM_UNAVAILABLE"))


def _active_round(value: FixedReviewRoundSnapshot) -> dict[str, object]:
    progress = value.progress
    decisions = {item.reviewer_id: item for item in progress.decisions}
    assignments = []
    for assignment_id, reviewer_id in zip(
            value.assignment_ids, progress.reviewer_ids, strict=True):
        decision = decisions.get(reviewer_id)
        assignments.append({
            "assignment_id": str(assignment_id),
            "reviewer_id": str(reviewer_id),
            "state": "DECIDED" if decision is not None else "PENDING",
            "decision": None if decision is None else {
                "decision_id": str(decision.decision_id),
                "decision": decision.kind.value,
                "comment": decision.comment,
                "decided_at": _instant(decision.decided_at),
            },
        })
    return {
        "review_round_id": str(progress.round_id),
        "round_no": value.round_no,
        "subject_version_ref": str(value.subject_version_id),
        "state": progress.state.value,
        "round_etag": f'"v{value.round_lock_version}"',
        "started_by": str(value.started_by),
        "started_at": _instant(progress.started_at),
        "assignments": assignments,
    }


def _detail(result: AuthorizedReviewRead, project_id: uuid.UUID,
            review_id: uuid.UUID) -> dict[str, object]:
    if type(result) is not AuthorizedReviewRead:
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    identity, fixed = result.review, result.fixed_round
    if (type(identity) is not ReviewIdentitySnapshot
            or identity.scope != "PROJECT"
            or identity.project_id != project_id
            or identity.review_id != review_id
            or (identity.state == "IN_REVIEW") != (fixed is not None)
            or fixed is not None
            and (type(fixed) is not FixedReviewRoundSnapshot
                 or fixed.review != identity
                 or fixed.progress.round_id != identity.active_round_id)):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    try:
        identity.__post_init__()
        if fixed is not None:
            fixed.__post_init__()
        return {
            "review_id": str(review_id),
            "project_id": str(project_id),
            "subject_ref": {
                "resource_type": identity.subject_type,
                "resource_id": str(identity.subject_id),
            },
            "policy_code": identity.policy_code,
            "state": identity.state,
            "active_round": None if fixed is None else _active_round(fixed),
            "etag": result.etag,
        }
    except ApplicationError:
        raise
    except Exception:
        raise ApplicationError("SYSTEM_UNAVAILABLE") from None


def create_review_read_router(
    *, origins: LoginOriginPolicy, reads: ReviewReadService,
) -> APIRouter:
    """Create an explicitly injected router; the default app stays closed."""
    if origins is None or reads is None:
        raise ValueError("Review read HTTP dependencies are required")
    router = APIRouter()

    @router.get("/api/v1/projects/{project_id}/reviews/{review_id}")
    async def get_review(project_id: str, review_id: str,
                         request: Request) -> JSONResponse:
        headers = tuple(request.scope.get("headers", ()))
        try:
            origins.require_trusted_host(headers)
        except LoginOriginError:
            raise ApplicationError("AUTH_CSRF_INVALID") from None
        if request.url.query:
            raise ApplicationError("REQUEST_MALFORMED")
        token = _session_cookie(headers)
        project, review = (
            _canonical_uuid(project_id), _canonical_uuid(review_id))
        trace_id = uuid.UUID(request.state.trace_id)
        try:
            result = await run_in_threadpool(
                reads.get, ReviewReadQuery(
                    token, project, review, trace_id,
                    include_active_round=True,
                ))
        except ReviewReadError as exc:
            raise _failure(exc.code) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        detail = _detail(result, project, review)
        return JSONResponse(
            {"data": detail, "trace_id": str(trace_id)},
            headers={"Cache-Control": "no-store", "ETag": result.etag},
        )

    return router
