"""Opt-in PROJECT Review write boundary for the frozen API v1 paths."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.api.session import _idempotency_header
from plm_assistant.modules.auth.application.session_service import SessionService
from plm_assistant.modules.capability.api.commands import (
    _canonical_uuid, _instant, _read_json, _security,
)
from plm_assistant.modules.platform.api.if_match import parse_if_match
from plm_assistant.modules.platform.application.errors import ApplicationError
from plm_assistant.modules.review.application.create_review import (
    CreateReview, CreatedReviewRef, ReviewCreateError, ReviewCreateService,
)
from plm_assistant.modules.review.application.persist_round import StartedReviewRoundRef
from plm_assistant.modules.review.application.persist_transition import (
    AppliedReviewTransitionRef,
)
from plm_assistant.modules.review.application.start_round import (
    ReviewStartError, ReviewStartService, StartReviewRound,
)
from plm_assistant.modules.review.application.transition_command import (
    DecideReviewRound, ReviewTransitionCommandError,
    ReviewTransitionCommandService, WithdrawReviewRound,
)
from plm_assistant.modules.review.domain.round_progress import ReviewDecisionKind


_CREATE_FIELDS = frozenset({"subject_ref"})
_SUBJECT_FIELDS = frozenset({"resource_type", "resource_id", "version_id"})
_START_FIELDS = frozenset({"subject_version_ref", "reviewer_user_ids", "policy_code"})
_DECIDE_FIELDS = frozenset({"decision", "comment"})
_WITHDRAW_FIELDS = frozenset({"reason"})


def _failure(code: str) -> ApplicationError:
    mapped = {
        "AUTH_ACCESS_DENIED": "RESOURCE_NOT_FOUND",
        "RESOURCE_NOT_FOUND": "RESOURCE_NOT_FOUND",
        "PROJECT_ARCHIVED": "PROJECT_ARCHIVED",
        "LICENSE_OPERATION_DENIED": "LICENSE_OPERATION_DENIED",
        "VALIDATION_FAILED": "VALIDATION_FAILED",
        "CONFLICT_IDEMPOTENCY": "CONFLICT_IDEMPOTENCY",
        "CONFLICT_VERSION": "CONFLICT_VERSION",
        "REVIEW_SUBJECT_LOCKED": "REVIEW_SUBJECT_LOCKED",
        "REVIEW_REVIEWER_INELIGIBLE": "REVIEW_REVIEWER_INELIGIBLE",
        "REVIEW_COMMENT_REQUIRED": "REVIEW_COMMENT_REQUIRED",
        "REVIEW_DECISION_EXISTS": "REVIEW_DECISION_EXISTS",
        "REVIEW_ROUND_STATE_INVALID": "CONFLICT_STATE",
    }.get(code, "SYSTEM_UNAVAILABLE")
    return ApplicationError(mapped)


def _object(body: object, fields: frozenset[str]) -> dict[str, object]:
    if type(body) is not dict or set(body) != fields:
        raise ApplicationError("REQUEST_MALFORMED")
    return body


def _text_or_none(value: object) -> str | None:
    if value is not None and type(value) is not str:
        raise ApplicationError("VALIDATION_FAILED")
    return value


def _response(data: dict[str, object], request: Request, status: int, *,
              etag: str | None = None, location: str | None = None) -> JSONResponse:
    headers = {"Cache-Control": "no-store"}
    if etag is not None:
        headers["ETag"] = etag
    if location is not None:
        headers["Location"] = location
    return JSONResponse(
        {"data": data, "trace_id": request.state.trace_id},
        status_code=status, headers=headers,
    )


def create_review_command_router(
    *, sessions: SessionService, origins: LoginOriginPolicy,
    creates: ReviewCreateService, starts: ReviewStartService,
    transitions: ReviewTransitionCommandService,
) -> APIRouter:
    """Create an explicitly injected router; unknown Subject Owners fail closed."""
    if any(value is None for value in (sessions, origins, creates, starts, transitions)):
        raise ValueError("Review command HTTP dependencies are required")
    router = APIRouter()

    @router.post("/api/v1/projects/{project_id}/reviews")
    async def create(project_id: str, request: Request) -> JSONResponse:
        token, csrf = await _security(request, sessions, origins)
        headers = tuple(request.scope.get("headers", ()))
        key = _idempotency_header(headers)
        body = _object(await _read_json(request, headers), _CREATE_FIELDS)
        subject = _object(body["subject_ref"], _SUBJECT_FIELDS)
        resource_type = subject["resource_type"]
        if type(resource_type) is not str:
            raise ApplicationError("VALIDATION_FAILED")
        command = CreateReview(
            token, csrf, uuid.UUID(request.state.trace_id),
            _canonical_uuid(project_id), resource_type,
            _canonical_uuid(subject["resource_id"]),
            _canonical_uuid(subject["version_id"]),
        )
        try:
            result = await run_in_threadpool(
                creates.create_idempotent, command, idempotency_key=key,
            )
        except ReviewCreateError as exc:
            raise _failure(exc.code) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if type(result) is not CreatedReviewRef:
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        etag = '"v0"'
        path = f"/api/v1/projects/{project_id}/reviews/{result.review_id}"
        return _response({
            "review_id": str(result.review_id),
            "subject_ref": {
                "resource_type": result.subject_type,
                "resource_id": str(result.subject_id),
                "version_id": str(command.subject_version_id),
            },
            "policy_code": result.policy_code, "state": "DRAFT",
            "active_round": None, "etag": etag,
            "created_by": str(result.created_by),
            "created_at": _instant(result.created_at),
        }, request, 201, etag=etag, location=path)

    @router.post("/api/v1/projects/{project_id}/reviews/{review_id}/rounds")
    async def start(project_id: str, review_id: str, request: Request) -> JSONResponse:
        token, csrf = await _security(request, sessions, origins)
        headers = tuple(request.scope.get("headers", ()))
        key = _idempotency_header(headers)
        expected = parse_if_match(headers)
        body = _object(await _read_json(request, headers), _START_FIELDS)
        reviewers = body["reviewer_user_ids"]
        policy = body["policy_code"]
        if type(reviewers) is not list or type(policy) is not str:
            raise ApplicationError("VALIDATION_FAILED")
        command = StartReviewRound(
            token, csrf, _canonical_uuid(project_id), _canonical_uuid(review_id),
            _canonical_uuid(body["subject_version_ref"]),
            tuple(_canonical_uuid(value) for value in reviewers),
            policy, expected, uuid.UUID(request.state.trace_id),
        )
        try:
            result = await run_in_threadpool(
                starts.start_idempotent, command, idempotency_key=key,
            )
        except ReviewStartError as exc:
            raise _failure(exc.code) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if type(result) is not StartedReviewRoundRef:
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        etag = f'"v{expected + 1}"'
        location = (
            f"/api/v1/projects/{project_id}/reviews/{review_id}/rounds/"
            f"{result.round_id}"
        )
        return _response({
            "review_id": str(result.review_id),
            "review_round_id": str(result.round_id),
            "subject_version_ref": str(result.subject_version_id),
            "reviewer_user_ids": [str(value) for value in sorted(command.reviewer_ids)],
            "policy_code": command.policy_code, "state": "IN_REVIEW",
            "round_no": result.round_no, "etag": etag,
            "started_by": str(result.started_by),
            "started_at": _instant(result.started_at),
        }, request, 201, etag=etag, location=location)

    @router.post(
        "/api/v1/projects/{project_id}/reviews/{review_id}/rounds/"
        "{review_round_id}:decide"
    )
    async def decide(project_id: str, review_id: str, review_round_id: str,
                     request: Request) -> JSONResponse:
        token, csrf = await _security(request, sessions, origins)
        headers = tuple(request.scope.get("headers", ()))
        key = _idempotency_header(headers)
        body = _object(await _read_json(request, headers), _DECIDE_FIELDS)
        decision = body["decision"]
        try:
            kind = ReviewDecisionKind(decision) if type(decision) is str else None
        except ValueError:
            kind = None
        if kind is None:
            raise ApplicationError("VALIDATION_FAILED")
        comment = _text_or_none(body["comment"])
        if kind is ReviewDecisionKind.RETURN and (
                comment is None or not comment.strip()):
            raise ApplicationError("REVIEW_COMMENT_REQUIRED")
        command = DecideReviewRound(
            token, csrf, _canonical_uuid(project_id), _canonical_uuid(review_id),
            _canonical_uuid(review_round_id), uuid.UUID(request.state.trace_id),
            kind, comment,
        )
        try:
            result = await run_in_threadpool(
                transitions.decide_idempotent, command, idempotency_key=key,
            )
        except ReviewTransitionCommandError as exc:
            raise _failure(exc.code) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        return _transition_response(result, request, decision=kind.value)

    @router.post(
        "/api/v1/projects/{project_id}/reviews/{review_id}/rounds/"
        "{review_round_id}:withdraw"
    )
    async def withdraw(project_id: str, review_id: str, review_round_id: str,
                       request: Request) -> JSONResponse:
        token, csrf = await _security(request, sessions, origins)
        headers = tuple(request.scope.get("headers", ()))
        key = _idempotency_header(headers)
        expected = parse_if_match(headers)
        body = _object(await _read_json(request, headers), _WITHDRAW_FIELDS)
        command = WithdrawReviewRound(
            token, csrf, _canonical_uuid(project_id), _canonical_uuid(review_id),
            _canonical_uuid(review_round_id), uuid.UUID(request.state.trace_id),
            expected, _text_or_none(body["reason"]),
        )
        try:
            result = await run_in_threadpool(
                transitions.withdraw_idempotent, command, idempotency_key=key,
            )
        except ReviewTransitionCommandError as exc:
            raise _failure(exc.code) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        return _transition_response(result, request)

    return router


def _transition_response(result: object, request: Request, *,
                         decision: str | None = None) -> JSONResponse:
    if type(result) is not AppliedReviewTransitionRef:
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    etag = f'"v{result.review_after_version}"'
    data: dict[str, object] = {
        "review_id": str(result.review_id),
        "review_round_id": str(result.round_id),
        "subject_version_ref": str(result.subject_version_id),
        "actor_id": str(result.actor_id), "state": result.state.value,
        "etag": etag, "round_etag": f'"v{result.round_after_version}"',
        "occurred_at": _instant(result.occurred_at),
        "event_id": str(result.event_id),
    }
    if decision is not None:
        data.update({
            "assignment_state": "DECIDED", "decision": decision,
            "decision_id": str(result.decision_id),
        })
    else:
        data["withdrawn"] = True
    return _response(data, request, 200, etag=etag)
