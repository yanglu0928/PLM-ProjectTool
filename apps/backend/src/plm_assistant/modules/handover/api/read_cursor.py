"""Dedicated signed positions for Handover Analysis read families."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import uuid
from datetime import datetime, timezone

from plm_assistant.modules.platform.application.errors import ApplicationError


_TOKEN = re.compile(r"[A-Za-z0-9_-]{1,1024}\.[A-Za-z0-9_-]{43}\Z", re.ASCII)


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _query(page_size: int) -> str:
    return hashlib.sha256(f"page_size={page_size}".encode("ascii")).hexdigest()


def _instant(value: datetime) -> str:
    if (type(value) is not datetime or value.tzinfo is None
            or value.utcoffset() is None):
        raise ValueError()
    return value.astimezone(timezone.utc).isoformat(
        timespec="microseconds",
    ).replace("+00:00", "Z")


def _common(token: str, key: bytes) -> dict[str, object]:
    if type(token) is not str or _TOKEN.fullmatch(token) is None:
        raise ValueError()
    encoded, signature = token.split(".")
    raw, mac = _unb64(encoded), _unb64(signature)
    if (_b64(raw) != encoded or len(mac) != 32 or _b64(mac) != signature
            or not hmac.compare_digest(mac, hmac.digest(key, raw, "sha256"))):
        raise ValueError()
    payload = json.loads(raw.decode("ascii"))
    if type(payload) is not dict:
        raise ValueError()
    return payload


def _uuid(value: object) -> uuid.UUID:
    if type(value) is not str:
        raise ValueError()
    parsed = uuid.UUID(value)
    if parsed.int == 0 or str(parsed) != value:
        raise ValueError()
    return parsed


def _base(*, project_id: uuid.UUID, session_token: bytes,
          page_size: int) -> dict[str, object]:
    if (type(project_id) is not uuid.UUID or project_id.int == 0
            or type(session_token) is not bytes or len(session_token) != 32
            or type(page_size) is not int or not 1 <= page_size <= 200):
        raise ValueError()
    return {
        "v": 1, "project": str(project_id),
        "session": hashlib.sha256(session_token).hexdigest(),
        "query": _query(page_size),
    }


def _encode(payload: dict[str, object], key: bytes) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                     ensure_ascii=True).encode("ascii")
    return _b64(raw) + "." + _b64(hmac.digest(key, raw, "sha256"))


def _bound(payload: dict[str, object], *, family: str, project_id: uuid.UUID,
           session_token: bytes, page_size: int, fields: set[str]) -> None:
    expected = _base(
        project_id=project_id, session_token=session_token, page_size=page_size,
    )
    if (set(payload) != fields or payload.get("family") != family
            or payload.get("v") != expected["v"]
            or payload.get("project") != expected["project"]
            or payload.get("session") != expected["session"]
            or payload.get("query") != expected["query"]):
        raise ValueError()


class HandoverAnalysisCursorCodec:
    _FIELDS = {"v", "family", "project", "session", "query", "updated_at",
               "analysis_id"}

    def __init__(self, key: bytes) -> None:
        if type(key) is not bytes or len(key) != 32:
            raise ValueError("dedicated 32-byte Handover analysis cursor key required")
        self._key = key

    def encode(self, *, project_id: uuid.UUID, session_token: bytes,
               page_size: int, updated_at: datetime,
               analysis_id: uuid.UUID) -> str:
        payload = _base(
            project_id=project_id, session_token=session_token, page_size=page_size,
        )
        if type(analysis_id) is not uuid.UUID or analysis_id.int == 0:
            raise ValueError("invalid Handover analysis cursor position")
        payload.update({
            "family": "handover-analyses", "updated_at": _instant(updated_at),
            "analysis_id": str(analysis_id),
        })
        return _encode(payload, self._key)

    def decode(self, token: str, *, project_id: uuid.UUID,
               session_token: bytes, page_size: int) -> tuple[datetime, uuid.UUID]:
        try:
            payload = _common(token, self._key)
            _bound(payload, family="handover-analyses", project_id=project_id,
                   session_token=session_token, page_size=page_size,
                   fields=self._FIELDS)
            if type(payload["updated_at"]) is not str:
                raise ValueError()
            updated_at = datetime.fromisoformat(
                payload["updated_at"].replace("Z", "+00:00")
            )
            analysis_id = _uuid(payload["analysis_id"])
            if self.encode(
                project_id=project_id, session_token=session_token,
                page_size=page_size, updated_at=updated_at,
                analysis_id=analysis_id,
            ) != token:
                raise ValueError()
            return updated_at, analysis_id
        except (TypeError, ValueError, KeyError, OverflowError,
                UnicodeDecodeError, json.JSONDecodeError):
            raise ApplicationError("REQUEST_MALFORMED") from None


class HandoverVersionCursorCodec:
    _FIELDS = {"v", "family", "project", "analysis", "session", "query",
               "position"}

    def __init__(self, key: bytes) -> None:
        if type(key) is not bytes or len(key) != 32:
            raise ValueError("dedicated 32-byte Handover version cursor key required")
        self._key = key

    def encode(self, *, project_id: uuid.UUID, analysis_id: uuid.UUID,
               session_token: bytes, page_size: int, position: int) -> str:
        payload = _base(
            project_id=project_id, session_token=session_token, page_size=page_size,
        )
        if (type(analysis_id) is not uuid.UUID or analysis_id.int == 0
                or type(position) is not int or position <= 0):
            raise ValueError("invalid Handover version cursor position")
        payload.update({
            "family": "handover-versions", "analysis": str(analysis_id),
            "position": position,
        })
        return _encode(payload, self._key)

    def decode(self, token: str, *, project_id: uuid.UUID,
               analysis_id: uuid.UUID, session_token: bytes,
               page_size: int) -> int:
        try:
            payload = _common(token, self._key)
            _bound(payload, family="handover-versions", project_id=project_id,
                   session_token=session_token, page_size=page_size,
                   fields=self._FIELDS)
            if (_uuid(payload["analysis"]) != analysis_id
                    or type(payload["position"]) is not int
                    or payload["position"] <= 0):
                raise ValueError()
            if self.encode(
                project_id=project_id, analysis_id=analysis_id,
                session_token=session_token, page_size=page_size,
                position=payload["position"],
            ) != token:
                raise ValueError()
            return payload["position"]
        except (TypeError, ValueError, KeyError, OverflowError,
                UnicodeDecodeError, json.JSONDecodeError):
            raise ApplicationError("REQUEST_MALFORMED") from None


class HandoverItemCursorCodec:
    _FIELDS = {"v", "family", "project", "analysis", "version", "session",
               "query", "position"}

    def __init__(self, key: bytes) -> None:
        if type(key) is not bytes or len(key) != 32:
            raise ValueError("dedicated 32-byte Handover item cursor key required")
        self._key = key

    def encode(self, *, project_id: uuid.UUID, analysis_id: uuid.UUID,
               version_id: uuid.UUID, session_token: bytes, page_size: int,
               position: int) -> str:
        payload = _base(
            project_id=project_id, session_token=session_token, page_size=page_size,
        )
        if (any(type(value) is not uuid.UUID or value.int == 0
                for value in (analysis_id, version_id))
                or type(position) is not int or position < 0):
            raise ValueError("invalid Handover item cursor position")
        payload.update({
            "family": "handover-items", "analysis": str(analysis_id),
            "version": str(version_id), "position": position,
        })
        return _encode(payload, self._key)

    def decode(self, token: str, *, project_id: uuid.UUID,
               analysis_id: uuid.UUID, version_id: uuid.UUID,
               session_token: bytes, page_size: int) -> int:
        try:
            payload = _common(token, self._key)
            _bound(payload, family="handover-items", project_id=project_id,
                   session_token=session_token, page_size=page_size,
                   fields=self._FIELDS)
            if (_uuid(payload["analysis"]) != analysis_id
                    or _uuid(payload["version"]) != version_id
                    or type(payload["position"]) is not int
                    or payload["position"] < 0):
                raise ValueError()
            if self.encode(
                project_id=project_id, analysis_id=analysis_id,
                version_id=version_id, session_token=session_token,
                page_size=page_size, position=payload["position"],
            ) != token:
                raise ValueError()
            return payload["position"]
        except (TypeError, ValueError, KeyError, OverflowError,
                UnicodeDecodeError, json.JSONDecodeError):
            raise ApplicationError("REQUEST_MALFORMED") from None
