"""Session- and scope-bound signed cursors for Prototype reads."""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import re
import uuid
from datetime import datetime, timezone

from plm_assistant.modules.platform.application.errors import ApplicationError


_TOKEN = re.compile(r"[A-Za-z0-9_-]{1,1024}\.[A-Za-z0-9_-]{43}\Z", re.ASCII)


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _uuid(value: object) -> uuid.UUID:
    if type(value) is not uuid.UUID or value.int == 0:
        raise ValueError()
    return value


def _session(value: object) -> bytes:
    if type(value) is not bytes or len(value) != 32:
        raise ValueError()
    return value


def _page_size(value: object, maximum: int) -> int:
    if type(value) is not int or not 1 <= value <= maximum:
        raise ValueError()
    return value


def _instant(value: object) -> str:
    if (type(value) is not datetime or value.tzinfo is None
            or value.utcoffset() is None):
        raise ValueError()
    return value.astimezone(timezone.utc).isoformat(
        timespec="microseconds",
    ).replace("+00:00", "Z")


def _base(*, family: str, session_token: bytes, page_size: int,
          maximum: int) -> dict[str, object]:
    return {
        "v": 1,
        "family": family,
        "session": hashlib.sha256(_session(session_token)).hexdigest(),
        "query": hashlib.sha256(
            f"page_size={_page_size(page_size, maximum)}".encode("ascii"),
        ).hexdigest(),
    }


class _Codec:
    def __init__(self, key: bytes) -> None:
        if type(key) is not bytes or len(key) != 32:
            raise ValueError("dedicated 32-byte Prototype cursor key required")
        self._key = key

    def _encode(self, payload: dict[str, object]) -> str:
        raw = json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        ).encode("ascii")
        return _b64(raw) + "." + _b64(hmac.digest(self._key, raw, "sha256"))

    def _decode(self, token: str) -> dict[str, object]:
        try:
            if type(token) is not str or _TOKEN.fullmatch(token) is None:
                raise ValueError()
            encoded, signature = token.split(".")
            raw, mac = _unb64(encoded), _unb64(signature)
            if (_b64(raw) != encoded or len(mac) != 32
                    or _b64(mac) != signature
                    or not hmac.compare_digest(
                        mac, hmac.digest(self._key, raw, "sha256"),
                    )):
                raise ValueError()
            value = json.loads(raw.decode("ascii"))
            if type(value) is not dict:
                raise ValueError()
            return value
        except (TypeError, ValueError, UnicodeDecodeError, json.JSONDecodeError,
                binascii.Error):
            raise ApplicationError("REQUEST_MALFORMED") from None

    @staticmethod
    def _matches_base(
        value: dict[str, object], *, family: str, session_token: bytes,
        page_size: int, maximum: int,
    ) -> bool:
        expected = _base(
            family=family, session_token=session_token,
            page_size=page_size, maximum=maximum,
        )
        return all(value.get(field) == expected[field] for field in expected)


class PrototypePackageCursorCodec(_Codec):
    _FAMILY = "prototype-packages"
    _FIELDS = {
        "v", "family", "project", "session", "query", "updated_at",
        "package_id",
    }

    def encode(
        self, *, project_id: uuid.UUID, session_token: bytes, page_size: int,
        updated_at: datetime, package_id: uuid.UUID,
    ) -> str:
        payload = _base(
            family=self._FAMILY, session_token=session_token,
            page_size=page_size, maximum=200,
        )
        payload.update({
            "project": str(_uuid(project_id)),
            "updated_at": _instant(updated_at),
            "package_id": str(_uuid(package_id)),
        })
        return self._encode(payload)

    def decode(
        self, token: str, *, project_id: uuid.UUID, session_token: bytes,
        page_size: int,
    ) -> tuple[datetime, uuid.UUID]:
        try:
            value = self._decode(token)
            if (set(value) != self._FIELDS
                    or not self._matches_base(
                        value, family=self._FAMILY, session_token=session_token,
                        page_size=page_size, maximum=200,
                    )
                    or value["project"] != str(_uuid(project_id))
                    or type(value["updated_at"]) is not str
                    or type(value["package_id"]) is not str):
                raise ValueError()
            instant = datetime.fromisoformat(value["updated_at"].replace("Z", "+00:00"))
            identity = uuid.UUID(value["package_id"])
            if (identity.int == 0 or str(identity) != value["package_id"]
                    or self.encode(
                        project_id=project_id, session_token=session_token,
                        page_size=page_size, updated_at=instant,
                        package_id=identity,
                    ) != token):
                raise ValueError()
            return instant, identity
        except ApplicationError:
            raise
        except (KeyError, TypeError, ValueError, OverflowError):
            raise ApplicationError("REQUEST_MALFORMED") from None


class PrototypeCursorCodec(_Codec):
    _FAMILY = "prototypes"
    _FIELDS = {
        "v", "family", "project", "session", "query", "updated_at",
        "prototype_id",
    }

    def encode(
        self, *, project_id: uuid.UUID, session_token: bytes, page_size: int,
        updated_at: datetime, prototype_id: uuid.UUID,
    ) -> str:
        payload = _base(
            family=self._FAMILY, session_token=session_token,
            page_size=page_size, maximum=200,
        )
        payload.update({
            "project": str(_uuid(project_id)),
            "updated_at": _instant(updated_at),
            "prototype_id": str(_uuid(prototype_id)),
        })
        return self._encode(payload)

    def decode(
        self, token: str, *, project_id: uuid.UUID, session_token: bytes,
        page_size: int,
    ) -> tuple[datetime, uuid.UUID]:
        try:
            value = self._decode(token)
            if (set(value) != self._FIELDS
                    or not self._matches_base(
                        value, family=self._FAMILY, session_token=session_token,
                        page_size=page_size, maximum=200,
                    )
                    or value["project"] != str(_uuid(project_id))
                    or type(value["updated_at"]) is not str
                    or type(value["prototype_id"]) is not str):
                raise ValueError()
            instant = datetime.fromisoformat(value["updated_at"].replace("Z", "+00:00"))
            identity = uuid.UUID(value["prototype_id"])
            if (identity.int == 0 or str(identity) != value["prototype_id"]
                    or self.encode(
                        project_id=project_id, session_token=session_token,
                        page_size=page_size, updated_at=instant,
                        prototype_id=identity,
                    ) != token):
                raise ValueError()
            return instant, identity
        except ApplicationError:
            raise
        except (KeyError, TypeError, ValueError, OverflowError):
            raise ApplicationError("REQUEST_MALFORMED") from None


class PrototypeVersionCursorCodec(_Codec):
    _FAMILY = "prototype-versions"
    _FIELDS = {
        "v", "family", "project", "prototype", "session", "query",
        "version_no",
    }

    def encode(
        self, *, project_id: uuid.UUID, prototype_id: uuid.UUID,
        session_token: bytes, page_size: int, version_no: int,
    ) -> str:
        if type(version_no) is not int or version_no < 1:
            raise ValueError("invalid PrototypeVersion cursor position")
        payload = _base(
            family=self._FAMILY, session_token=session_token,
            page_size=page_size, maximum=100,
        )
        payload.update({
            "project": str(_uuid(project_id)),
            "prototype": str(_uuid(prototype_id)),
            "version_no": version_no,
        })
        return self._encode(payload)

    def decode(
        self, token: str, *, project_id: uuid.UUID,
        prototype_id: uuid.UUID, session_token: bytes, page_size: int,
    ) -> int:
        try:
            value = self._decode(token)
            if (set(value) != self._FIELDS
                    or not self._matches_base(
                        value, family=self._FAMILY, session_token=session_token,
                        page_size=page_size, maximum=100,
                    )
                    or value["project"] != str(_uuid(project_id))
                    or value["prototype"] != str(_uuid(prototype_id))
                    or type(value["version_no"]) is not int
                    or value["version_no"] < 1
                    or self.encode(
                        project_id=project_id, prototype_id=prototype_id,
                        session_token=session_token, page_size=page_size,
                        version_no=value["version_no"],
                    ) != token):
                raise ValueError()
            return value["version_no"]
        except ApplicationError:
            raise
        except (KeyError, TypeError, ValueError, OverflowError):
            raise ApplicationError("REQUEST_MALFORMED") from None


class PrototypeTemplateCursorCodec(_Codec):
    _FAMILY = "prototype-templates"
    _FIELDS = {
        "v", "family", "scope", "project", "session", "query",
        "updated_at", "template_id",
    }

    @staticmethod
    def _scope(scope: str, project_id: uuid.UUID | None) -> tuple[str, str | None]:
        if scope == "GLOBAL" and project_id is None:
            return scope, None
        if scope == "PROJECT":
            return scope, str(_uuid(project_id))
        raise ValueError()

    def encode(
        self, *, scope: str, project_id: uuid.UUID | None,
        session_token: bytes, page_size: int, updated_at: datetime,
        template_id: uuid.UUID,
    ) -> str:
        scope_value, project_value = self._scope(scope, project_id)
        payload = _base(
            family=self._FAMILY, session_token=session_token,
            page_size=page_size, maximum=200,
        )
        payload.update({
            "scope": scope_value,
            "project": project_value,
            "updated_at": _instant(updated_at),
            "template_id": str(_uuid(template_id)),
        })
        return self._encode(payload)

    def decode(
        self, token: str, *, scope: str, project_id: uuid.UUID | None,
        session_token: bytes, page_size: int,
    ) -> tuple[datetime, uuid.UUID]:
        try:
            scope_value, project_value = self._scope(scope, project_id)
            value = self._decode(token)
            if (set(value) != self._FIELDS
                    or not self._matches_base(
                        value, family=self._FAMILY, session_token=session_token,
                        page_size=page_size, maximum=200,
                    )
                    or value["scope"] != scope_value
                    or value["project"] != project_value
                    or type(value["updated_at"]) is not str
                    or type(value["template_id"]) is not str):
                raise ValueError()
            instant = datetime.fromisoformat(value["updated_at"].replace("Z", "+00:00"))
            identity = uuid.UUID(value["template_id"])
            if (identity.int == 0 or str(identity) != value["template_id"]
                    or self.encode(
                        scope=scope, project_id=project_id,
                        session_token=session_token, page_size=page_size,
                        updated_at=instant, template_id=identity,
                    ) != token):
                raise ValueError()
            return instant, identity
        except ApplicationError:
            raise
        except (KeyError, TypeError, ValueError, OverflowError):
            raise ApplicationError("REQUEST_MALFORMED") from None


class RequirementPrototypeLinkCursorCodec(_Codec):
    _FAMILY = "requirement-prototype-links"
    _FIELDS = {
        "v", "family", "project", "session", "query", "link_id",
    }

    def encode(
        self, *, project_id: uuid.UUID, session_token: bytes,
        page_size: int, link_id: uuid.UUID,
    ) -> str:
        payload = _base(
            family=self._FAMILY, session_token=session_token,
            page_size=page_size, maximum=200,
        )
        payload.update({
            "project": str(_uuid(project_id)),
            "link_id": str(_uuid(link_id)),
        })
        return self._encode(payload)

    def decode(
        self, token: str, *, project_id: uuid.UUID,
        session_token: bytes, page_size: int,
    ) -> uuid.UUID:
        try:
            value = self._decode(token)
            if (set(value) != self._FIELDS
                    or not self._matches_base(
                        value, family=self._FAMILY, session_token=session_token,
                        page_size=page_size, maximum=200,
                    )
                    or value["project"] != str(_uuid(project_id))
                    or type(value["link_id"]) is not str):
                raise ValueError()
            identity = uuid.UUID(value["link_id"])
            if (identity.int == 0 or str(identity) != value["link_id"]
                    or self.encode(
                        project_id=project_id, session_token=session_token,
                        page_size=page_size, link_id=identity,
                    ) != token):
                raise ValueError()
            return identity
        except ApplicationError:
            raise
        except (KeyError, TypeError, ValueError, OverflowError):
            raise ApplicationError("REQUEST_MALFORMED") from None
