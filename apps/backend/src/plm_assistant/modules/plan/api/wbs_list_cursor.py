"""Session-, project- and fixed-version-bound signed WBS page cursor."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import uuid

from plm_assistant.modules.platform.application.errors import ApplicationError


_TOKEN = re.compile(r"[A-Za-z0-9_-]{1,512}\.[A-Za-z0-9_-]{43}\Z", re.ASCII)
_FIELDS = {
    "v", "family", "project_id", "plan_id", "plan_version_id", "session",
    "page_size", "ordinal", "wbs_item_id",
}


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


class PlanVersionWbsCursorCodec:
    def __init__(self, key: bytes) -> None:
        if type(key) is not bytes or len(key) != 32:
            raise ValueError("dedicated Plan cursor key required")
        self._key = key

    def encode(self, *, session_token: bytes, project_id: uuid.UUID,
               plan_id: uuid.UUID, plan_version_id: uuid.UUID,
               page_size: int, ordinal: int, wbs_item_id: uuid.UUID) -> str:
        if (type(session_token) is not bytes or len(session_token) != 32
                or any(type(value) is not uuid.UUID or value.int == 0 for value in (
                    project_id, plan_id, plan_version_id, wbs_item_id))
                or type(page_size) is not int or not 1 <= page_size <= 200
                or type(ordinal) is not int or ordinal < 1):
            raise ValueError("invalid PlanVersion WBS cursor position")
        payload = {
            "v": 1, "family": "plan-version-wbs-list",
            "project_id": str(project_id), "plan_id": str(plan_id),
            "plan_version_id": str(plan_version_id),
            "session": hashlib.sha256(session_token).hexdigest(),
            "page_size": page_size, "ordinal": ordinal,
            "wbs_item_id": str(wbs_item_id),
        }
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=True).encode("ascii")
        return _b64(raw) + "." + _b64(hmac.digest(self._key, raw, "sha256"))

    def decode(self, token: str, *, session_token: bytes, project_id: uuid.UUID,
               plan_id: uuid.UUID, plan_version_id: uuid.UUID,
               page_size: int) -> tuple[int, uuid.UUID]:
        try:
            if (type(token) is not str or _TOKEN.fullmatch(token) is None
                    or type(session_token) is not bytes or len(session_token) != 32
                    or any(type(value) is not uuid.UUID or value.int == 0 for value in (
                        project_id, plan_id, plan_version_id))
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
                    or payload["family"] != "plan-version-wbs-list"
                    or payload["project_id"] != str(project_id)
                    or payload["plan_id"] != str(plan_id)
                    or payload["plan_version_id"] != str(plan_version_id)
                    or payload["session"] != hashlib.sha256(session_token).hexdigest()
                    or type(payload["page_size"]) is not int
                    or payload["page_size"] != page_size
                    or type(payload["ordinal"]) is not int
                    or payload["ordinal"] < 1
                    or type(payload["wbs_item_id"]) is not str):
                raise ValueError()
            item_id = uuid.UUID(payload["wbs_item_id"])
            ordinal = payload["ordinal"]
            if (item_id.int == 0 or str(item_id) != payload["wbs_item_id"]
                    or self.encode(
                        session_token=session_token, project_id=project_id,
                        plan_id=plan_id, plan_version_id=plan_version_id,
                        page_size=page_size, ordinal=ordinal,
                        wbs_item_id=item_id) != token):
                raise ValueError()
            return ordinal, item_id
        except (TypeError, ValueError, KeyError, OverflowError, UnicodeDecodeError,
                json.JSONDecodeError):
            raise ApplicationError("REQUEST_MALFORMED") from None
