from __future__ import annotations

import unittest
import uuid
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.survey.api.read_cursor import SurveyRoundCursorCodec
from plm_assistant.modules.survey.api.rounds import (
    create_survey_round_command_router, create_survey_round_read_router,
)
from plm_assistant.modules.survey.application.change_round import SurveyRoundStateError
from plm_assistant.modules.survey.application.create_round import SurveyRoundCreateError
from plm_assistant.modules.survey.application.read_rounds import SurveyRoundReadError
from plm_assistant.modules.survey.application.round_views import (
    SurveyRoundPage, SurveyRoundView,
)


NOW = datetime(2026, 10, 6, tzinfo=timezone.utc)
PROJECT, SURVEY, VERSION, ROUND, ACTOR = (uuid.uuid4() for _ in range(5))


def view(state="PLANNED", etag='"v0"', **changes):
    value = SurveyRoundView(
        ROUND, SURVEY, VERSION, PROJECT, 1, state,
        NOW + timedelta(hours=1), NOW + timedelta(hours=2), "Customer site",
        ACTOR if state != "PLANNED" else None,
        NOW if state != "PLANNED" else None,
        ACTOR if state == "CLOSED" else None,
        NOW + timedelta(minutes=1) if state == "CLOSED" else None,
        b"p" * 32 if state == "CLOSED" else None,
        cancelled_by=ACTOR if state == "CANCELLED" else None,
        cancelled_at=NOW if state == "CANCELLED" else None,
        cancellation_reason="Duplicate" if state == "CANCELLED" else None,
        created_by=ACTOR, created_at=NOW, updated_by=ACTOR,
        updated_at=NOW, etag=etag,
    )
    return replace(value, **changes)


class Sessions:
    def validate(self, token, **kwargs):
        if token != b"s" * 32:
            raise SessionError("AUTH_SESSION_EXPIRED")
        return object()


class Reads:
    fail = None

    def list_rounds(self, query, *, page_size, after_created_at=None,
                    after_round_id=None):
        if self.fail:
            raise SurveyRoundReadError(self.fail)
        self.after = after_created_at, after_round_id
        more = after_created_at is None
        return SurveyRoundPage((view(),), NOW if more else None,
                               ROUND if more else None, more)

    def get_round(self, query, identity):
        if self.fail:
            raise SurveyRoundReadError(self.fail)
        return view()


class Creates:
    fail = None

    def create(self, command):
        self.last = command
        if self.fail:
            raise SurveyRoundCreateError(self.fail)
        return view()


class States:
    fail = None

    def _result(self, command, state):
        self.last = command
        if self.fail:
            raise SurveyRoundStateError(self.fail)
        changes = {"scheduled_start_at": command.scheduled_start_at,
                   "scheduled_end_at": command.scheduled_end_at,
                   "location_note": command.location_note} if state == "PLANNED" else {}
        return view(state, '"v1"', **changes)

    def patch(self, command): return self._result(command, "PLANNED")
    def open(self, command): return self._result(command, "OPEN")
    def close(self, command): return self._result(command, "CLOSED")
    def cancel(self, command): return self._result(command, "CANCELLED")


class SurveyRoundApiTests(unittest.TestCase):
    def setUp(self):
        self.reads, self.creates, self.states = Reads(), Creates(), States()
        self.reads.fail = self.creates.fail = self.states.fail = None
        origins = LoginOriginPolicy(["https://plm.example.test"])
        read_router = create_survey_round_read_router(
            sessions=Sessions(), origins=origins, reads=self.reads,
            cursors=SurveyRoundCursorCodec(b"r" * 32))
        command_router = create_survey_round_command_router(
            sessions=Sessions(), origins=origins,
            creates=self.creates, states=self.states)
        self.client = TestClient(create_app(
            survey_read_router=read_router, survey_command_router=command_router),
            base_url="https://plm.example.test")
        self.addCleanup(self.client.close)
        self.root = f"/api/v1/projects/{PROJECT}/survey-rounds"
        self.path = f"{self.root}/{ROUND}"
        self.headers = {
            "origin": "https://plm.example.test",
            "cookie": "plm_session=" + (b"s" * 32).hex(),
            "x-csrf-token": (b"c" * 32).hex(),
            "idempotency-key": str(uuid.uuid4()), "if-match": '"v0"',
        }
        self.body = {
            "survey_id": str(SURVEY), "survey_version_id": str(VERSION),
            "scheduled_start_at": "2026-10-06T01:00:00Z",
            "scheduled_end_at": "2026-10-06T02:00:00Z",
            "location_note": "Customer site",
        }

    def test_default_closed_and_all_seven_success_contracts(self):
        with TestClient(create_app(), base_url="https://plm.example.test") as bare:
            self.assertEqual(404, bare.get(self.root).status_code)
            self.assertEqual(404, bare.post(self.root).status_code)

        first = self.client.get(self.root + "?page_size=1", headers=self.headers)
        self.assertEqual(200, first.status_code)
        cursor = first.json()["data"]["next_cursor"]
        second = self.client.get(
            self.root + f"?page_size=1&cursor={cursor}", headers=self.headers)
        self.assertEqual(200, second.status_code)
        self.assertEqual((NOW, ROUND), self.reads.after)

        detail = self.client.get(self.path, headers=self.headers)
        self.assertEqual(200, detail.status_code)
        self.assertEqual('"v0"', detail.headers["etag"])
        self.assertEqual([], detail.json()["data"]["source_records"])

        created = self.client.post(self.root, headers=self.headers, json=self.body)
        self.assertEqual(201, created.status_code)
        self.assertEqual(self.path, created.headers["location"])
        self.assertEqual(SURVEY, self.creates.last.survey_id)

        schedule = {key: self.body[key] for key in (
            "scheduled_start_at", "scheduled_end_at", "location_note")}
        self.assertEqual(200, self.client.patch(
            self.path, headers=self.headers, json=schedule).status_code)
        self.assertEqual(200, self.client.post(
            self.path + ":open", headers=self.headers, content=b"").status_code)
        closed = self.client.post(
            self.path + ":close", headers=self.headers, content=b"")
        self.assertEqual(200, closed.status_code)
        self.assertEqual("70" * 32,
                         closed.json()["data"]["close_report_fingerprint"])
        cancelled = self.client.post(
            self.path + ":cancel", headers=self.headers,
            json={"reason": "Duplicate"})
        self.assertEqual(200, cancelled.status_code)
        self.assertEqual("Duplicate", self.states.last.reason)

    def test_strict_request_and_safe_errors(self):
        self.assertEqual(400, self.client.post(
            self.root, headers=self.headers, json={**self.body, "extra": 1}).status_code)
        self.assertEqual(422, self.client.post(
            self.root, headers=self.headers,
            json={**self.body, "scheduled_end_at": None}).status_code)
        self.assertEqual(428, self.client.post(
            self.path + ":open",
            headers={key: value for key, value in self.headers.items()
                     if key != "if-match"}, content=b"").status_code)
        self.states.fail = "SURVEY_ROUND_INCOMPLETE"
        failed = self.client.post(
            self.path + ":close", headers=self.headers, content=b"")
        self.assertEqual(422, failed.status_code)
        self.assertEqual("VALIDATION_FAILED", failed.json()["error"]["code"])
        self.assertNotIn("Traceback", failed.text)


if __name__ == "__main__":
    unittest.main()
