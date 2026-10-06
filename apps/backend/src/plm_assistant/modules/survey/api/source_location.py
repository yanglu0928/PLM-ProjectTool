"""Opt-in HTTP boundary for authorized Survey source locations."""

from __future__ import annotations

import re
import uuid

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionService
from plm_assistant.modules.platform.application.errors import ApplicationError
from plm_assistant.modules.survey.application.source_location import (
    SurveyPublicLocation, SurveySourceLocationError, SurveySourceLocationQuery,
    SurveySourceLocationService, SurveySourceLocationView, SurveySourceRecordRef,
)

from .commands import _canonical_uuid, _require_empty
from .read import _query


_ORDINAL = re.compile(r"(?:0|[1-9][0-9]?)\Z", re.ASCII)
_SOURCES = frozenset({
    "HANDOVER_ITEM", "CAPABILITY_ITEM", "TEMPLATE_DOCUMENT_VERSION", "MANUAL",
})
_STATES = frozenset({"LOCATABLE", "PARTIALLY_LOCATABLE", "UNAVAILABLE"})
_REASONS = frozenset({
    "MANUAL_SOURCE_NOT_FIXED", "NO_AUTHORIZED_LOCATION",
    "SOURCE_TARGET_UNAVAILABLE",
})


def _error(exc: SurveySourceLocationError) -> ApplicationError:
    return ApplicationError({
        "AUTH_ACCESS_DENIED": "RESOURCE_NOT_FOUND",
        "RESOURCE_NOT_FOUND": "RESOURCE_NOT_FOUND",
        "LICENSE_OPERATION_DENIED": "LICENSE_OPERATION_DENIED",
        "VALIDATION_FAILED": "VALIDATION_FAILED",
        "PROJECT_ARCHIVED": "PROJECT_ARCHIVED",
    }.get(exc.code, "SYSTEM_UNAVAILABLE"))


def _uuid(value: uuid.UUID) -> str:
    if type(value) is not uuid.UUID or value.int == 0:
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return str(value)


def _record(value: SurveySourceRecordRef, source_kind: str) -> dict[str, object]:
    if type(value) is not SurveySourceRecordRef or value.record_kind != source_kind:
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    primary, version = _uuid(value.primary_id), _uuid(value.version_id)
    if source_kind == "HANDOVER_ITEM":
        if value.item_id is None:
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        return {"record_kind": source_kind, "handover_analysis_id": primary,
                "handover_analysis_version_id": version,
                "analysis_item_id": _uuid(value.item_id)}
    if source_kind == "CAPABILITY_ITEM":
        if value.item_id is None:
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        return {"record_kind": source_kind, "baseline_id": primary,
                "baseline_version_id": version,
                "capability_item_id": _uuid(value.item_id)}
    if source_kind == "TEMPLATE_DOCUMENT_VERSION":
        if value.item_id is not None:
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        return {"record_kind": source_kind, "document_id": primary,
                "document_version_id": version}
    raise ApplicationError("SYSTEM_UNAVAILABLE")


def _location(value: SurveyPublicLocation, project_id: uuid.UUID,
              source_kind: str) -> dict[str, object]:
    if (type(value) is not SurveyPublicLocation or value.scope != "PROJECT"
            or value.project_id != project_id):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    base: dict[str, object] = {
        "location_kind": value.location_kind, "scope": value.scope,
        "project_id": _uuid(value.project_id),
    }
    if value.location_kind == "BUSINESS_RECORD" and source_kind == "HANDOVER_ITEM":
        if value.version_id is None or value.item_id is None:
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        return base | {"handover_analysis_id": _uuid(value.primary_id),
            "handover_analysis_version_id": _uuid(value.version_id),
            "analysis_item_id": _uuid(value.item_id)}
    if value.location_kind == "EVIDENCE" and source_kind == "HANDOVER_ITEM":
        if value.version_id is not None or value.item_id is not None:
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        return base | {"evidence_id": _uuid(value.primary_id)}
    if (value.location_kind == "DOCUMENT_VERSION"
            and source_kind == "TEMPLATE_DOCUMENT_VERSION"):
        if value.version_id is None or value.item_id is not None:
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        return base | {"document_id": _uuid(value.primary_id),
                       "document_version_id": _uuid(value.version_id)}
    raise ApplicationError("SYSTEM_UNAVAILABLE")


def _view(value: SurveySourceLocationView, *, project_id: uuid.UUID,
          source_ordinal: int) -> dict[str, object]:
    if (type(value) is not SurveySourceLocationView
            or value.source_kind not in _SOURCES
            or value.source_ordinal != source_ordinal
            or value.resolution_state not in _STATES
            or type(value.current_eligibility) is not bool
            or type(value.locations) is not tuple or len(value.locations) > 100
            or value.unavailable_reason is not None
            and value.unavailable_reason not in _REASONS):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    record = (None if value.record_ref is None
              else _record(value.record_ref, value.source_kind))
    locations = [_location(item, project_id, value.source_kind)
                 for item in value.locations]
    if (value.resolution_state == "LOCATABLE"
            and (record is None or not locations
                 or value.unavailable_reason is not None)
            or value.resolution_state == "PARTIALLY_LOCATABLE"
            and (record is None or locations
                 or value.unavailable_reason != "NO_AUTHORIZED_LOCATION")
            or value.resolution_state == "UNAVAILABLE"
            and (record is not None or locations or value.current_eligibility
                 or value.unavailable_reason not in (
                     "MANUAL_SOURCE_NOT_FIXED", "SOURCE_TARGET_UNAVAILABLE"))
            or value.source_kind == "MANUAL"
            and (value.resolution_state != "UNAVAILABLE"
                 or value.unavailable_reason != "MANUAL_SOURCE_NOT_FIXED")):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return {"source_kind": value.source_kind,
            "source_ordinal": value.source_ordinal,
            "resolution_state": value.resolution_state,
            "current_eligibility": value.current_eligibility,
            "record_ref": record, "locations": locations,
            "unavailable_reason": value.unavailable_reason}


def create_survey_source_location_router(
    *, sessions: SessionService, origins: LoginOriginPolicy,
    locations: SurveySourceLocationService,
) -> APIRouter:
    if any(value is None for value in (sessions, origins, locations)):
        raise ValueError("Survey source location HTTP dependencies required")
    router = APIRouter()

    @router.get(
        "/api/v1/projects/{project_id}/surveys/{survey_id}/versions/{version_id}"
        "/questions/{question_id}/sources/{source_ordinal}/location"
    )
    async def get_source_location(
        project_id: str, survey_id: str, version_id: str, question_id: str,
        source_ordinal: str, request: Request,
    ) -> JSONResponse:
        token, trace = await _query(request, sessions, origins)
        if request.url.query:
            raise ApplicationError("REQUEST_MALFORMED")
        await _require_empty(request)
        project, survey, version, question = (
            _canonical_uuid(project_id), _canonical_uuid(survey_id),
            _canonical_uuid(version_id), _canonical_uuid(question_id),
        )
        if _ORDINAL.fullmatch(source_ordinal) is None:
            raise ApplicationError("VALIDATION_FAILED")
        ordinal = int(source_ordinal)
        try:
            result = await run_in_threadpool(
                locations.locate,
                SurveySourceLocationQuery(token, trace, project),
                survey_id=survey, survey_version_id=version,
                question_id=question, source_ordinal=ordinal,
            )
        except SurveySourceLocationError as exc:
            raise _error(exc) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        return JSONResponse(
            {"data": _view(result, project_id=project, source_ordinal=ordinal),
             "trace_id": str(trace)},
            headers={"Cache-Control": "no-store"},
        )

    return router
