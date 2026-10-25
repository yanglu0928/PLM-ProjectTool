"""Session- and fixed-version-bound signed cursor for CAP-01 Review items."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import uuid

from plm_assistant.modules.platform.application.errors import ApplicationError


_TOKEN = re.compile(r"[A-Za-z0-9_-]{1,512}\.[A-Za-z0-9_-]{43}\Z", re.ASCII)
_FIELDS = frozenset({
    "v", "family", "review_id", "version_id", "session", "page_size", "after_ordinal",
})


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


class GlobalCapabilityFixedItemsCursorCodec:
    def __init__(self, key: bytes) -> None:
        if type(key) is not bytes or len(key) != 32:
            raise ValueError("dedicated Capability child key is required")
        self._key = hmac.digest(key, b"global-capability-review-fixed-items-v1", "sha256")

    def encode(self, *, review_id: uuid.UUID, version_id: uuid.UUID,
               session_token: bytes, page_size: int, after_ordinal: int) -> str:
        if (any(type(value) is not uuid.UUID or value.int == 0
                for value in (review_id, version_id))
                or type(session_token) is not bytes or len(session_token) != 32
                or type(page_size) is not int or not 1 <= page_size <= 50
                or type(after_ordinal) is not int or after_ordinal < 0):
            raise ValueError("invalid fixed item cursor context")
        payload = {
            "v": 1, "family": "global-capability-review-fixed-items",
            "review_id": str(review_id), "version_id": str(version_id),
            "session": hashlib.sha256(session_token).hexdigest(),
            "page_size": page_size, "after_ordinal": after_ordinal,
        }
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=True).encode("ascii")
        return _b64(raw) + "." + _b64(hmac.digest(self._key, raw, "sha256"))

    def decode(self, token: str, *, review_id: uuid.UUID, version_id: uuid.UUID,
               session_token: bytes, page_size: int) -> int:
        try:
            if type(token) is not str or _TOKEN.fullmatch(token) is None:
                raise ValueError()
            encoded, signature = token.split(".")
            raw, mac = _unb64(encoded), _unb64(signature)
            if (_b64(raw) != encoded or len(mac) != 32 or _b64(mac) != signature
                    or not hmac.compare_digest(mac, hmac.digest(self._key, raw, "sha256"))):
                raise ValueError()
            payload = json.loads(raw.decode("ascii"))
            if (type(payload) is not dict or set(payload) != _FIELDS
                    or type(payload["v"]) is not int or payload["v"] != 1
                    or payload["family"] != "global-capability-review-fixed-items"
                    or payload["review_id"] != str(review_id)
                    or payload["version_id"] != str(version_id)
                    or payload["session"] != hashlib.sha256(session_token).hexdigest()
                    or type(payload["page_size"]) is not int
                    or payload["page_size"] != page_size
                    or type(payload["after_ordinal"]) is not int
                    or payload["after_ordinal"] < 0):
                raise ValueError()
            after = payload["after_ordinal"]
            if self.encode(
                review_id=review_id, version_id=version_id,
                session_token=session_token, page_size=page_size,
                after_ordinal=after,
            ) != token:
                raise ValueError()
            return after
        except (TypeError, ValueError, KeyError, OverflowError, UnicodeDecodeError,
                json.JSONDecodeError):
            raise ApplicationError("REQUEST_MALFORMED") from None
