"""Dedicated signed PROJECT StructuredSolutionSpec version-list cursor."""

from __future__ import annotations

import hashlib
import hmac
import json
import uuid

from plm_assistant.modules.platform.application.errors import ApplicationError
from .reference_list_cursor import _TOKEN, _b64, _query_fingerprint, _unb64


_FIELDS = {"v", "family", "project_id", "session", "query", "before_spec_id"}


class StructuredSpecListCursorCodec:
    def __init__(self, key: bytes) -> None:
        if type(key) is not bytes or len(key) != 32:
            raise ValueError("dedicated 32-byte StructuredSpec cursor key required")
        self._key = key

    def encode(self, *, session_token: bytes, project_id: uuid.UUID,
               page_size: int, before_spec_id: uuid.UUID) -> str:
        if (type(session_token) is not bytes or len(session_token) != 32
                or type(project_id) is not uuid.UUID or project_id.int == 0
                or type(page_size) is not int or not 1 <= page_size <= 100
                or type(before_spec_id) is not uuid.UUID
                or before_spec_id.int == 0):
            raise ValueError("invalid StructuredSpec cursor position")
        payload = {
            "v": 1, "family": "project-structured-spec-version-list",
            "project_id": str(project_id),
            "session": hashlib.sha256(session_token).hexdigest(),
            "query": _query_fingerprint(page_size),
            "before_spec_id": str(before_spec_id),
        }
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=True).encode("ascii")
        return _b64(raw) + "." + _b64(hmac.digest(self._key, raw, "sha256"))

    def decode(self, token: str, *, session_token: bytes,
               project_id: uuid.UUID, page_size: int) -> uuid.UUID:
        try:
            if (type(token) is not str or _TOKEN.fullmatch(token) is None
                    or type(session_token) is not bytes
                    or len(session_token) != 32
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
                    or payload["family"]
                    != "project-structured-spec-version-list"
                    or payload["project_id"] != str(project_id)
                    or payload["session"]
                    != hashlib.sha256(session_token).hexdigest()
                    or payload["query"] != _query_fingerprint(page_size)
                    or type(payload["before_spec_id"]) is not str):
                raise ValueError()
            identity = uuid.UUID(payload["before_spec_id"])
            if (identity.int == 0 or str(identity) != payload["before_spec_id"]
                    or self.encode(
                        session_token=session_token, project_id=project_id,
                        page_size=page_size,
                        before_spec_id=identity) != token):
                raise ValueError()
            return identity
        except (TypeError, ValueError, KeyError, OverflowError,
                UnicodeDecodeError, json.JSONDecodeError):
            raise ApplicationError("REQUEST_MALFORMED") from None
