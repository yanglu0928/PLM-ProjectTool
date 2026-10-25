"""Signed Session/Scope/Document-bound descending Version keyset position."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import uuid

from plm_assistant.modules.platform.application.errors import ApplicationError


_TOKEN = re.compile(r"[A-Za-z0-9_-]{1,512}\.[A-Za-z0-9_-]{43}\Z", re.ASCII)
_FIELDS = {"v", "family", "scope", "project_id", "document_id", "session",
           "query", "before_version_no"}


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _valid_scope(scope: str, project_id: uuid.UUID | None) -> bool:
    return (scope == "GLOBAL" and project_id is None
            or scope == "PROJECT" and type(project_id) is uuid.UUID
            and project_id.int != 0)


class VersionListCursorCodec:
    def __init__(self, key: bytes) -> None:
        if type(key) is not bytes or len(key) != 32:
            raise ValueError("dedicated 32-byte Version cursor key is required")
        self._key = key

    def encode(self, *, session_token: bytes, scope: str,
               project_id: uuid.UUID | None, document_id: uuid.UUID,
               page_size: int, before_version_no: int) -> str:
        if (type(session_token) is not bytes or len(session_token) != 32
                or not _valid_scope(scope, project_id)
                or type(document_id) is not uuid.UUID or document_id.int == 0
                or type(page_size) is not int or not 1 <= page_size <= 200
                or type(before_version_no) is not int or before_version_no <= 0):
            raise ValueError("invalid Version cursor position")
        payload = {
            "v": 1, "family": "document-version-list", "scope": scope,
            "project_id": str(project_id) if project_id else None,
            "document_id": str(document_id),
            "session": hashlib.sha256(session_token).hexdigest(),
            "query": hashlib.sha256(f"page_size={page_size}".encode("ascii")).hexdigest(),
            "before_version_no": before_version_no,
        }
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=True).encode("ascii")
        return _b64(raw) + "." + _b64(hmac.digest(self._key, raw, "sha256"))

    def decode(self, token: str, *, session_token: bytes, scope: str,
               project_id: uuid.UUID | None, document_id: uuid.UUID,
               page_size: int) -> int:
        try:
            if (type(token) is not str or _TOKEN.fullmatch(token) is None
                    or type(session_token) is not bytes or len(session_token) != 32
                    or not _valid_scope(scope, project_id)
                    or type(document_id) is not uuid.UUID or document_id.int == 0
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
                    or payload["family"] != "document-version-list"
                    or payload["scope"] != scope
                    or payload["project_id"] != (str(project_id) if project_id else None)
                    or payload["document_id"] != str(document_id)
                    or payload["session"] != hashlib.sha256(session_token).hexdigest()
                    or payload["query"] != hashlib.sha256(
                        f"page_size={page_size}".encode("ascii")).hexdigest()
                    or type(payload["before_version_no"]) is not int
                    or payload["before_version_no"] <= 0
                    or self.encode(
                        session_token=session_token, scope=scope, project_id=project_id,
                        document_id=document_id, page_size=page_size,
                        before_version_no=payload["before_version_no"],
                    ) != token):
                raise ValueError()
            return payload["before_version_no"]
        except (TypeError, ValueError, KeyError, OverflowError, UnicodeDecodeError,
                json.JSONDecodeError):
            raise ApplicationError("REQUEST_MALFORMED") from None
