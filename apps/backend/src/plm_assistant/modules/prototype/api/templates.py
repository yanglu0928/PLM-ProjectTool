"""Opt-in HTTP boundary for the six frozen PrototypeTemplate operations."""

from __future__ import annotations

import re
import uuid

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.api.session import _idempotency_header
from plm_assistant.modules.auth.application.session_service import SessionService
from plm_assistant.modules.platform.api.if_match import parse_if_match
from plm_assistant.modules.platform.application.errors import ApplicationError
from plm_assistant.modules.prototype.application.create_template import (
    CreateGlobalPrototypeTemplate,
    CreateProjectPrototypeTemplate,
    PrototypeTemplateCreateError,
    PrototypeTemplateCreateService,
    PrototypeTemplateInitialView,
    TemplateArtifactRef,
)
from plm_assistant.modules.prototype.application.read_templates import (
    GlobalPrototypeTemplateReadQuery,
    ProjectPrototypeTemplateReadQuery,
    PrototypeTemplatePage,
    PrototypeTemplateReadError,
    PrototypeTemplateReadService,
    PrototypeTemplateVersionView,
)
from plm_assistant.modules.prototype.application.revise_template import (
    PrototypeTemplateReviseError,
    PrototypeTemplateReviseService,
    PrototypeTemplateRevisionView,
    ReviseGlobalPrototypeTemplate,
    ReviseProjectPrototypeTemplate,
)

from .cursors import PrototypeTemplateCursorCodec
from .packages import (
    _canonical_uuid,
    _instant,
    _page_query,
    _read_json,
    _read_security,
    _uuid_or_none,
    _write_security,
)


_ETAG = re.compile(r'"v(0|[1-9][0-9]*)"\Z', re.ASCII)
_CREATE_FIELDS = {
    "name", "layout_contract", "component_contract",
    "applicable_terminals", "artifact_refs",
}
_REVISE_FIELDS = _CREATE_FIELDS - {"name"}


def _failure(code: str) -> ApplicationError:
    return ApplicationError({
        "AUTH_ACCESS_DENIED": "RESOURCE_NOT_FOUND",
        "RESOURCE_NOT_FOUND": "RESOURCE_NOT_FOUND",
        "LICENSE_OPERATION_DENIED": "LICENSE_OPERATION_DENIED",
        "VALIDATION_FAILED": "VALIDATION_FAILED",
        "PROTOTYPE_ARTIFACT_UNAVAILABLE": "RESOURCE_NOT_FOUND",
        "CONFLICT_IDEMPOTENCY": "CONFLICT_IDEMPOTENCY",
        "VERSION_CONFLICT": "CONFLICT_VERSION",
        "PROTOTYPE_STATE_CONFLICT": "CONFLICT_STATE",
        "PROJECT_ARCHIVED": "PROJECT_ARCHIVED",
    }.get(code, "SYSTEM_UNAVAILABLE"))


def _terminals(value: object) -> tuple[str, ...]:
    if type(value) is not list or any(type(item) is not str for item in value):
        raise ApplicationError("VALIDATION_FAILED")
    return tuple(value)


def _artifacts(value: object) -> tuple[TemplateArtifactRef, ...]:
    if type(value) is not list:
        raise ApplicationError("VALIDATION_FAILED")
    result: list[TemplateArtifactRef] = []
    for item in value:
        if type(item) is not dict or set(item) != {"artifact_kind", "target_id"}:
            raise ApplicationError("REQUEST_MALFORMED")
        if type(item["artifact_kind"]) is not str:
            raise ApplicationError("VALIDATION_FAILED")
        result.append(TemplateArtifactRef(
            item["artifact_kind"], _canonical_uuid(item["target_id"]),
        ))
    return tuple(result)


def _body(value: object, *, create: bool) -> tuple[
    str | None, dict[str, object], dict[str, object], tuple[str, ...],
    tuple[TemplateArtifactRef, ...],
]:
    expected = _CREATE_FIELDS if create else _REVISE_FIELDS
    if type(value) is not dict or set(value) != expected:
        raise ApplicationError("REQUEST_MALFORMED")
    if (create and type(value["name"]) is not str
            or type(value["layout_contract"]) is not dict
            or type(value["component_contract"]) is not dict):
        raise ApplicationError("VALIDATION_FAILED")
    return (
        value["name"] if create else None,
        value["layout_contract"],
        value["component_contract"],
        _terminals(value["applicable_terminals"]),
        _artifacts(value["artifact_refs"]),
    )


def _artifact_data(values: tuple[TemplateArtifactRef, ...]) -> list[dict[str, str]]:
    if (type(values) is not tuple
            or any(type(item) is not TemplateArtifactRef for item in values)):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return [
        {"artifact_kind": item.artifact_kind, "target_id": str(item.target_id)}
        for item in values
    ]


def _common(
    *, template_id: uuid.UUID, version_id: uuid.UUID, scope: str,
    project_id: uuid.UUID | None, name: str, version_no: int,
    layout: dict[str, object], components: dict[str, object],
    terminals: tuple[str, ...], artifacts: tuple[TemplateArtifactRef, ...],
    fingerprint: str, state: str, version_state: str, etag: str,
) -> dict[str, object]:
    try:
        normalized_name = PrototypeTemplateCreateService._name(name)
        normalized_layout = PrototypeTemplateCreateService._contract(layout)
        normalized_components = PrototypeTemplateCreateService._contract(components)
        normalized_terminals = PrototypeTemplateCreateService._terminals(terminals)
        normalized_artifacts = PrototypeTemplateCreateService._artifacts(artifacts)
    except PrototypeTemplateCreateError:
        raise ApplicationError("SYSTEM_UNAVAILABLE") from None
    valid_scope = (
        scope == "GLOBAL" and project_id is None
        or scope == "PROJECT" and type(project_id) is uuid.UUID
        and project_id.int != 0
    )
    if (type(template_id) is not uuid.UUID or template_id.int == 0
            or type(version_id) is not uuid.UUID or version_id.int == 0
            or not valid_scope or type(name) is not str or not name
            or type(version_no) is not int or version_no < 1
            or type(layout) is not dict or type(components) is not dict
            or type(terminals) is not tuple
            or normalized_name != name or normalized_layout != layout
            or normalized_components != components
            or normalized_terminals != terminals
            or normalized_artifacts != artifacts
            or re.fullmatch(r"[0-9a-f]{64}", fingerprint) is None
            or state not in {"ACTIVE", "ARCHIVED", "RESTRICTED"}
            or version_state != "PUBLISHED" or _ETAG.fullmatch(etag) is None):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return {
        "prototype_template_id": str(template_id),
        "prototype_template_version_id": str(version_id),
        "scope": scope,
        "project_id": _uuid_or_none(project_id),
        "name": name,
        "state": state,
        "version_no": version_no,
        "version_state": version_state,
        "layout_contract": layout,
        "component_contract": components,
        "applicable_terminals": list(terminals),
        "artifact_refs": _artifact_data(artifacts),
        "content_fingerprint": fingerprint,
        "etag": etag,
    }


def _read_view(view: PrototypeTemplateVersionView) -> dict[str, object]:
    if type(view) is not PrototypeTemplateVersionView:
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    result = _common(
        template_id=view.prototype_template_id,
        version_id=view.prototype_template_version_id,
        scope=view.scope,
        project_id=view.project_id,
        name=view.name,
        version_no=view.version_no,
        layout=view.layout_contract,
        components=view.component_contract,
        terminals=view.applicable_terminals,
        artifacts=view.artifact_refs,
        fingerprint=view.content_fingerprint,
        state=view.template_state,
        version_state=view.version_state,
        etag=view.etag,
    )
    result.update({
        "supersedes_version_id": _uuid_or_none(view.supersedes_version_id),
        "is_current": view.is_current,
        "updated_at": _instant(view.root_updated_at),
        "created_at": _instant(view.version_created_at),
    })
    return result


def _created_view(view: PrototypeTemplateInitialView) -> dict[str, object]:
    if type(view) is not PrototypeTemplateInitialView:
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    result = _common(
        template_id=view.prototype_template_id,
        version_id=view.prototype_template_version_id,
        scope=view.scope,
        project_id=view.project_id,
        name=view.name,
        version_no=view.version_no,
        layout=view.layout_contract,
        components=view.component_contract,
        terminals=view.applicable_terminals,
        artifacts=view.artifact_refs,
        fingerprint=view.content_fingerprint,
        state=view.template_state,
        version_state=view.version_state,
        etag=view.etag,
    )
    result["created_at"] = _instant(view.created_at)
    return result


def _revised_view(view: PrototypeTemplateRevisionView) -> dict[str, object]:
    if type(view) is not PrototypeTemplateRevisionView:
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    result = _common(
        template_id=view.prototype_template_id,
        version_id=view.prototype_template_version_id,
        scope=view.scope,
        project_id=view.project_id,
        name=view.name,
        version_no=view.version_no,
        layout=view.layout_contract,
        components=view.component_contract,
        terminals=view.applicable_terminals,
        artifacts=view.artifact_refs,
        fingerprint=view.content_fingerprint,
        state=view.template_state,
        version_state=view.version_state,
        etag=view.etag,
    )
    result.update({
        "supersedes_version_id": str(view.supersedes_version_id),
        "created_at": _instant(view.created_at),
    })
    return result


def create_prototype_template_router(
    *, sessions: SessionService, origins: LoginOriginPolicy,
    reads: PrototypeTemplateReadService,
    creates: PrototypeTemplateCreateService,
    revisions: PrototypeTemplateReviseService,
    cursors: PrototypeTemplateCursorCodec,
) -> APIRouter:
    if any(value is None for value in (
            sessions, origins, reads, creates, revisions, cursors)):
        raise ValueError("PrototypeTemplate HTTP dependencies are required")
    if type(cursors) is not PrototypeTemplateCursorCodec:
        raise ValueError("dedicated PrototypeTemplate cursor codec is required")
    router = APIRouter()

    async def list_templates(
        request: Request, *, scope: str, project_id: uuid.UUID | None,
    ) -> JSONResponse:
        token, trace = await _read_security(request, sessions, origins)
        size, cursor = _page_query(request)
        position = cursors.decode(
            cursor, scope=scope, project_id=project_id,
            session_token=token, page_size=size,
        ) if cursor is not None else (None, None)
        query = (
            ProjectPrototypeTemplateReadQuery(token, trace, project_id)
            if scope == "PROJECT" else GlobalPrototypeTemplateReadQuery(token, trace)
        )
        try:
            operation = reads.list_project if scope == "PROJECT" else reads.list_global
            page = await run_in_threadpool(
                operation, query, page_size=size,
                after_updated_at=position[0], after_template_id=position[1],
            )
        except PrototypeTemplateReadError as exc:
            raise _failure(exc.code) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if (type(page) is not PrototypeTemplatePage
                or type(page.items) is not tuple or len(page.items) > size
                or any(not _in_scope(item, scope, project_id) for item in page.items)
                or type(page.has_more) is not bool
                or page.has_more != (page.next_updated_at is not None
                                     and page.next_template_id is not None)
                or page.has_more and (
                    not page.items
                    or page.next_updated_at != page.items[-1].root_updated_at
                    or page.next_template_id
                    != page.items[-1].prototype_template_id
                )):
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        next_cursor = cursors.encode(
            scope=scope, project_id=project_id, session_token=token,
            page_size=size, updated_at=page.next_updated_at,
            template_id=page.next_template_id,
        ) if page.has_more else None
        return JSONResponse({
            "data": {
                "items": [_read_view(item) for item in page.items],
                "next_cursor": next_cursor,
                "has_more": page.has_more,
            },
            "trace_id": str(trace),
        }, headers={"Cache-Control": "no-store"})

    @router.get("/api/v1/projects/{project_id}/prototype-templates")
    async def list_project(project_id: str, request: Request) -> JSONResponse:
        return await list_templates(
            request, scope="PROJECT", project_id=_canonical_uuid(project_id),
        )

    @router.get("/api/v1/global/prototype-templates")
    async def list_global(request: Request) -> JSONResponse:
        return await list_templates(request, scope="GLOBAL", project_id=None)

    async def create_template(
        request: Request, *, scope: str, project_id: uuid.UUID | None,
    ) -> JSONResponse:
        token, csrf, trace, headers = await _write_security(
            request, sessions, origins,
        )
        key = _idempotency_header(headers)
        name, layout, components, terminals, artifacts = _body(
            await _read_json(request, headers), create=True,
        )
        command = (
            CreateProjectPrototypeTemplate(
                token, csrf, trace, project_id, name, layout, components,
                terminals, artifacts, key,
            )
            if scope == "PROJECT" else CreateGlobalPrototypeTemplate(
                token, csrf, trace, name, layout, components, terminals,
                artifacts, key,
            )
        )
        try:
            operation = creates.create_project if scope == "PROJECT" else creates.create_global
            view = await run_in_threadpool(operation, command)
        except PrototypeTemplateCreateError as exc:
            raise _failure(exc.code) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if not _created_in_scope(view, scope, project_id):
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        return JSONResponse(
            {"data": _created_view(view), "trace_id": str(trace)},
            status_code=201,
            headers={"Cache-Control": "no-store", "ETag": view.etag},
        )

    @router.post("/api/v1/projects/{project_id}/prototype-templates")
    async def create_project(project_id: str, request: Request) -> JSONResponse:
        return await create_template(
            request, scope="PROJECT", project_id=_canonical_uuid(project_id),
        )

    @router.post("/api/v1/global/prototype-templates")
    async def create_global(request: Request) -> JSONResponse:
        return await create_template(request, scope="GLOBAL", project_id=None)

    async def revise_template(
        template_id: str, request: Request, *, scope: str,
        project_id: uuid.UUID | None,
    ) -> JSONResponse:
        token, csrf, trace, headers = await _write_security(
            request, sessions, origins,
        )
        expected, key = parse_if_match(headers), _idempotency_header(headers)
        _, layout, components, terminals, artifacts = _body(
            await _read_json(request, headers), create=False,
        )
        template = _canonical_uuid(template_id)
        command = (
            ReviseProjectPrototypeTemplate(
                token, csrf, trace, project_id, template, expected, layout,
                components, terminals, artifacts, key,
            )
            if scope == "PROJECT" else ReviseGlobalPrototypeTemplate(
                token, csrf, trace, template, expected, layout, components,
                terminals, artifacts, key,
            )
        )
        try:
            operation = (
                revisions.revise_project
                if scope == "PROJECT" else revisions.revise_global
            )
            view = await run_in_threadpool(operation, command)
        except PrototypeTemplateReviseError as exc:
            raise _failure(exc.code) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if (not _revised_in_scope(view, scope, project_id)
                or view.prototype_template_id != template):
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        return JSONResponse(
            {"data": _revised_view(view), "trace_id": str(trace)},
            status_code=201,
            headers={"Cache-Control": "no-store", "ETag": view.etag},
        )

    @router.post(
        "/api/v1/projects/{project_id}/prototype-templates/{template_id}:revise"
    )
    async def revise_project(
        project_id: str, template_id: str, request: Request,
    ) -> JSONResponse:
        return await revise_template(
            template_id, request, scope="PROJECT",
            project_id=_canonical_uuid(project_id),
        )

    @router.post("/api/v1/global/prototype-templates/{template_id}:revise")
    async def revise_global(template_id: str, request: Request) -> JSONResponse:
        return await revise_template(
            template_id, request, scope="GLOBAL", project_id=None,
        )

    return router


def _in_scope(
    view: object, scope: str, project_id: uuid.UUID | None,
) -> bool:
    return (
        type(view) is PrototypeTemplateVersionView
        and (
            scope == "GLOBAL" and view.scope == "GLOBAL"
            and view.project_id is None
            or scope == "PROJECT" and (
                view.scope == "GLOBAL" and view.project_id is None
                or view.scope == "PROJECT" and view.project_id == project_id
            )
        )
    )


def _created_in_scope(
    view: object, scope: str, project_id: uuid.UUID | None,
) -> bool:
    return (
        type(view) is PrototypeTemplateInitialView
        and view.scope == scope and view.project_id == project_id
    )


def _revised_in_scope(
    view: object, scope: str, project_id: uuid.UUID | None,
) -> bool:
    return (
        type(view) is PrototypeTemplateRevisionView
        and view.scope == scope and view.project_id == project_id
    )
