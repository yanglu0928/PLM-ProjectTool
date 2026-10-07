"""Dedicated, session-bound RequirementVersion list cursor."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import uuid

from plm_assistant.modules.platform.application.errors import ApplicationError


_TOKEN = re.compile(r"[A-Za-z0-9_-]{1,1024}\.[A-Za-z0-9_-]{43}\Z", re.ASCII)
_FIELDS = {
    "v", "family", "project", "requirement", "session", "query", "version_no",
}


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


class RequirementVersionCursorCodec:
    def __init__(self, key: bytes) -> None:
        if type(key) is not bytes or len(key) != 32:
            raise ValueError("dedicated 32-byte RequirementVersion cursor key required")
        self._key = key

    def encode(
        self, *, project_id: uuid.UUID, requirement_id: uuid.UUID,
        session_token: bytes, page_size: int, version_no: int,
    ) -> str:
        if (type(project_id) is not uuid.UUID or project_id.int == 0
                or type(requirement_id) is not uuid.UUID or requirement_id.int == 0
                or type(session_token) is not bytes or len(session_token) != 32
                or type(page_size) is not int or not 1 <= page_size <= 200
                or type(version_no) is not int or version_no < 1):
            raise ValueError("invalid RequirementVersion cursor position")
        payload = {
            "v": 1, "family": "requirement-versions",
            "project": str(project_id), "requirement": str(requirement_id),
            "session": hashlib.sha256(session_token).hexdigest(),
            "query": hashlib.sha256(
                f"page_size={page_size}".encode("ascii")).hexdigest(),
            "version_no": version_no,
        }
        raw = json.dumps(
            payload, sort_keys=True, separators=(",", ":"),
            ensure_ascii=True).encode("ascii")
        return _b64(raw) + "." + _b64(hmac.digest(self._key, raw, "sha256"))

    def decode(
        self, token: str, *, project_id: uuid.UUID,
        requirement_id: uuid.UUID, session_token: bytes, page_size: int,
    ) -> int:
        try:
            if (type(project_id) is not uuid.UUID or project_id.int == 0
                    or type(requirement_id) is not uuid.UUID or requirement_id.int == 0
                    or type(session_token) is not bytes or len(session_token) != 32
                    or type(page_size) is not int or not 1 <= page_size <= 200
                    or type(token) is not str or _TOKEN.fullmatch(token) is None):
                raise ValueError()
            encoded, signature = token.split(".")
            raw, mac = _unb64(encoded), _unb64(signature)
            if (_b64(raw) != encoded or len(mac) != 32 or _b64(mac) != signature
                    or not hmac.compare_digest(
                        mac, hmac.digest(self._key, raw, "sha256"))):
                raise ValueError()
            payload = json.loads(raw.decode("ascii"))
            if (type(payload) is not dict or set(payload) != _FIELDS
                    or payload["v"] != 1
                    or payload["family"] != "requirement-versions"
                    or payload["project"] != str(project_id)
                    or payload["requirement"] != str(requirement_id)
                    or payload["session"]
                    != hashlib.sha256(session_token).hexdigest()
                    or payload["query"] != hashlib.sha256(
                        f"page_size={page_size}".encode("ascii")).hexdigest()
                    or type(payload["version_no"]) is not int
                    or payload["version_no"] < 1
                    or self.encode(
                        project_id=project_id, requirement_id=requirement_id,
                        session_token=session_token, page_size=page_size,
                        version_no=payload["version_no"]) != token):
                raise ValueError()
            return payload["version_no"]
        except (TypeError, ValueError, KeyError, OverflowError,
                UnicodeDecodeError, json.JSONDecodeError):
            raise ApplicationError("REQUEST_MALFORMED") from None
