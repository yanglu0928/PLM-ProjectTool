"""Dedicated signed raw-root cursor for project GLOBAL candidate discovery."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import uuid


_TOKEN = re.compile(r"[A-Za-z0-9_-]{1,512}\.[A-Za-z0-9_-]{43}\Z", re.ASCII)
_FIELDS = {"v", "family", "project_id", "session", "page_size", "after_root_id"}


class GlobalReferenceCandidateCursorError(RuntimeError):
    pass


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


class GlobalReferenceCandidateCursorCodec:
    def __init__(self, key: bytes) -> None:
        if type(key) is not bytes or len(key) != 32:
            raise ValueError("dedicated 32-byte GLOBAL candidate cursor key required")
        self._key = key

    def encode(self, *, session_token: bytes, project_id: uuid.UUID,
               page_size: int, after_root_id: uuid.UUID) -> str:
        if (type(session_token) is not bytes or len(session_token) != 32
                or type(project_id) is not uuid.UUID or project_id.int == 0
                or type(page_size) is not int or not 1 <= page_size <= 100
                or type(after_root_id) is not uuid.UUID or after_root_id.int == 0):
            raise ValueError("invalid GLOBAL candidate cursor position")
        payload = {
            "v": 1, "family": "project-global-reference-candidate-list",
            "project_id": str(project_id),
            "session": hashlib.sha256(session_token).hexdigest(),
            "page_size": page_size, "after_root_id": str(after_root_id),
        }
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=True).encode("ascii")
        return _b64(raw) + "." + _b64(hmac.digest(self._key, raw, "sha256"))

    def decode(self, token: str, *, session_token: bytes,
               project_id: uuid.UUID, page_size: int) -> uuid.UUID:
        try:
            if (type(token) is not str or _TOKEN.fullmatch(token) is None
                    or type(session_token) is not bytes or len(session_token) != 32
                    or type(project_id) is not uuid.UUID or project_id.int == 0
                    or type(page_size) is not int or not 1 <= page_size <= 100):
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
                    or payload["family"] != "project-global-reference-candidate-list"
                    or payload["project_id"] != str(project_id)
                    or payload["session"] != hashlib.sha256(session_token).hexdigest()
                    or type(payload["page_size"]) is not int
                    or payload["page_size"] != page_size
                    or type(payload["after_root_id"]) is not str):
                raise ValueError()
            after = uuid.UUID(payload["after_root_id"])
            if (after.int == 0 or str(after) != payload["after_root_id"]
                    or self.encode(
                        session_token=session_token, project_id=project_id,
                        page_size=page_size, after_root_id=after) != token):
                raise ValueError()
            return after
        except (ValueError, TypeError, KeyError, UnicodeDecodeError,
                json.JSONDecodeError, OverflowError):
            raise GlobalReferenceCandidateCursorError() from None
