"""Opaque encrypted AI Task list cursor with a dedicated protocol family."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import uuid
from datetime import datetime, timezone

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from plm_assistant.modules.ai.application.task_read import (
    AITaskReadError,
    ListAITasks,
    _position,
)


_TOKEN = re.compile(r"ait1\.[A-Za-z0-9_-]{1,1536}\Z", re.ASCII)
_FAMILY = "plm-ai-task-list-aesgcm-v1"


def _json(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=True, sort_keys=True, separators=(",", ":"),
    ).encode("ascii")


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _aad(query: ListAITasks) -> bytes:
    if type(query) is not ListAITasks:
        raise ValueError("invalid AI Task cursor binding")
    query.__post_init__()
    return _json({
        "family": _FAMILY,
        "v": 1,
        "session": hashlib.sha256(query.session_token).hexdigest(),
        "project_id": str(query.project_id),
        "page_size": query.page_size,
    })


def _payload(before: tuple[datetime, uuid.UUID]) -> bytes:
    if not _position(before):
        raise ValueError("invalid AI Task cursor position")
    return _json({
        "v": 1,
        "requested_at": before[0].astimezone(timezone.utc).isoformat(
            timespec="microseconds",
        ),
        "ai_task_id": str(before[1]),
    })


class AITaskListCursorCodec:
    def __init__(self, key: bytes) -> None:
        if type(key) is not bytes or len(key) != 32:
            raise ValueError("dedicated 32-byte AI read cursor key required")
        self._aes = AESGCM(key)

    def encode(self, *, query: ListAITasks,
               before: tuple[datetime, uuid.UUID]) -> str:
        aad, payload = _aad(query), _payload(before)
        nonce = os.urandom(12)
        return "ait1." + _b64(nonce + self._aes.encrypt(nonce, payload, aad))

    def decode(self, token: str, *, query: ListAITasks) -> tuple[datetime, uuid.UUID]:
        try:
            aad = _aad(query)
            if type(token) is not str or _TOKEN.fullmatch(token) is None:
                raise ValueError()
            encoded = token[5:]
            packed = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
            if len(packed) < 29 or _b64(packed) != encoded:
                raise ValueError()
            raw = self._aes.decrypt(packed[:12], packed[12:], aad)
            value = json.loads(raw.decode("ascii"))
            if (type(value) is not dict
                    or set(value) != {"v", "requested_at", "ai_task_id"}
                    or type(value["v"]) is not int or value["v"] != 1):
                raise ValueError()
            before = (
                datetime.fromisoformat(value["requested_at"]),
                uuid.UUID(value["ai_task_id"]),
            )
            if (before[0].utcoffset() != timezone.utc.utcoffset(before[0])
                    or _payload(before) != raw):
                raise ValueError()
            return before
        except Exception:
            raise AITaskReadError("REQUEST_MALFORMED") from None
