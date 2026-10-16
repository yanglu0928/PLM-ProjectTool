"""DeploymentAdmin-only AIModel metadata, never a route or quality clearance."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from plm_assistant.modules.ai.application.model_list_cursor import ModelListCursorCodec
from plm_assistant.modules.ai.domain.model_definition import AIModelKind
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError


class AIModelMetadataError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class AIModelMetadataQuery:
    session_token: bytes = field(repr=False)
    trace_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class AIModelMetadataView:
    model_id: uuid.UUID
    provider_id: uuid.UUID
    provider_model_key: str
    kind: AIModelKind
    revision: str
    embedding_dimension: int | None
    structured_output: bool
    context_window_tokens: int | None
    quality_profile_refs: tuple[str, ...]
    state: str
    lock_version: int
    created_at: datetime

    @property
    def etag(self) -> str:
        return f'"v{self.lock_version}"'

    @property
    def quality_status(self) -> str:
        return "NOT_EVALUATED"


@dataclass(frozen=True, slots=True)
class AIModelMetadataPage:
    items: tuple[AIModelMetadataView, ...]
    next_cursor: str | None
    has_more: bool


class AIModelReadAccessPort(Protocol):
    def authorized_admin(self, transaction: object, *, session_token: bytes,
                         now: datetime) -> uuid.UUID | None: ...


class AIModelReadLicensePort(Protocol):
    def require_valid(self, *, trace_id: uuid.UUID) -> object: ...


class AIModelMetadataRepositoryPort(Protocol):
    def get(self, transaction: object, *, model_id: uuid.UUID) -> AIModelMetadataView | None: ...

    def list_page(self, transaction: object, *, after: tuple[datetime, uuid.UUID] | None,
                  limit: int) -> list[AIModelMetadataView]: ...


class AIModelMetadataService:
    def __init__(self, *, unit_of_work: Callable[[], object],
                 access: AIModelReadAccessPort, license_guard: AIModelReadLicensePort,
                 repository: AIModelMetadataRepositoryPort,
                 cursors: ModelListCursorCodec | None = None,
                 clock: Callable[[], datetime] | None = None) -> None:
        if any(item is None for item in (unit_of_work, access, license_guard, repository)):
            raise ValueError("AI Model metadata dependencies are required")
        self._uow, self._access, self._guard = unit_of_work, access, license_guard
        self._repo, self._cursors = repository, cursors
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def get(self, query: AIModelMetadataQuery, model_id: uuid.UUID) -> AIModelMetadataView:
        self._validate(query)
        if type(model_id) is not uuid.UUID or model_id.int == 0:
            raise AIModelMetadataError("VALIDATION_FAILED")
        try:
            with self._uow() as tx:
                self._require_admin(tx, query)
            self._guard.require_valid(trace_id=query.trace_id)
            with self._uow() as tx:
                self._require_admin(tx, query)
                view = self._repo.get(tx, model_id=model_id)
                if view is None:
                    raise AIModelMetadataError("RESOURCE_NOT_FOUND")
                if type(view) is not AIModelMetadataView:
                    raise AIModelMetadataError("AI_MODEL_UNAVAILABLE")
                return view
        except AIModelMetadataError:
            raise
        except RuntimeLicenseError:
            raise AIModelMetadataError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise AIModelMetadataError("AI_MODEL_UNAVAILABLE") from None

    def list_page(self, query: AIModelMetadataQuery, *, page_size: int = 50,
                  cursor: str | None = None) -> AIModelMetadataPage:
        self._validate(query)
        if (type(page_size) is not int or not 1 <= page_size <= 200
                or cursor is not None and type(cursor) is not str):
            raise AIModelMetadataError("VALIDATION_FAILED")
        if type(self._cursors) is not ModelListCursorCodec:
            raise AIModelMetadataError("AI_MODEL_UNAVAILABLE")
        try:
            with self._uow() as tx:
                self._require_admin(tx, query)
            self._guard.require_valid(trace_id=query.trace_id)
            with self._uow() as tx:
                self._require_admin(tx, query)
                try:
                    after = (self._cursors.decode(
                        cursor, session_token=query.session_token, page_size=page_size,
                    ) if cursor is not None else None)
                except ValueError:
                    raise AIModelMetadataError("REQUEST_MALFORMED") from None
                rows = self._repo.list_page(tx, after=after, limit=page_size + 1)
                if (type(rows) is not list or len(rows) > page_size + 1
                        or any(type(row) is not AIModelMetadataView for row in rows)):
                    raise AIModelMetadataError("AI_MODEL_UNAVAILABLE")
                has_more = len(rows) > page_size
                page = rows[:page_size]
                next_cursor = (self._cursors.encode(
                    session_token=query.session_token, page_size=page_size,
                    created_at=page[-1].created_at, model_id=page[-1].model_id,
                ) if has_more else None)
                return AIModelMetadataPage(tuple(page), next_cursor, has_more)
        except AIModelMetadataError:
            raise
        except RuntimeLicenseError:
            raise AIModelMetadataError("LICENSE_OPERATION_DENIED") from None
        except ValueError:
            raise AIModelMetadataError("VALIDATION_FAILED") from None
        except Exception:
            raise AIModelMetadataError("AI_MODEL_UNAVAILABLE") from None

    @staticmethod
    def _validate(query: AIModelMetadataQuery) -> None:
        if (type(query) is not AIModelMetadataQuery
                or type(query.session_token) is not bytes or len(query.session_token) != 32
                or type(query.trace_id) is not uuid.UUID or query.trace_id.int == 0):
            raise AIModelMetadataError("VALIDATION_FAILED")

    def _require_admin(self, tx: object, query: AIModelMetadataQuery) -> uuid.UUID:
        now = self._clock()
        if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
            raise AIModelMetadataError("AI_MODEL_UNAVAILABLE")
        actor_id = self._access.authorized_admin(
            tx, session_token=query.session_token, now=now.astimezone(timezone.utc),
        )
        if type(actor_id) is not uuid.UUID or actor_id.int == 0:
            raise AIModelMetadataError("AUTH_ACCESS_DENIED")
        return actor_id
