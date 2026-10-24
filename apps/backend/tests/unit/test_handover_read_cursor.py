from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone

from plm_assistant.modules.handover.api.read_cursor import (
    HandoverAnalysisCursorCodec, HandoverItemCursorCodec,
    HandoverVersionCursorCodec,
)
from plm_assistant.modules.platform.application.errors import ApplicationError


class HandoverReadCursorTests(unittest.TestCase):
    def setUp(self):
        self.project, self.analysis, self.version = (
            uuid.uuid4(), uuid.uuid4(), uuid.uuid4(),
        )
        self.session = b"s" * 32
        self.analyses = HandoverAnalysisCursorCodec(b"a" * 32)
        self.versions = HandoverVersionCursorCodec(b"v" * 32)
        self.items = HandoverItemCursorCodec(b"i" * 32)

    def test_analysis_round_trip_binds_complete_position(self):
        instant = datetime(2026, 10, 5, 1, 2, 3, 456789,
                           tzinfo=timezone.utc)
        token = self.analyses.encode(
            project_id=self.project, session_token=self.session, page_size=25,
            updated_at=instant, analysis_id=self.analysis,
        )
        self.assertEqual((instant, self.analysis), self.analyses.decode(
            token, project_id=self.project, session_token=self.session,
            page_size=25,
        ))
        for changed in (
            {"project_id": uuid.uuid4()}, {"session_token": b"x" * 32},
            {"page_size": 26},
        ):
            with self.subTest(changed=changed), self.assertRaises(ApplicationError):
                self.analyses.decode(token, project_id=changed.get(
                    "project_id", self.project), session_token=changed.get(
                    "session_token", self.session), page_size=changed.get(
                    "page_size", 25))

    def test_version_round_trip_binds_analysis_and_key_family(self):
        token = self.versions.encode(
            project_id=self.project, analysis_id=self.analysis,
            session_token=self.session, page_size=10, position=3,
        )
        self.assertEqual(3, self.versions.decode(
            token, project_id=self.project, analysis_id=self.analysis,
            session_token=self.session, page_size=10,
        ))
        with self.assertRaises(ApplicationError):
            self.versions.decode(
                token, project_id=self.project, analysis_id=uuid.uuid4(),
                session_token=self.session, page_size=10,
            )
        with self.assertRaises(ApplicationError):
            HandoverVersionCursorCodec(b"x" * 32).decode(
                token, project_id=self.project, analysis_id=self.analysis,
                session_token=self.session, page_size=10,
            )

    def test_item_round_trip_binds_full_parent_chain_and_allows_zero(self):
        token = self.items.encode(
            project_id=self.project, analysis_id=self.analysis,
            version_id=self.version, session_token=self.session,
            page_size=1, position=0,
        )
        self.assertEqual(0, self.items.decode(
            token, project_id=self.project, analysis_id=self.analysis,
            version_id=self.version, session_token=self.session, page_size=1,
        ))
        for analysis, version in (
            (uuid.uuid4(), self.version), (self.analysis, uuid.uuid4()),
        ):
            with self.assertRaises(ApplicationError):
                self.items.decode(
                    token, project_id=self.project, analysis_id=analysis,
                    version_id=version, session_token=self.session, page_size=1,
                )


if __name__ == "__main__":
    unittest.main()
