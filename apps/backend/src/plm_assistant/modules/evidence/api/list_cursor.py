"""Signed Session/Scope-bound Evidence `(created_at, evidence_id)` keyset."""

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
_FIELDS = {"v", "family", "scope", "project_id", "session", "query",
           "created_at", "evidence_id"}


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _valid_scope(scope: str, project_id: uuid.UUID | None) -> bool:
    return (scope == "GLOBAL" and project_id is None
            or scope == "PROJECT" and type(project_id) is uuid.UUID
            and project_id.int != 0)


def _query_fingerprint(page_size: int) -> str:
    return hashlib.sha256(f"page_size={page_size}".encode("ascii")).hexdigest()


def _utc(value: datetime) -> str:
    if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("invalid Evidence cursor timestamp")
    return (value.astimezone(timezone.utc)
            .isoformat(timespec="microseconds").replace("+00:00", "Z"))


class EvidenceListCursorCodec:
    def __init__(self, key: bytes) -> None:
        if type(key) is not bytes or len(key) != 32:
            raise ValueError("dedicated 32-byte Evidence cursor key is required")
        self._key = key

    def encode(self, *, session_token: bytes, scope: str,
               project_id: uuid.UUID | None, page_size: int,
               created_at: datetime, evidence_id: uuid.UUID) -> str:
        if (type(session_token) is not bytes or len(session_token) != 32
                or not _valid_scope(scope, project_id)
                or type(page_size) is not int or not 1 <= page_size <= 200
                or type(evidence_id) is not uuid.UUID or evidence_id.int == 0):
            raise ValueError("invalid Evidence cursor position")
        payload = {
            "v": 1, "family": "evidence-list",
            "scope": scope, "project_id": str(project_id) if project_id else None,
            "session": hashlib.sha256(session_token).hexdigest(),
            "query": _query_fingerprint(page_size),
            "created_at": _utc(created_at), "evidence_id": str(evidence_id),
        }
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=True).encode("ascii")
        return _b64(raw) + "." + _b64(hmac.digest(self._key, raw, "sha256"))

    def decode(self, token: str, *, session_token: bytes, scope: str,
               project_id: uuid.UUID | None, page_size: int) -> tuple[datetime, uuid.UUID]:
        try:
            if (type(token) is not str or _TOKEN.fullmatch(token) is None
                    or type(session_token) is not bytes or len(session_token) != 32
                    or not _valid_scope(scope, project_id)
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
                    or payload["family"] != "evidence-list"
                    or payload["scope"] != scope
                    or payload["project_id"] != (str(project_id) if project_id else None)
                    or payload["session"] != hashlib.sha256(session_token).hexdigest()
                    or payload["query"] != _query_fingerprint(page_size)
                    or type(payload["created_at"]) is not str
                    or type(payload["evidence_id"]) is not str):
                raise ValueError()
            created_at = datetime.fromisoformat(payload["created_at"].replace("Z", "+00:00"))
            evidence_id = uuid.UUID(payload["evidence_id"])
            if (evidence_id.int == 0 or str(evidence_id) != payload["evidence_id"]
                    or _utc(created_at) != payload["created_at"]
                    or self.encode(session_token=session_token, scope=scope,
                                   project_id=project_id, page_size=page_size,
                                   created_at=created_at, evidence_id=evidence_id) != token):
                raise ValueError()
            return created_at, evidence_id
        except (TypeError, ValueError, KeyError, OverflowError, UnicodeDecodeError,
                json.JSONDecodeError):
            raise ApplicationError("REQUEST_MALFORMED") from None
