"""Session-bound signed cursors for Survey definition reads."""

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


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _base(project_id: uuid.UUID, session_token: bytes, page_size: int) -> dict:
    if (type(project_id) is not uuid.UUID or project_id.int == 0
            or type(session_token) is not bytes or len(session_token) != 32
            or type(page_size) is not int or not 1 <= page_size <= 200):
        raise ValueError()
    return {"v": 1, "project": str(project_id),
            "session": hashlib.sha256(session_token).hexdigest(),
            "query": hashlib.sha256(
                f"page_size={page_size}".encode("ascii")
            ).hexdigest()}


class _Codec:
    def __init__(self, key: bytes) -> None:
        if type(key) is not bytes or len(key) != 32:
            raise ValueError("dedicated 32-byte Survey cursor key required")
        self._key = key

    def _encode(self, payload: dict) -> str:
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("ascii")
        return _b64(raw) + "." + _b64(hmac.digest(self._key, raw, "sha256"))

    def _decode(self, token: str) -> dict:
        try:
            if type(token) is not str or _TOKEN.fullmatch(token) is None:
                raise ValueError()
            encoded, signature = token.split(".")
            raw, mac = _unb64(encoded), _unb64(signature)
            if (_b64(raw) != encoded or _b64(mac) != signature or len(mac) != 32
                    or not hmac.compare_digest(
                        mac, hmac.digest(self._key, raw, "sha256")
                    )):
                raise ValueError()
            value = json.loads(raw.decode("ascii"))
            if type(value) is not dict:
                raise ValueError()
            return value
        except (TypeError, ValueError, UnicodeDecodeError, json.JSONDecodeError):
            raise ApplicationError("REQUEST_MALFORMED") from None


class SurveyCursorCodec(_Codec):
    _FIELDS = {"v", "family", "project", "session", "query", "updated_at",
               "survey_id"}

    def encode(self, *, project_id: uuid.UUID, session_token: bytes,
               page_size: int, updated_at: datetime, survey_id: uuid.UUID) -> str:
        payload = _base(project_id, session_token, page_size)
        if (type(updated_at) is not datetime or updated_at.tzinfo is None
                or updated_at.utcoffset() is None or type(survey_id) is not uuid.UUID
                or survey_id.int == 0):
            raise ValueError("invalid Survey cursor position")
        payload.update({"family": "surveys", "updated_at": updated_at.astimezone(
            timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z"),
            "survey_id": str(survey_id)})
        return self._encode(payload)

    def decode(self, token: str, *, project_id: uuid.UUID, session_token: bytes,
               page_size: int) -> tuple[datetime, uuid.UUID]:
        try:
            value = self._decode(token)
            expected = _base(project_id, session_token, page_size)
            if (set(value) != self._FIELDS or value["family"] != "surveys"
                    or any(value[key] != expected[key]
                           for key in ("v", "project", "session", "query"))
                    or type(value["updated_at"]) is not str
                    or type(value["survey_id"]) is not str):
                raise ValueError()
            instant = datetime.fromisoformat(value["updated_at"].replace("Z", "+00:00"))
            identity = uuid.UUID(value["survey_id"])
            if str(identity) != value["survey_id"] or identity.int == 0 or self.encode(
                    project_id=project_id, session_token=session_token,
                    page_size=page_size, updated_at=instant,
                    survey_id=identity) != token:
                raise ValueError()
            return instant, identity
        except ApplicationError:
            raise
        except (KeyError, TypeError, ValueError, OverflowError):
            raise ApplicationError("REQUEST_MALFORMED") from None


class SurveyVersionCursorCodec(_Codec):
    _FIELDS = {"v", "family", "project", "survey", "session", "query",
               "position"}

    def encode(self, *, project_id: uuid.UUID, survey_id: uuid.UUID,
               session_token: bytes, page_size: int, position: int) -> str:
        payload = _base(project_id, session_token, page_size)
        if (type(survey_id) is not uuid.UUID or survey_id.int == 0
                or type(position) is not int or position <= 0):
            raise ValueError("invalid SurveyVersion cursor position")
        payload.update({"family": "survey-versions", "survey": str(survey_id),
                        "position": position})
        return self._encode(payload)

    def decode(self, token: str, *, project_id: uuid.UUID, survey_id: uuid.UUID,
               session_token: bytes, page_size: int) -> int:
        try:
            value = self._decode(token)
            expected = _base(project_id, session_token, page_size)
            if (set(value) != self._FIELDS or value["family"] != "survey-versions"
                    or any(value[key] != expected[key]
                           for key in ("v", "project", "session", "query"))
                    or value["survey"] != str(survey_id)
                    or type(value["position"]) is not int
                    or value["position"] <= 0 or self.encode(
                        project_id=project_id, survey_id=survey_id,
                        session_token=session_token, page_size=page_size,
                        position=value["position"]) != token):
                raise ValueError()
            return value["position"]
        except ApplicationError:
            raise
        except (KeyError, TypeError, ValueError, OverflowError):
            raise ApplicationError("REQUEST_MALFORMED") from None


class SurveyRoundCursorCodec(_Codec):
    _FIELDS = {
        "v", "family", "project", "session", "query", "created_at", "round_id",
    }

    def encode(
        self, *, project_id: uuid.UUID, session_token: bytes,
        page_size: int, created_at: datetime, round_id: uuid.UUID,
    ) -> str:
        payload = _base(project_id, session_token, page_size)
        if (type(created_at) is not datetime or created_at.tzinfo is None
                or created_at.utcoffset() is None
                or type(round_id) is not uuid.UUID or round_id.int == 0):
            raise ValueError("invalid SurveyRound cursor position")
        payload.update({
            "family": "survey-rounds",
            "created_at": created_at.astimezone(timezone.utc).isoformat(
                timespec="microseconds",
            ).replace("+00:00", "Z"),
            "round_id": str(round_id),
        })
        return self._encode(payload)

    def decode(
        self, token: str, *, project_id: uuid.UUID,
        session_token: bytes, page_size: int,
    ) -> tuple[datetime, uuid.UUID]:
        try:
            value = self._decode(token)
            expected = _base(project_id, session_token, page_size)
            if (set(value) != self._FIELDS
                    or value["family"] != "survey-rounds"
                    or any(value[key] != expected[key]
                           for key in ("v", "project", "session", "query"))
                    or type(value["created_at"]) is not str
                    or type(value["round_id"]) is not str):
                raise ValueError()
            instant = datetime.fromisoformat(
                value["created_at"].replace("Z", "+00:00")
            )
            identity = uuid.UUID(value["round_id"])
            if (str(identity) != value["round_id"] or identity.int == 0
                    or self.encode(
                        project_id=project_id,
                        session_token=session_token,
                        page_size=page_size,
                        created_at=instant,
                        round_id=identity,
                    ) != token):
                raise ValueError()
            return instant, identity
        except ApplicationError:
            raise
        except (KeyError, TypeError, ValueError, OverflowError):
            raise ApplicationError("REQUEST_MALFORMED") from None


class SurveyAssignmentCursorCodec(_Codec):
    _FIELDS = {
        "v", "family", "project", "session", "query", "round",
        "created_at", "assignment_id",
    }

    def encode(
        self, *, project_id: uuid.UUID, survey_round_id: uuid.UUID,
        session_token: bytes, page_size: int, created_at: datetime,
        assignment_id: uuid.UUID,
    ) -> str:
        payload = _base(project_id, session_token, page_size)
        if (type(survey_round_id) is not uuid.UUID or survey_round_id.int == 0
                or type(created_at) is not datetime or created_at.tzinfo is None
                or created_at.utcoffset() is None
                or type(assignment_id) is not uuid.UUID or assignment_id.int == 0):
            raise ValueError("invalid SurveyAssignment cursor position")
        payload.update({
            "family": "survey-assignments", "round": str(survey_round_id),
            "created_at": created_at.astimezone(timezone.utc).isoformat(
                timespec="microseconds").replace("+00:00", "Z"),
            "assignment_id": str(assignment_id),
        })
        return self._encode(payload)

    def decode(
        self, token: str, *, project_id: uuid.UUID,
        survey_round_id: uuid.UUID, session_token: bytes, page_size: int,
    ) -> tuple[datetime, uuid.UUID]:
        try:
            value = self._decode(token)
            expected = _base(project_id, session_token, page_size)
            if (set(value) != self._FIELDS
                    or value["family"] != "survey-assignments"
                    or any(value[key] != expected[key]
                           for key in ("v", "project", "session", "query"))
                    or value["round"] != str(survey_round_id)
                    or type(value["created_at"]) is not str
                    or type(value["assignment_id"]) is not str):
                raise ValueError()
            instant = datetime.fromisoformat(value["created_at"].replace("Z", "+00:00"))
            identity = uuid.UUID(value["assignment_id"])
            if (str(identity) != value["assignment_id"] or identity.int == 0
                    or self.encode(
                        project_id=project_id, survey_round_id=survey_round_id,
                        session_token=session_token, page_size=page_size,
                        created_at=instant, assignment_id=identity) != token):
                raise ValueError()
            return instant, identity
        except ApplicationError:
            raise
        except (KeyError, TypeError, ValueError, OverflowError):
            raise ApplicationError("REQUEST_MALFORMED") from None


class SurveyConclusionCursorCodec(_Codec):
    _FIELDS = {
        "v", "family", "project", "session", "query", "created_at",
        "conclusion_id",
    }

    def encode(
        self, *, project_id: uuid.UUID, session_token: bytes,
        page_size: int, created_at: datetime, conclusion_id: uuid.UUID,
    ) -> str:
        payload = _base(project_id, session_token, page_size)
        if (type(created_at) is not datetime or created_at.tzinfo is None
                or created_at.utcoffset() is None
                or type(conclusion_id) is not uuid.UUID
                or conclusion_id.int == 0):
            raise ValueError("invalid SurveyConclusion cursor position")
        payload.update({
            "family": "survey-conclusions",
            "created_at": created_at.astimezone(timezone.utc).isoformat(
                timespec="microseconds").replace("+00:00", "Z"),
            "conclusion_id": str(conclusion_id),
        })
        return self._encode(payload)

    def decode(
        self, token: str, *, project_id: uuid.UUID,
        session_token: bytes, page_size: int,
    ) -> tuple[datetime, uuid.UUID]:
        try:
            value = self._decode(token)
            expected = _base(project_id, session_token, page_size)
            if (set(value) != self._FIELDS
                    or value["family"] != "survey-conclusions"
                    or any(value[key] != expected[key]
                           for key in ("v", "project", "session", "query"))
                    or type(value["created_at"]) is not str
                    or type(value["conclusion_id"]) is not str):
                raise ValueError()
            instant = datetime.fromisoformat(
                value["created_at"].replace("Z", "+00:00"))
            identity = uuid.UUID(value["conclusion_id"])
            if (str(identity) != value["conclusion_id"] or identity.int == 0
                    or self.encode(
                        project_id=project_id,
                        session_token=session_token,
                        page_size=page_size,
                        created_at=instant,
                        conclusion_id=identity,
                    ) != token):
                raise ValueError()
            return instant, identity
        except ApplicationError:
            raise
        except (KeyError, TypeError, ValueError, OverflowError):
            raise ApplicationError("REQUEST_MALFORMED") from None
