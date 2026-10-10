"""Authenticated, session-bound keyset cursor for administrator Secret metadata."""

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
_FIELDS = {"v", "family", "scope", "session", "query", "created_at", "secret_id"}


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _query_fingerprint(page_size: int) -> str:
    return hashlib.sha256(f"page_size={page_size}".encode("ascii")).hexdigest()


class SecretListCursorCodec:
    def __init__(self, key: bytes) -> None:
        if type(key) is not bytes or len(key) != 32:
            raise ValueError("dedicated 32-byte cursor signing key is required")
        self._key = key

    def encode(self, *, session_token: bytes, page_size: int,
               created_at: datetime, secret_id: uuid.UUID) -> str:
        if (type(session_token) is not bytes or len(session_token) != 32
                or type(page_size) is not int or not 1 <= page_size <= 200
                or type(secret_id) is not uuid.UUID or secret_id.int == 0
                or not isinstance(created_at, datetime) or created_at.tzinfo is None
                or created_at.utcoffset() is None):
            raise ValueError("invalid cursor position")
        payload = {
            "v": 1, "family": "platform-secret-metadata",
            "scope": "DEPLOYMENT_ADMIN",
            "session": hashlib.sha256(session_token).hexdigest(),
            "query": _query_fingerprint(page_size),
            "created_at": created_at.astimezone(timezone.utc).isoformat(),
            "secret_id": str(secret_id),
        }
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=True).encode("ascii")
        return _b64(raw) + "." + _b64(hmac.digest(self._key, raw, "sha256"))

    def decode(self, token: str, *, session_token: bytes,
               page_size: int) -> tuple[datetime, uuid.UUID]:
        try:
            if (type(token) is not str or _TOKEN.fullmatch(token) is None
                    or type(session_token) is not bytes or len(session_token) != 32
                    or type(page_size) is not int or not 1 <= page_size <= 200):
                raise ValueError()
            encoded, signature = token.split(".")
            raw, mac = _unb64(encoded), _unb64(signature)
            if (_b64(raw) != encoded or len(mac) != 32 or _b64(mac) != signature
                    or not hmac.compare_digest(mac, hmac.digest(self._key, raw, "sha256"))):
                raise ValueError()
            payload = json.loads(raw.decode("ascii"))
            if (type(payload) is not dict or set(payload) != _FIELDS
                    or payload["v"] != 1 or payload["family"] != "platform-secret-metadata"
                    or payload["scope"] != "DEPLOYMENT_ADMIN"
                    or payload["session"] != hashlib.sha256(session_token).hexdigest()
                    or payload["query"] != _query_fingerprint(page_size)):
                raise ValueError()
            created_at = datetime.fromisoformat(payload["created_at"])
            secret_id = uuid.UUID(payload["secret_id"])
            if (created_at.tzinfo is None or created_at.utcoffset() is None
                    or created_at.utcoffset().total_seconds() != 0
                    or str(secret_id) != payload["secret_id"] or secret_id.int == 0
                    or self.encode(session_token=session_token, page_size=page_size,
                                   created_at=created_at, secret_id=secret_id) != token):
                raise ValueError()
            return created_at, secret_id
        except (TypeError, ValueError, KeyError, OverflowError, UnicodeDecodeError, json.JSONDecodeError):
            raise ApplicationError("REQUEST_MALFORMED") from None
