"""Dedicated, scope-bound signed cursor for current project Plans."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import uuid
from datetime import datetime, timezone

from plm_assistant.modules.platform.application.errors import ApplicationError


_TOKEN = re.compile(r"[A-Za-z0-9_-]{1,512}\.[A-Za-z0-9_-]{43}\Z", re.ASCII)
_FIELDS = {"v", "family", "project_id", "session", "query", "created_at", "plan_id"}


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds").replace(
        "+00:00", "Z")


class PlanListCursorCodec:
    def __init__(self, key: bytes) -> None:
        if type(key) is not bytes or len(key) != 32:
            raise ValueError("dedicated 32-byte Plan cursor key required")
        self._key = key

    def encode(self, *, session_token: bytes, project_id: uuid.UUID,
               page_size: int, created_at: datetime, plan_id: uuid.UUID) -> str:
        if (type(session_token) is not bytes or len(session_token) != 32
                or type(project_id) is not uuid.UUID or project_id.int == 0
                or type(page_size) is not int or not 1 <= page_size <= 200
                or type(created_at) is not datetime or created_at.tzinfo is None
                or created_at.utcoffset() is None
                or type(plan_id) is not uuid.UUID or plan_id.int == 0):
            raise ValueError("invalid Plan cursor position")
        payload = {
            "v": 1, "family": "project-plan-list", "project_id": str(project_id),
            "session": hashlib.sha256(session_token).hexdigest(),
            "query": hashlib.sha256(f"page_size={page_size}".encode("ascii")).hexdigest(),
            "created_at": _timestamp(created_at), "plan_id": str(plan_id),
        }
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=True).encode("ascii")
        return _b64(raw) + "." + _b64(hmac.digest(self._key, raw, "sha256"))

    def decode(self, token: str, *, session_token: bytes, project_id: uuid.UUID,
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
                    or not hmac.compare_digest(mac, hmac.digest(self._key, raw, "sha256"))):
                raise ValueError()
            payload = json.loads(raw.decode("ascii"))
            if (type(payload) is not dict or set(payload) != _FIELDS
                    or type(payload["v"]) is not int or payload["v"] != 1
                    or payload["family"] != "project-plan-list"
                    or payload["project_id"] != str(project_id)
                    or payload["session"] != hashlib.sha256(session_token).hexdigest()
                    or payload["query"] != hashlib.sha256(
                        f"page_size={page_size}".encode("ascii")).hexdigest()
                    or type(payload["created_at"]) is not str
                    or type(payload["plan_id"]) is not str):
                raise ValueError()
            created_at = datetime.fromisoformat(payload["created_at"].replace("Z", "+00:00"))
            plan_id = uuid.UUID(payload["plan_id"])
            if (created_at.tzinfo is None or created_at.utcoffset() is None
                    or _timestamp(created_at) != payload["created_at"]
                    or plan_id.int == 0 or str(plan_id) != payload["plan_id"]
                    or self.encode(session_token=session_token, project_id=project_id,
                                   page_size=page_size, created_at=created_at,
                                   plan_id=plan_id) != token):
                raise ValueError()
            return created_at, plan_id
        except (TypeError, ValueError, KeyError, OverflowError, UnicodeDecodeError,
                json.JSONDecodeError):
            raise ApplicationError("REQUEST_MALFORMED") from None
