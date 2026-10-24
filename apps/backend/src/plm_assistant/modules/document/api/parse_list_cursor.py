"""Dedicated signed, Session/version-bound ParseRecord keyset cursor."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import uuid
from datetime import datetime, timezone

from plm_assistant.modules.platform.application.errors import ApplicationError


_TOKEN = re.compile(r"[A-Za-z0-9_-]{1,1024}\.[A-Za-z0-9_-]{43}\Z", re.ASCII)
_FIELDS = {"v", "family", "scope", "project_id", "document_id",
           "document_version_id", "session", "page_size", "created_at",
           "parse_record_id"}


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


class ParseListCursorCodec:
    def __init__(self, key: bytes) -> None:
        if type(key) is not bytes or len(key) != 32:
            raise ValueError("dedicated 32-byte Parse cursor key is required")
        self._key = key

    def encode(self, *, session_token: bytes, scope: str,
               project_id: uuid.UUID | None, document_id: uuid.UUID,
               document_version_id: uuid.UUID, page_size: int,
               before: tuple[datetime, uuid.UUID]) -> str:
        if (type(session_token) is not bytes or len(session_token) != 32
                or not (scope == "GLOBAL" and project_id is None
                        or scope == "PROJECT" and type(project_id) is uuid.UUID
                        and project_id.int != 0)
                or type(document_id) is not uuid.UUID or document_id.int == 0
                or type(document_version_id) is not uuid.UUID
                or document_version_id.int == 0
                or type(page_size) is not int or not 1 <= page_size <= 200
                or type(before) is not tuple or len(before) != 2
                or type(before[0]) is not datetime or before[0].tzinfo is None
                or before[0].utcoffset() is None
                or type(before[1]) is not uuid.UUID or before[1].int == 0):
            raise ValueError("invalid Parse cursor position")
        created_at = before[0].astimezone(timezone.utc).isoformat(timespec="microseconds")
        payload = {
            "v": 1, "family": "document-parse-list", "scope": scope,
            "project_id": str(project_id) if project_id else None,
            "document_id": str(document_id),
            "document_version_id": str(document_version_id),
            "session": hashlib.sha256(session_token).hexdigest(),
            "page_size": page_size, "created_at": created_at,
            "parse_record_id": str(before[1]),
        }
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=True).encode("ascii")
        return _b64(raw) + "." + _b64(hmac.digest(self._key, raw, "sha256"))

    def decode(self, token: str, *, session_token: bytes, scope: str,
               project_id: uuid.UUID | None, document_id: uuid.UUID,
               document_version_id: uuid.UUID,
               page_size: int) -> tuple[datetime, uuid.UUID]:
        try:
            if type(token) is not str or _TOKEN.fullmatch(token) is None:
                raise ValueError()
            encoded, signature = token.split(".")
            raw, mac = _unb64(encoded), _unb64(signature)
            if (_b64(raw) != encoded or len(mac) != 32 or _b64(mac) != signature
                    or not hmac.compare_digest(mac, hmac.digest(self._key, raw, "sha256"))):
                raise ValueError()
            payload = json.loads(raw.decode("ascii"))
            if type(payload) is not dict or set(payload) != _FIELDS:
                raise ValueError()
            created_at = datetime.fromisoformat(payload["created_at"])
            record_id = uuid.UUID(payload["parse_record_id"])
            before = (created_at, record_id)
            if (type(payload["v"]) is not int or payload["v"] != 1
                    or payload["family"] != "document-parse-list"
                    or payload["scope"] != scope
                    or payload["project_id"] != (str(project_id) if project_id else None)
                    or payload["document_id"] != str(document_id)
                    or payload["document_version_id"] != str(document_version_id)
                    or payload["session"] != hashlib.sha256(session_token).hexdigest()
                    or type(payload["page_size"]) is not int
                    or payload["page_size"] != page_size
                    or self.encode(
                        session_token=session_token, scope=scope, project_id=project_id,
                        document_id=document_id, document_version_id=document_version_id,
                        page_size=page_size, before=before,
                    ) != token):
                raise ValueError()
            return before
        except (TypeError, ValueError, KeyError, OverflowError, UnicodeDecodeError,
                json.JSONDecodeError):
            raise ApplicationError("REQUEST_MALFORMED") from None
