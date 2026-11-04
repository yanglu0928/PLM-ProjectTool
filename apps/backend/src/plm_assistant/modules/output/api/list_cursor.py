"""HMAC-authenticated cursor for OutputRequest list pages."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import uuid
from datetime import datetime, timezone

from plm_assistant.modules.platform.application.errors import ApplicationError

_TOKEN = re.compile(r"[A-Za-z0-9_-]{1,1200}\.[A-Za-z0-9_-]{43}\Z", re.ASCII)
_FIELDS = {"v", "family", "project", "session", "query", "requested_at", "request_id"}


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _timestamp(value: datetime) -> str:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("cursor timestamp must be aware")
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _query_fingerprint(page_size: int) -> str:
    return hashlib.sha256(f"page_size={page_size}".encode("ascii")).hexdigest()


class OutputRequestListCursorCodec:
    def __init__(self, key: bytes) -> None:
        if type(key) is not bytes or len(key) != 32:
            raise ValueError("dedicated 32-byte OutputRequest cursor key is required")
        self._key = key

    def encode(self, *, session_token: bytes, project_id: uuid.UUID, page_size: int,
               requested_at: datetime, request_id: uuid.UUID) -> str:
        if (type(session_token) is not bytes or len(session_token) != 32
                or type(project_id) is not uuid.UUID or not project_id.int
                or type(page_size) is not int or not 1 <= page_size <= 200
                or type(request_id) is not uuid.UUID or not request_id.int):
            raise ValueError("invalid OutputRequest cursor position")
        payload = {
            "v": 1, "family": "output-request-list",
            "project": str(project_id),
            "session": hashlib.sha256(session_token).hexdigest(),
            "query": _query_fingerprint(page_size),
            "requested_at": _timestamp(requested_at),
            "request_id": str(request_id),
        }
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=True).encode("ascii")
        return _b64(raw) + "." + _b64(hmac.digest(self._key, raw, "sha256"))

    def decode(self, token: str, *, session_token: bytes, project_id: uuid.UUID,
               page_size: int) -> tuple[datetime, uuid.UUID]:
        try:
            if (type(token) is not str or _TOKEN.fullmatch(token) is None
                    or type(session_token) is not bytes or len(session_token) != 32
                    or type(project_id) is not uuid.UUID or not project_id.int
                    or type(page_size) is not int or not 1 <= page_size <= 200):
                raise ValueError()
            encoded, signature = token.split(".")
            raw, mac = _unb64(encoded), _unb64(signature)
            if (_b64(raw) != encoded or len(mac) != 32 or _b64(mac) != signature
                    or not hmac.compare_digest(mac, hmac.digest(self._key, raw, "sha256"))):
                raise ValueError()
            payload = json.loads(raw.decode("ascii"))
            if (type(payload) is not dict or set(payload) != _FIELDS
                    or type(payload["v"]) is not int or payload["v"] != 1
                    or payload["family"] != "output-request-list"
                    or payload["project"] != str(project_id)
                    or payload["session"] != hashlib.sha256(session_token).hexdigest()
                    or payload["query"] != _query_fingerprint(page_size)):
                raise ValueError()
            requested_at = datetime.fromisoformat(
                payload["requested_at"].replace("Z", "+00:00"),
            )
            if (_timestamp(requested_at) != payload["requested_at"]
                    or requested_at.utcoffset() is None):
                raise ValueError()
            request_id = uuid.UUID(payload["request_id"])
            if (not request_id.int or str(request_id) != payload["request_id"]
                    or self.encode(
                        session_token=session_token, project_id=project_id,
                        page_size=page_size, requested_at=requested_at,
                        request_id=request_id,
                    ) != token):
                raise ValueError()
            return requested_at.astimezone(timezone.utc), request_id
        except (TypeError, ValueError, KeyError, OverflowError,
                UnicodeDecodeError, json.JSONDecodeError):
            raise ApplicationError("REQUEST_MALFORMED") from None
