"""Opt-in frozen SOL_SECTION_VERSION_SUBMIT_REVIEW HTTP boundary."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from plm_assistant.modules.auth.api.login_origin_policy import (
    LoginOriginError, LoginOriginPolicy,
)
from plm_assistant.modules.auth.api.session import (
    _csrf_header, _idempotency_header, _session_cookie, _session_failure,
)
from plm_assistant.modules.auth.application.session_service import (
    SessionError, SessionService,
)
from plm_assistant.modules.platform.application.errors import ApplicationError
from plm_assistant.modules.review.application.project_persistence import (
    SubmittedProjectReviewRef,
)
from plm_assistant.modules.solution.api.outline_version_create import _body
from plm_assistant.modules.solution.api.reference_create import _uuid
from plm_assistant.modules.solution.application.section_submit_review import (
    SectionReviewSubmissionError, SectionReviewSubmissionService,
    SubmitSectionReview,
)


_FIELDS = frozenset({
    "reviewer_ids", "policy_ref", "due_at", "submission_note",
})


def _failure(error: SectionReviewSubmissionError) -> ApplicationError:
    return ApplicationError({
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
    }.get(error.code, "SYSTEM_UNAVAILABLE"))


def _response(result: SubmittedProjectReviewRef, *, project: uuid.UUID,
              section: uuid.UUID, version: uuid.UUID) -> dict[str, object]:
    if (type(result) is not SubmittedProjectReviewRef
            or result.project_id != project
            or result.subject_type != "SOL-05"
            or result.subject_id != section
            or result.subject_version_id != version
            or result.policy_code != "SOLUTION_SECTION_ALL_V1"
            or result.round_no != 1
            or result.review_after_version != 1
            or type(result.submitted_at) is not datetime
            or result.submitted_at.tzinfo is None
            or result.submitted_at.utcoffset() is None):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    result.__post_init__()
    return {
        "review_id": str(result.review_id),
        "review_round_id": str(result.round_id),
        "subject_type": "SOL-05",
        "project_id": str(project),
        "solution_section_id": str(section),
        "solution_section_version_id": str(version),
        "policy_ref": result.policy_code,
        "reviewer_ids": [str(value) for value in result.reviewer_ids],
        "state": "IN_REVIEW",
        "round_no": result.round_no,
        "review_etag": '"v1"',
        "submitted_by": str(result.submitted_by),
        "submitted_at": result.submitted_at.astimezone(
            timezone.utc).isoformat().replace("+00:00", "Z"),
    }


def create_section_review_submission_router(
        *, sessions: SessionService, origins: LoginOriginPolicy,
        submissions: SectionReviewSubmissionService) -> APIRouter:
    if any(value is None for value in (sessions, origins, submissions)):
        raise ValueError("Section Review HTTP dependencies required")
    router = APIRouter()

    @router.post(
        "/api/v1/projects/{project_id}/solution-sections/{section_id}/"
        "versions/{section_version_id}:submit-review"
    )
    async def submit_review(
            project_id: str, section_id: str, section_version_id: str,
            request: Request) -> JSONResponse:
        headers = tuple(request.scope.get("headers", ()))
        try:
            origins.require_trusted(headers)
        except LoginOriginError:
            raise ApplicationError("AUTH_CSRF_INVALID") from None
        token, csrf = _session_cookie(headers), _csrf_header(headers)
        try:
            await run_in_threadpool(
                sessions.validate, token, csrf_token=csrf,
                require_csrf=True)
        except SessionError as error:
            raise _session_failure(error) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if request.url.query:
            raise ApplicationError("REQUEST_MALFORMED")
        key = _idempotency_header(headers)
        project, section, version = (
            _uuid(project_id), _uuid(section_id), _uuid(section_version_id))
        body = await _body(request, headers)
        if type(body) is not dict or set(body) != _FIELDS:
            raise ApplicationError("REQUEST_MALFORMED")
        reviewers = body["reviewer_ids"]
        if (type(reviewers) is not list
                or body["policy_ref"] != "SOLUTION_SECTION_ALL_V1"
                or body["due_at"] is not None
                or body["submission_note"] is not None):
            raise ApplicationError("VALIDATION_FAILED")
        command = SubmitSectionReview(
            token, csrf, uuid.UUID(request.state.trace_id), project,
            section, version, tuple(_uuid(value) for value in reviewers),
            body["policy_ref"], key)
        try:
            result = await run_in_threadpool(submissions.submit, command)
        except SectionReviewSubmissionError as error:
            raise _failure(error) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        etag = f'"v{result.review_after_version}"'
        data = _response(
            result, project=project, section=section, version=version)
        if data["review_etag"] != etag:
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        return JSONResponse(
            {"data": data, "trace_id": request.state.trace_id},
            status_code=201,
            headers={"Cache-Control": "no-store", "ETag": etag},
        )

    return router
