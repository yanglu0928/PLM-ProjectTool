"""Opt-in CAP-01 GLOBAL Review read/decision HTTP; never PROJECT fallback."""

from __future__ import annotations

import uuid
import re

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from plm_assistant.modules.auth.api.login_origin_policy import (
    LoginOriginError, LoginOriginPolicy,
)
from plm_assistant.modules.auth.api.session import (
    _idempotency_header, _session_cookie,
)
from plm_assistant.modules.auth.application.session_service import SessionService
from plm_assistant.modules.capability.api.commands import (
    _canonical_uuid, _instant, _read_json, _security,
)
from plm_assistant.modules.capability.api.read import _item, _version
from plm_assistant.modules.platform.application.errors import ApplicationError
from plm_assistant.modules.review.application.global_capability_decide import (
    DecideGlobalCapabilityReview, GlobalCapabilityReviewDecisionError,
    GlobalCapabilityReviewDecisionService,
)
from plm_assistant.modules.review.application.global_capability_read import (
    AuthorizedGlobalCapabilityReview, AuthorizedGlobalCapabilityFixedItems,
    AuthorizedGlobalCapabilityFixedVersion, GetGlobalCapabilityReview,
    GlobalCapabilityReviewReadError, GlobalCapabilityReviewReadService,
)
from plm_assistant.modules.review.api.global_capability_cursor import (
    GlobalCapabilityFixedItemsCursorCodec,
)
from plm_assistant.modules.review.application.global_persistence import (
    AppliedGlobalReviewTransitionRef,
)
from plm_assistant.modules.review.domain.round_progress import ReviewDecisionKind


_DECIDE_FIELDS = frozenset({"decision", "comment"})
_PAGE_SIZE = re.compile(r"[1-9][0-9]?\Z", re.ASCII)


def _read_failure(code: str) -> ApplicationError:
    return ApplicationError({
        "AUTH_ACCESS_DENIED": "AUTH_SESSION_EXPIRED",
        "RESOURCE_NOT_FOUND": "RESOURCE_NOT_FOUND",
        "LICENSE_OPERATION_DENIED": "LICENSE_OPERATION_DENIED",
        "VALIDATION_FAILED": "VALIDATION_FAILED",
    }.get(code, "SYSTEM_UNAVAILABLE"))


def _decision_failure(code: str) -> ApplicationError:
    return ApplicationError({
        "AUTH_ACCESS_DENIED": "RESOURCE_NOT_FOUND",
        "RESOURCE_NOT_FOUND": "RESOURCE_NOT_FOUND",
        "LICENSE_OPERATION_DENIED": "LICENSE_OPERATION_DENIED",
        "VALIDATION_FAILED": "VALIDATION_FAILED",
        "REVIEW_COMMENT_REQUIRED": "REVIEW_COMMENT_REQUIRED",
        "REVIEW_DECISION_EXISTS": "REVIEW_DECISION_EXISTS",
        "REVIEW_ROUND_STATE_INVALID": "CONFLICT_STATE",
        "CONFLICT_IDEMPOTENCY": "CONFLICT_IDEMPOTENCY",
        "CONFLICT_VERSION": "CONFLICT_VERSION",
    }.get(code, "SYSTEM_UNAVAILABLE"))


def _detail(result: AuthorizedGlobalCapabilityReview,
            review_id: uuid.UUID) -> dict[str, object]:
    if (type(result) is not AuthorizedGlobalCapabilityReview
            or result.review.review_id != review_id
            or result.review.scope != "GLOBAL"
            or result.review.project_id is not None
            or result.review.subject_type != "CAP-01"
            or result.review.policy_code != "DEPLOYMENT_ALL_V1"
            or result.fixed_round.review != result.review):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    fixed, progress = result.fixed_round, result.fixed_round.progress
    try:
        result.review.__post_init__()
        fixed.__post_init__()
        return {
            "review_id": str(review_id), "subject_type": "CAP-01",
            "baseline_id": str(result.review.subject_id),
            "baseline_version_id": str(fixed.subject_version_id),
            "policy_ref": "DEPLOYMENT_ALL_V1",
            "review_round_id": str(progress.round_id), "round_no": fixed.round_no,
            "reviewer_ids": [str(value) for value in progress.reviewer_ids],
            "decisions": [{
                "decision_id": str(item.decision_id),
                "reviewer_id": str(item.reviewer_id),
                "decision": item.kind.value, "comment": item.comment,
                "decided_at": _instant(item.decided_at),
            } for item in progress.decisions],
            "state": progress.state.value,
            "review_etag": result.review_etag,
            "round_etag": result.round_etag,
            "submitted_by": str(fixed.started_by),
            "submitted_at": _instant(progress.started_at),
        }
    except ApplicationError:
        raise
    except Exception:
        raise ApplicationError("SYSTEM_UNAVAILABLE") from None


def create_global_capability_review_router(
    *, sessions: SessionService, origins: LoginOriginPolicy,
    reads: GlobalCapabilityReviewReadService,
    decisions: GlobalCapabilityReviewDecisionService,
) -> APIRouter:
    if any(value is None for value in (sessions, origins, reads, decisions)):
        raise ValueError("GLOBAL Capability Review HTTP dependencies required")
    router = APIRouter()

    @router.get("/api/v1/global/reviews/{review_id}")
    async def get_review(review_id: str, request: Request) -> JSONResponse:
        headers = tuple(request.scope.get("headers", ()))
        try:
            origins.require_trusted_host(headers)
        except LoginOriginError:
            raise ApplicationError("AUTH_CSRF_INVALID") from None
        if request.url.query:
            raise ApplicationError("REQUEST_MALFORMED")
        token = _session_cookie(headers)
        review = _canonical_uuid(review_id)
        trace_id = uuid.UUID(request.state.trace_id)
        try:
            result = await run_in_threadpool(
                reads.get, GetGlobalCapabilityReview(token, trace_id, review),
            )
        except GlobalCapabilityReviewReadError as exc:
            raise _read_failure(exc.code) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        return JSONResponse({
            "data": _detail(result, review), "trace_id": str(trace_id),
        }, headers={"Cache-Control": "no-store", "ETag": result.review_etag})

    @router.post(
        "/api/v1/global/reviews/{review_id}/rounds/{round_id}:decide"
    )
    async def decide(review_id: str, round_id: str,
                     request: Request) -> JSONResponse:
        token, csrf = await _security(request, sessions, origins)
        headers = tuple(request.scope.get("headers", ()))
        key = _idempotency_header(headers)
        body = await _read_json(request, headers)
        if type(body) is not dict or set(body) != _DECIDE_FIELDS:
            raise ApplicationError("REQUEST_MALFORMED")
        try:
            kind = (ReviewDecisionKind(body["decision"])
                    if type(body["decision"]) is str else None)
        except ValueError:
            kind = None
        if kind is None or body["comment"] is not None and type(body["comment"]) is not str:
            raise ApplicationError("VALIDATION_FAILED")
        if kind is ReviewDecisionKind.RETURN and (
                body["comment"] is None or not body["comment"].strip()):
            raise ApplicationError("REVIEW_COMMENT_REQUIRED")
        trace_id = uuid.UUID(request.state.trace_id)
        command = DecideGlobalCapabilityReview(
            token, csrf, trace_id, _canonical_uuid(review_id),
            _canonical_uuid(round_id), kind, body["comment"], key,
        )
        try:
            result = await run_in_threadpool(decisions.decide, command)
        except GlobalCapabilityReviewDecisionError as exc:
            raise _decision_failure(exc.code) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if (type(result) is not AppliedGlobalReviewTransitionRef
                or result.review_id != command.review_id
                or result.round_id != command.round_id
                or result.actor_id.int == 0
                or result.action != "DECIDE"
                or result.decision_id is None):
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        try:
            result.__post_init__()
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        etag = f'"v{result.review_after_version}"'
        data: dict[str, object] = {
            "review_id": str(result.review_id),
            "review_round_id": str(result.round_id),
            "baseline_version_id": str(result.subject_version_id),
            "actor_id": str(result.actor_id),
            "decision": kind.value, "decision_id": str(result.decision_id),
            "state": result.state.value,
            "review_etag": etag,
            "round_etag": f'"v{result.round_after_version}"',
            "occurred_at": _instant(result.occurred_at),
            "event_id": str(result.event_id),
        }
        return JSONResponse({
            "data": data, "trace_id": str(trace_id),
        }, headers={"Cache-Control": "no-store", "ETag": etag})

    return router


def create_global_capability_fixed_content_router(
    *, origins: LoginOriginPolicy, reads: GlobalCapabilityReviewReadService,
    cursors: GlobalCapabilityFixedItemsCursorCodec,
) -> APIRouter:
    if any(value is None for value in (origins, reads, cursors)):
        raise ValueError("GLOBAL Capability fixed content dependencies required")
    router = APIRouter()

    def query(request: Request) -> tuple[bytes, uuid.UUID]:
        headers = tuple(request.scope.get("headers", ()))
        try:
            origins.require_trusted_host(headers)
        except LoginOriginError:
            raise ApplicationError("AUTH_CSRF_INVALID") from None
        return _session_cookie(headers), uuid.UUID(request.state.trace_id)

    def fixed(result: AuthorizedGlobalCapabilityFixedVersion,
              review_id: uuid.UUID) -> tuple[uuid.UUID, uuid.UUID]:
        if (type(result) is not AuthorizedGlobalCapabilityFixedVersion
                or result.review.review.review_id != review_id
                or result.review.fixed_round.subject_version_id
                != result.version.baseline_version_id
                or result.review.review.subject_id != result.version.baseline_id):
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        return result.version.baseline_id, result.version.baseline_version_id

    @router.get("/api/v1/global/reviews/{review_id}/fixed-version")
    async def get_fixed_version(review_id: str, request: Request) -> JSONResponse:
        token, trace_id = query(request)
        if request.url.query:
            raise ApplicationError("REQUEST_MALFORMED")
        identity = _canonical_uuid(review_id)
        try:
            result = await run_in_threadpool(
                reads.fixed_version, GetGlobalCapabilityReview(token, trace_id, identity),
            )
        except GlobalCapabilityReviewReadError as exc:
            raise _read_failure(exc.code) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        fixed(result, identity)
        return JSONResponse({"data": {
            "review_id": str(identity),
            "review_round_id": str(result.review.fixed_round.progress.round_id),
            "version": _version(result.version),
            "review_etag": result.review.review_etag,
        }, "trace_id": str(trace_id)}, headers={
            "Cache-Control": "no-store", "ETag": result.review.review_etag,
        })

    @router.get("/api/v1/global/reviews/{review_id}/fixed-items")
    async def get_fixed_items(review_id: str, request: Request) -> JSONResponse:
        token, trace_id = query(request)
        identity = _canonical_uuid(review_id)
        entries = list(request.query_params.multi_items())
        if (len(entries) > 2 or len({key for key, _ in entries}) != len(entries)
                or any(key not in {"page_size", "cursor"} for key, _ in entries)):
            raise ApplicationError("REQUEST_MALFORMED")
        params = dict(entries)
        raw_size = params.get("page_size", "50")
        if _PAGE_SIZE.fullmatch(raw_size) is None or int(raw_size) > 50:
            raise ApplicationError("VALIDATION_FAILED")
        size = int(raw_size)
        try:
            bound = await run_in_threadpool(
                reads.fixed_version, GetGlobalCapabilityReview(token, trace_id, identity),
            )
        except GlobalCapabilityReviewReadError as exc:
            raise _read_failure(exc.code) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        _, version_id = fixed(bound, identity)
        cursor = params.get("cursor")
        after = (cursors.decode(
            cursor, review_id=identity, version_id=version_id,
            session_token=token, page_size=size,
        ) if cursor is not None else None)
        try:
            page = await run_in_threadpool(
                reads.fixed_items, GetGlobalCapabilityReview(token, trace_id, identity),
                page_size=size, after_ordinal=after,
            )
        except GlobalCapabilityReviewReadError as exc:
            raise _read_failure(exc.code) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if (type(page) is not AuthorizedGlobalCapabilityFixedItems
                or page.review.review != bound.review.review
                or page.version != bound.version
                or page.review.review_etag != bound.review.review_etag
                or page.next_ordinal is not None and (
                    not page.items or page.next_ordinal != page.items[-1].ordinal)):
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        next_cursor = (cursors.encode(
            review_id=identity, version_id=version_id,
            session_token=token, page_size=size, after_ordinal=page.next_ordinal,
        ) if page.next_ordinal is not None else None)
        return JSONResponse({"data": {
            "review_id": str(identity),
            "review_round_id": str(page.review.fixed_round.progress.round_id),
            "baseline_version_id": str(version_id),
            "items": [_item(item) for item in page.items],
            "next_cursor": next_cursor,
            "has_more": next_cursor is not None,
            "review_etag": page.review.review_etag,
        }, "trace_id": str(trace_id)}, headers={
            "Cache-Control": "no-store", "ETag": page.review.review_etag,
        })

    return router
