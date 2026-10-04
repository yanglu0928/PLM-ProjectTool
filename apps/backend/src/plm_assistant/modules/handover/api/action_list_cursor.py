"""Signed Session/Project/query-bound Handover Action keyset position."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import uuid
from datetime import datetime, timezone

from plm_assistant.modules.platform.application.errors import ApplicationError


_TOKEN = re.compile(r"[A-Za-z0-9_-]{1,768}\.[A-Za-z0-9_-]{43}\Z", re.ASCII)
_FIELDS = {"v", "family", "project_id", "session", "query", "updated_at", "action_item_id"}


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _date(value: datetime) -> str:
    if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError()
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


class HandoverActionListCursorCodec:
    def __init__(self, key: bytes) -> None:
        if type(key) is not bytes or len(key) != 32:
            raise ValueError("dedicated 32-byte Handover Action cursor key required")
        self._key = key

    def encode(self, *, session_token: bytes, project_id: uuid.UUID,
               page_size: int, updated_at: datetime,
               action_item_id: uuid.UUID) -> str:
        if (type(session_token) is not bytes or len(session_token) != 32
                or type(project_id) is not uuid.UUID or project_id.int == 0
                or type(page_size) is not int or not 1 <= page_size <= 200
                or type(action_item_id) is not uuid.UUID
                or action_item_id.int == 0):
            raise ValueError("invalid Handover Action cursor position")
        payload = {
            "v": 1, "family": "handover-action-list",
            "project_id": str(project_id),
            "session": hashlib.sha256(session_token).hexdigest(),
            "query": hashlib.sha256(
                f"page_size={page_size}".encode("ascii"),
            ).hexdigest(),
            "updated_at": _date(updated_at),
            "action_item_id": str(action_item_id),
        }
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=True).encode("ascii")
        return _b64(raw) + "." + _b64(hmac.digest(self._key, raw, "sha256"))

    def decode(self, token: str, *, session_token: bytes,
               project_id: uuid.UUID,
               page_size: int) -> tuple[datetime, uuid.UUID]:
        try:
            if (type(token) is not str or _TOKEN.fullmatch(token) is None
                    or type(session_token) is not bytes or len(session_token) != 32
                    or type(project_id) is not uuid.UUID or project_id.int == 0
                    or type(page_size) is not int or not 1 <= page_size <= 200):
                raise ValueError()
            encoded, signature = token.split(".")
            raw, mac = _unb64(encoded), _unb64(signature)
            if (_b64(raw) != encoded or len(mac) != 32 or _b64(mac) != signature
                    or not hmac.compare_digest(
                        mac, hmac.digest(self._key, raw, "sha256"))):
                raise ValueError()
            payload = json.loads(raw.decode("ascii"))
            if (type(payload) is not dict or set(payload) != _FIELDS
                    or type(payload["v"]) is not int or payload["v"] != 1
                    or payload["family"] != "handover-action-list"
                    or payload["project_id"] != str(project_id)
                    or payload["session"] != hashlib.sha256(session_token).hexdigest()
                    or payload["query"] != hashlib.sha256(
                        f"page_size={page_size}".encode("ascii"),
                    ).hexdigest()
                    or type(payload["updated_at"]) is not str
                    or type(payload["action_item_id"]) is not str):
                raise ValueError()
            updated_at = datetime.fromisoformat(
                payload["updated_at"].replace("Z", "+00:00"),
            )
            action_id = uuid.UUID(payload["action_item_id"])
            if (updated_at.tzinfo is None or updated_at.utcoffset() is None
                    or _date(updated_at) != payload["updated_at"]
                    or action_id.int == 0 or str(action_id) != payload["action_item_id"]
                    or self.encode(
                        session_token=session_token, project_id=project_id,
                        page_size=page_size, updated_at=updated_at,
                        action_item_id=action_id,
                    ) != token):
                raise ValueError()
            return updated_at, action_id
        except (TypeError, ValueError, KeyError, OverflowError,
                UnicodeDecodeError, json.JSONDecodeError):
            raise ApplicationError("REQUEST_MALFORMED") from None
