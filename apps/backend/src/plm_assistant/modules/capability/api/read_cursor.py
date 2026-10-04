"""Dedicated signed positions for Capability baseline and child listings."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import uuid

from plm_assistant.modules.platform.application.errors import ApplicationError


_TOKEN = re.compile(r"[A-Za-z0-9_-]{1,512}\.[A-Za-z0-9_-]{43}\Z", re.ASCII)


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _query(page_size: int, visibility: str) -> str:
    return hashlib.sha256(
        f"page_size={page_size}&visibility={visibility}".encode("ascii")
    ).hexdigest()


def _common(token: str, key: bytes) -> tuple[bytes, dict[str, object]]:
    if type(token) is not str or _TOKEN.fullmatch(token) is None:
        raise ValueError()
    encoded, signature = token.split(".")
    raw, mac = _unb64(encoded), _unb64(signature)
    if (_b64(raw) != encoded or len(mac) != 32 or _b64(mac) != signature
            or not hmac.compare_digest(mac, hmac.digest(key, raw, "sha256"))):
        raise ValueError()
    payload = json.loads(raw.decode("ascii"))
    if type(payload) is not dict:
        raise ValueError()
    return raw, payload


class CapabilityBaselineCursorCodec:
    _FIELDS = {"v", "family", "session", "query", "baseline_id"}

    def __init__(self, key: bytes) -> None:
        if type(key) is not bytes or len(key) != 32:
            raise ValueError("dedicated 32-byte Capability baseline cursor key is required")
        self._key = key

    def encode(self, *, session_token: bytes, page_size: int, visibility: str,
               baseline_id: uuid.UUID) -> str:
        if (type(session_token) is not bytes or len(session_token) != 32
                or type(page_size) is not int or not 1 <= page_size <= 200
                or visibility not in {"ADMIN_HISTORY", "CURRENT_APPROVED"}
                or type(baseline_id) is not uuid.UUID or baseline_id.int == 0):
            raise ValueError("invalid Capability baseline cursor position")
        payload = {
            "v": 1, "family": "capability-baselines",
            "session": hashlib.sha256(session_token).hexdigest(),
            "query": _query(page_size, visibility), "baseline_id": str(baseline_id),
        }
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=True).encode("ascii")
        return _b64(raw) + "." + _b64(hmac.digest(self._key, raw, "sha256"))

    def decode(self, token: str, *, session_token: bytes, page_size: int,
               visibility: str) -> uuid.UUID:
        try:
            if (type(session_token) is not bytes or len(session_token) != 32
                    or type(page_size) is not int or not 1 <= page_size <= 200
                    or visibility not in {"ADMIN_HISTORY", "CURRENT_APPROVED"}):
                raise ValueError()
            _, payload = _common(token, self._key)
            if (set(payload) != self._FIELDS
                    or type(payload["v"]) is not int or payload["v"] != 1
                    or payload["family"] != "capability-baselines"
                    or payload["session"] != hashlib.sha256(session_token).hexdigest()
                    or payload["query"] != _query(page_size, visibility)
                    or type(payload["baseline_id"]) is not str):
                raise ValueError()
            position = uuid.UUID(payload["baseline_id"])
            if (position.int == 0 or str(position) != payload["baseline_id"]
                    or self.encode(session_token=session_token, page_size=page_size,
                                   visibility=visibility, baseline_id=position) != token):
                raise ValueError()
            return position
        except (TypeError, ValueError, KeyError, OverflowError, UnicodeDecodeError,
                json.JSONDecodeError):
            raise ApplicationError("REQUEST_MALFORMED") from None


class CapabilityChildCursorCodec:
    _FIELDS = {"v", "family", "scope", "session", "query", "position"}

    def __init__(self, key: bytes) -> None:
        if type(key) is not bytes or len(key) != 32:
            raise ValueError("dedicated 32-byte Capability child cursor key is required")
        self._key = key

    def encode(self, *, family: str, scope_id: uuid.UUID, session_token: bytes,
               page_size: int, visibility: str, position: int) -> str:
        if (family not in {"capability-versions", "capability-items"}
                or type(scope_id) is not uuid.UUID or scope_id.int == 0
                or type(session_token) is not bytes or len(session_token) != 32
                or type(page_size) is not int or not 1 <= page_size <= 200
                or visibility not in {"ADMIN_HISTORY", "CURRENT_APPROVED"}
                or type(position) is not int or position < 0
                or (family == "capability-versions" and position == 0)):
            raise ValueError("invalid Capability child cursor position")
        payload = {
            "v": 1, "family": family, "scope": str(scope_id),
            "session": hashlib.sha256(session_token).hexdigest(),
            "query": _query(page_size, visibility), "position": position,
        }
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=True).encode("ascii")
        return _b64(raw) + "." + _b64(hmac.digest(self._key, raw, "sha256"))

    def decode(self, token: str, *, family: str, scope_id: uuid.UUID,
               session_token: bytes, page_size: int, visibility: str) -> int:
        try:
            if (family not in {"capability-versions", "capability-items"}
                    or type(scope_id) is not uuid.UUID or scope_id.int == 0
                    or type(session_token) is not bytes or len(session_token) != 32
                    or type(page_size) is not int or not 1 <= page_size <= 200
                    or visibility not in {"ADMIN_HISTORY", "CURRENT_APPROVED"}):
                raise ValueError()
            _, payload = _common(token, self._key)
            if (set(payload) != self._FIELDS
                    or type(payload["v"]) is not int or payload["v"] != 1
                    or payload["family"] != family or payload["scope"] != str(scope_id)
                    or payload["session"] != hashlib.sha256(session_token).hexdigest()
                    or payload["query"] != _query(page_size, visibility)
                    or type(payload["position"]) is not int
                    or payload["position"] < 0
                    or (family == "capability-versions" and payload["position"] == 0)):
                raise ValueError()
            if self.encode(
                family=family, scope_id=scope_id, session_token=session_token,
                page_size=page_size, visibility=visibility,
                position=payload["position"],
            ) != token:
                raise ValueError()
            return payload["position"]
        except (TypeError, ValueError, KeyError, OverflowError, UnicodeDecodeError,
                json.JSONDecodeError):
            raise ApplicationError("REQUEST_MALFORMED") from None
