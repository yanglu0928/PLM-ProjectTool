"""Opt-in frozen PLAN_VERSION_SUBMIT_REVIEW HTTP boundary."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginError, LoginOriginPolicy
from plm_assistant.modules.auth.api.session import _csrf_header, _idempotency_header, _session_cookie, _session_failure
from plm_assistant.modules.auth.application.session_service import SessionError, SessionService
from plm_assistant.modules.platform.application.errors import ApplicationError
from plm_assistant.modules.review.application.project_persistence import SubmittedProjectReviewRef
from ._request import canonical_uuid, read_body
from ..application.submit_plan_version_review import (
    PlanVersionReviewSubmissionError, PlanVersionReviewSubmissionService,
    SubmitPlanVersionReview,
)


_FIELDS = frozenset({"reviewer_ids", "policy_ref", "due_at", "submission_note"})


def _failure(error: PlanVersionReviewSubmissionError) -> ApplicationError:
    return ApplicationError({
        "AUTH_ACCESS_DENIED": "RESOURCE_NOT_FOUND",
        "RESOURCE_NOT_FOUND": "RESOURCE_NOT_FOUND",
        "PROJECT_ARCHIVED": "PROJECT_ARCHIVED",
        "LICENSE_OPERATION_DENIED": "LICENSE_OPERATION_DENIED",
        "CONFLICT_IDEMPOTENCY": "CONFLICT_IDEMPOTENCY",
        "VALIDATION_FAILED": "VALIDATION_FAILED",
        "BUSINESS_REVIEW_NOT_ELIGIBLE": "BUSINESS_REVIEW_NOT_ELIGIBLE",
        "REVIEW_REVIEWER_INELIGIBLE": "REVIEW_REVIEWER_INELIGIBLE",
        "REVIEW_SUBJECT_LOCKED": "REVIEW_SUBJECT_LOCKED",
        "CONFLICT_VERSION": "CONFLICT_VERSION",
    }.get(error.code, "SYSTEM_UNAVAILABLE"))


def _response(result: SubmittedProjectReviewRef, *, project: uuid.UUID,
              plan: uuid.UUID, version: uuid.UUID) -> dict[str, object]:
    if (type(result) is not SubmittedProjectReviewRef
            or result.project_id != project
            or result.subject_type != "PLN-02"
            or result.subject_id != version
            or result.subject_version_id != version
            or result.policy_code != "PLAN_VERSION_ALL_V1"
            or result.round_no != 1 or result.review_after_version != 1
            or type(result.submitted_at) is not datetime
            or result.submitted_at.tzinfo is None
            or result.submitted_at.utcoffset() is None):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    result.__post_init__()
    return {
        "review_id": str(result.review_id),
        "review_round_id": str(result.round_id),
        "subject_type": "PLN-02",
        "project_id": str(project),
        "plan_id": str(plan),
        "plan_version_id": str(version),
        "policy_ref": result.policy_code,
        "reviewer_ids": [str(value) for value in result.reviewer_ids],
        "state": "IN_REVIEW", "round_no": result.round_no,
        "review_etag": '"v1"',
        "submitted_by": str(result.submitted_by),
        "submitted_at": result.submitted_at.astimezone(timezone.utc).isoformat().replace(
            "+00:00", "Z"),
    }


def create_plan_version_review_submission_router(
        *, sessions: SessionService, origins: LoginOriginPolicy,
        submissions: PlanVersionReviewSubmissionService) -> APIRouter:
    if any(value is None for value in (sessions, origins, submissions)):
        raise ValueError("PlanVersion Review HTTP dependencies required")
    router = APIRouter()

    @router.post(
        "/api/v1/projects/{project_id}/plans/{plan_id}/versions/"
        "{plan_version_id}:submit-review")
    async def submit_review(project_id: str, plan_id: str,
                           plan_version_id: str, request: Request) -> JSONResponse:
        headers = tuple(request.scope.get("headers", ()))
        try:
            origins.require_trusted(headers)
        except LoginOriginError:
            raise ApplicationError("AUTH_CSRF_INVALID") from None
        token, csrf = _session_cookie(headers), _csrf_header(headers)
        try:
            await run_in_threadpool(
                sessions.validate, token, csrf_token=csrf, require_csrf=True)
        except SessionError as error:
            raise _session_failure(error) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if request.url.query:
            raise ApplicationError("REQUEST_MALFORMED")
        key = _idempotency_header(headers)
        project, plan, version = (
            canonical_uuid(project_id), canonical_uuid(plan_id),
            canonical_uuid(plan_version_id))
        body = await read_body(request, headers, maximum_bytes=32 * 1024)
        if type(body) is not dict or set(body) != _FIELDS:
            raise ApplicationError("REQUEST_MALFORMED")
        reviewers = body["reviewer_ids"]
        if (type(reviewers) is not list
                or body["policy_ref"] != "PLAN_VERSION_ALL_V1"
                or body["due_at"] is not None
                or body["submission_note"] is not None):
            raise ApplicationError("VALIDATION_FAILED")
        command = SubmitPlanVersionReview(
            token, csrf, uuid.UUID(request.state.trace_id), project, plan,
            version, tuple(canonical_uuid(value) for value in reviewers),
            body["policy_ref"], key)
        try:
            result = await run_in_threadpool(submissions.submit, command)
        except PlanVersionReviewSubmissionError as error:
            raise _failure(error) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        etag = f'"v{result.review_after_version}"'
        data = _response(result, project=project, plan=plan, version=version)
        if data["review_etag"] != etag:
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        return JSONResponse(
            {"data": data, "trace_id": request.state.trace_id}, status_code=201,
            headers={"Cache-Control": "no-store", "ETag": etag})

    return router
