"""Authorized read-only Prompt metadata; never returns template text."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from plm_assistant.modules.ai.application.prompt_list_cursor import PromptListCursorCodec
from plm_assistant.modules.ai.domain.prompt_identity import PromptTaskType
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError


class PromptMetadataError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class PromptMetadataQuery:
    session_token: bytes = field(repr=False)
    trace_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class PromptMetadataView:
    template_id: uuid.UUID
    task_type: PromptTaskType
    state: str
    active_version_no: int | None
    output_schema_ref: str | None
    schema_version: int | None
    rag_policy_ref: str | None
    provider_policy_ref: str | None
    system_template_hash: str | None
    user_template_hash: str | None
    lock_version: int
    created_at: datetime

    @property
    def etag(self) -> str:
        return f'"v{self.lock_version}"'


@dataclass(frozen=True, slots=True)
class PromptMetadataPage:
    items: tuple[PromptMetadataView, ...]
    next_cursor: str | None
    has_more: bool


class PromptReadAccessPort(Protocol):
    def authorized_admin(self, transaction: object, *, session_token: bytes,
                         now: datetime) -> uuid.UUID | None: ...


class PromptReadLicensePort(Protocol):
    def require_valid(self, *, trace_id: uuid.UUID) -> object: ...


class PromptMetadataRepositoryPort(Protocol):
    def get(self, transaction: object, *, template_id: uuid.UUID) -> PromptMetadataView | None: ...

    def list_page(self, transaction: object, *, after: tuple[datetime, uuid.UUID] | None,
                  limit: int) -> list[PromptMetadataView]: ...


class PromptMetadataService:
    def __init__(self, *, unit_of_work: Callable[[], object], access: PromptReadAccessPort,
                 license_guard: PromptReadLicensePort, repository: PromptMetadataRepositoryPort,
                 cursors: PromptListCursorCodec | None = None,
                 clock: Callable[[], datetime] | None = None) -> None:
        if any(item is None for item in (unit_of_work, access, license_guard, repository)):
            raise ValueError("Prompt metadata dependencies are required")
        self._uow, self._access, self._guard = unit_of_work, access, license_guard
        self._repo, self._cursors = repository, cursors
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def get(self, query: PromptMetadataQuery, template_id: uuid.UUID) -> PromptMetadataView:
        self._validate(query)
        if type(template_id) is not uuid.UUID or template_id.int == 0:
            raise PromptMetadataError("VALIDATION_FAILED")
        try:
            with self._uow() as tx:
                self._require_admin(tx, query)
            self._guard.require_valid(trace_id=query.trace_id)
            with self._uow() as tx:
                self._require_admin(tx, query)
                view = self._repo.get(tx, template_id=template_id)
                if view is None:
                    raise PromptMetadataError("RESOURCE_NOT_FOUND")
                if type(view) is not PromptMetadataView:
                    raise PromptMetadataError("AI_PROMPT_UNAVAILABLE")
                return view
        except PromptMetadataError:
            raise
        except RuntimeLicenseError:
            raise PromptMetadataError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise PromptMetadataError("AI_PROMPT_UNAVAILABLE") from None

    def list_page(self, query: PromptMetadataQuery, *, page_size: int = 50,
                  cursor: str | None = None) -> PromptMetadataPage:
        self._validate(query)
        if (type(page_size) is not int or not 1 <= page_size <= 200
                or cursor is not None and type(cursor) is not str):
            raise PromptMetadataError("VALIDATION_FAILED")
        if type(self._cursors) is not PromptListCursorCodec:
            raise PromptMetadataError("AI_PROMPT_UNAVAILABLE")
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
                    raise PromptMetadataError("REQUEST_MALFORMED") from None
                rows = self._repo.list_page(tx, after=after, limit=page_size + 1)
                if (type(rows) is not list or len(rows) > page_size + 1
                        or any(type(row) is not PromptMetadataView for row in rows)):
                    raise PromptMetadataError("AI_PROMPT_UNAVAILABLE")
                has_more = len(rows) > page_size
                page = rows[:page_size]
                next_cursor = (self._cursors.encode(
                    session_token=query.session_token, page_size=page_size,
                    created_at=page[-1].created_at, template_id=page[-1].template_id,
                ) if has_more else None)
                return PromptMetadataPage(tuple(page), next_cursor, has_more)
        except PromptMetadataError:
            raise
        except RuntimeLicenseError:
            raise PromptMetadataError("LICENSE_OPERATION_DENIED") from None
        except ValueError:
            raise PromptMetadataError("VALIDATION_FAILED") from None
        except Exception:
            raise PromptMetadataError("AI_PROMPT_UNAVAILABLE") from None

    @staticmethod
    def _validate(query: PromptMetadataQuery) -> None:
        if (type(query) is not PromptMetadataQuery
                or type(query.session_token) is not bytes or len(query.session_token) != 32
                or type(query.trace_id) is not uuid.UUID or query.trace_id.int == 0):
            raise PromptMetadataError("VALIDATION_FAILED")

    def _require_admin(self, tx: object, query: PromptMetadataQuery) -> uuid.UUID:
        now = self._clock()
        if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
            raise PromptMetadataError("AI_PROMPT_UNAVAILABLE")
        actor_id = self._access.authorized_admin(
            tx, session_token=query.session_token, now=now.astimezone(timezone.utc),
        )
        if type(actor_id) is not uuid.UUID or actor_id.int == 0:
            raise PromptMetadataError("AUTH_ACCESS_DENIED")
        return actor_id
