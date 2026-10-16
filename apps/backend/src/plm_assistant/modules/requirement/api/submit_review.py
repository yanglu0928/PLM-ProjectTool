"""Opt-in RequirementVersion submit-review HTTP boundary."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.api.session import _idempotency_header
from plm_assistant.modules.auth.application.session_service import SessionService
from plm_assistant.modules.platform.application.errors import ApplicationError
from plm_assistant.modules.requirement.application.submit_review import (
    RequirementReviewSubmissionError, RequirementReviewSubmissionService,
    SubmitRequirementVersionReview,
)
from plm_assistant.modules.review.application.project_persistence import (
    SubmittedProjectReviewRef,
)

from .versions import _canonical_uuid, _instant, _read_json, _write_security


_FIELDS = frozenset({"reviewer_ids", "policy_ref", "due_at", "submission_note"})


def _failure(code: str) -> ApplicationError:
    mapped = {
        "AUTH_ACCESS_DENIED": "RESOURCE_NOT_FOUND",
        "RESOURCE_NOT_FOUND": "RESOURCE_NOT_FOUND",
        "LICENSE_OPERATION_DENIED": "LICENSE_OPERATION_DENIED",
        "VALIDATION_FAILED": "VALIDATION_FAILED",
        "BUSINESS_REVIEW_NOT_ELIGIBLE": "BUSINESS_REVIEW_NOT_ELIGIBLE",
        "REVIEW_REVIEWER_INELIGIBLE": "REVIEW_REVIEWER_INELIGIBLE",
        "REVIEW_SUBJECT_LOCKED": "REVIEW_SUBJECT_LOCKED",
        "CONFLICT_IDEMPOTENCY": "CONFLICT_IDEMPOTENCY",
        "CONFLICT_VERSION": "CONFLICT_VERSION",
        "PROJECT_ARCHIVED": "PROJECT_ARCHIVED",
    }.get(code, "SYSTEM_UNAVAILABLE")
    return ApplicationError(mapped)


def create_requirement_review_submission_router(
    *, sessions: SessionService, origins: LoginOriginPolicy,
    submissions: RequirementReviewSubmissionService,
) -> APIRouter:
    if any(value is None for value in (sessions, origins, submissions)):
        raise ValueError("Requirement Review submission HTTP dependencies required")
    router = APIRouter()

    @router.post(
        "/api/v1/projects/{project_id}/requirements/{requirement_id}/versions/"
        "{requirement_version_id}:submit-review"
    )
    async def submit_review(
        project_id: str, requirement_id: str,
        requirement_version_id: str, request: Request,
    ) -> JSONResponse:
        token, csrf, trace, headers = await _write_security(
            request, sessions, origins)
        key = _idempotency_header(headers)
        body = await _read_json(request, headers)
        if type(body) is not dict or set(body) != _FIELDS:
            raise ApplicationError("REQUEST_MALFORMED")
        reviewers = body["reviewer_ids"]
        if (type(reviewers) is not list
                or body["policy_ref"] != "REQUIREMENT_ALL_V1"
                or body["due_at"] is not None
                or body["submission_note"] is not None):
            raise ApplicationError("VALIDATION_FAILED")
        command = SubmitRequirementVersionReview(
            token, csrf, trace,
            _canonical_uuid(project_id), _canonical_uuid(requirement_id),
            _canonical_uuid(requirement_version_id),
            tuple(_canonical_uuid(value) for value in reviewers),
            body["policy_ref"], key,
        )
        try:
            result = await run_in_threadpool(submissions.submit, command)
        except RequirementReviewSubmissionError as exc:
            raise _failure(exc.code) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if (type(result) is not SubmittedProjectReviewRef
                or result.project_id != command.project_id
                or result.subject_type != "REQ-03"
                or result.subject_id != command.requirement_id
                or result.subject_version_id != command.requirement_version_id
                or result.policy_code != command.policy_ref):
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        etag = f'"v{result.review_after_version}"'
        return JSONResponse({"data": {
            "review_id": str(result.review_id),
            "review_round_id": str(result.round_id),
            "subject_type": result.subject_type,
            "project_id": str(result.project_id),
            "requirement_id": str(result.subject_id),
            "requirement_version_id": str(result.subject_version_id),
            "policy_ref": result.policy_code,
            "reviewer_ids": [str(value) for value in result.reviewer_ids],
            "state": "IN_REVIEW", "round_no": result.round_no,
            "review_etag": etag, "submitted_by": str(result.submitted_by),
            "submitted_at": _instant(result.submitted_at),
        }, "trace_id": request.state.trace_id}, status_code=201, headers={
            "Cache-Control": "no-store", "ETag": etag,
        })

    return router
