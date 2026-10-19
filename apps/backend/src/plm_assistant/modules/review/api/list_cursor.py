"""Encrypted REVIEW_LIST position; dedicated key, no authority or plaintext IDs."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from uuid import UUID

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from plm_assistant.modules.platform.application.errors import ApplicationError
from plm_assistant.modules.review.application.list_contract import (
    REVIEW_LIST_VIEWS, ReviewListPosition,
)


_TOKEN = re.compile(r"r1\.[A-Za-z0-9_-]{1,1536}\Z", re.ASCII)
_FAMILY = "plm-review-list-aesgcm-v1"


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True).encode("ascii")


def _binding(*, session_token: bytes, project_id: UUID,
             view: str, page_size: int) -> bytes:
    if (type(session_token) is not bytes or len(session_token) != 32
            or type(project_id) is not UUID or project_id.int == 0
            or type(view) is not str or view not in REVIEW_LIST_VIEWS
            or type(page_size) is not int or not 1 <= page_size <= 200):
        raise ValueError("invalid Review-list cursor binding")
    return _json({
        "family": _FAMILY,
        "v": 1,
        "session": hashlib.sha256(session_token).hexdigest(),
        "project_id": str(project_id),
        "view": view,
        "page_size": page_size,
    })


def _payload(position: ReviewListPosition) -> bytes:
    if type(position) is not ReviewListPosition:
        raise ValueError("invalid Review-list cursor position")
    position.__post_init__()
    return _json({
        "v": 1,
        "created_at": position.created_at.astimezone(timezone.utc).isoformat(
            timespec="microseconds").replace("+00:00", "Z"),
        "review_id": str(position.review_id),
    })


class ReviewListCursorCodec:
    def __init__(self, key: bytes) -> None:
        if type(key) is not bytes or len(key) != 32:
            raise ValueError("dedicated 32-byte Review-list cursor key is required")
        self._aes = AESGCM(key)

    def encode(self, *, session_token: bytes, project_id: UUID,
               view: str, page_size: int,
               position: ReviewListPosition) -> str:
        aad = _binding(
            session_token=session_token, project_id=project_id,
            view=view, page_size=page_size,
        )
        nonce = os.urandom(12)
        encrypted = self._aes.encrypt(nonce, _payload(position), aad)
        return "r1." + _b64(nonce + encrypted)

    def decode(self, token: str, *, session_token: bytes, project_id: UUID,
               view: str, page_size: int) -> ReviewListPosition:
        try:
            aad = _binding(
                session_token=session_token, project_id=project_id,
                view=view, page_size=page_size,
            )
            if type(token) is not str or _TOKEN.fullmatch(token) is None:
                raise ValueError()
            encoded = token[3:]
            packed = base64.urlsafe_b64decode(
                encoded + "=" * (-len(encoded) % 4))
            if len(packed) < 29 or _b64(packed) != encoded:
                raise ValueError()
            raw = self._aes.decrypt(packed[:12], packed[12:], aad)
            value = json.loads(raw.decode("ascii"))
            if (type(value) is not dict
                    or set(value) != {"v", "created_at", "review_id"}
                    or type(value["v"]) is not int or value["v"] != 1
                    or type(value["created_at"]) is not str
                    or not value["created_at"].endswith("Z")
                    or type(value["review_id"]) is not str):
                raise ValueError()
            position = ReviewListPosition(
                datetime.fromisoformat(value["created_at"][:-1] + "+00:00"),
                UUID(value["review_id"]),
            )
            if _payload(position) != raw:
                raise ValueError()
            return position
        except Exception:
            raise ApplicationError("REQUEST_MALFORMED") from None
