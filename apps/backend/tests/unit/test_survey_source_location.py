from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone

from plm_assistant.modules.capability.application.survey_source_location import (
    CapabilityDocumentLocation, CapabilitySurveySourceLocation,
)
from plm_assistant.modules.document.application.survey_source_location import (
    DocumentSurveySourceLocation,
)
from plm_assistant.modules.handover.application.survey_source_location import (
    HandoverSurveySourceLocation,
)
from plm_assistant.modules.survey.application.read_surveys import SurveySourceView
from plm_assistant.modules.survey.application.source_location import (
    SurveySourceLocationError, SurveySourceLocationQuery,
    SurveySourceLocationService,
)


class Tx:
    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class Guard:
    def require_valid(self, *, trace_id):
        self.trace_id = trace_id


class Access:
    actor = uuid.uuid4()

    def authenticated_user(self, transaction, *, session_token, now):
        return self.actor


class Authorization:
    def require_in_transaction(self, transaction, **kwargs):
        self.kwargs = kwargs


class Sources:
    source = None

    def get_source(self, transaction, **kwargs):
        self.kwargs = kwargs
        return self.source


class Resolver:
    target = None

    def resolve(self, transaction, **kwargs):
        self.kwargs = kwargs
        return self.target


class SurveySourceLocationTests(unittest.TestCase):
    def setUp(self):
        self.project, self.survey, self.version = (
            uuid.uuid4(), uuid.uuid4(), uuid.uuid4(),
        )
        self.question, self.row = uuid.uuid4(), uuid.uuid4()
        self.analysis, self.item = uuid.uuid4(), uuid.uuid4()
        self.baseline, self.capability = uuid.uuid4(), uuid.uuid4()
        self.document, self.document_version = uuid.uuid4(), uuid.uuid4()
        self.evidence = uuid.uuid4()
        self.query = SurveySourceLocationQuery(
            b"s" * 32, uuid.uuid4(), self.project,
        )
        self.sources, self.handover = Sources(), Resolver()
        self.capabilities, self.documents = Resolver(), Resolver()
        self.authorization = Authorization()
        self.service = SurveySourceLocationService(
            unit_of_work=Tx, access=Access(), license_guard=Guard(),
            authorization=self.authorization, sources=self.sources,
            handover=self.handover, capability=self.capabilities,
            documents=self.documents,
            clock=lambda: datetime(2026, 10, 6, tzinfo=timezone.utc),
        )

    def source(self, kind: str, ordinal: int = 0) -> SurveySourceView:
        return SurveySourceView(
            kind,
            self.row if kind == "HANDOVER_ITEM" else None,
            self.version if kind == "HANDOVER_ITEM" else None,
            self.analysis if kind == "HANDOVER_ITEM" else None,
            self.row if kind == "CAPABILITY_ITEM" else None,
            self.version if kind == "CAPABILITY_ITEM" else None,
            self.baseline if kind == "CAPABILITY_ITEM" else None,
            self.document_version if kind == "TEMPLATE_DOCUMENT_VERSION" else None,
            self.document if kind == "TEMPLATE_DOCUMENT_VERSION" else None,
            "会议纪要" if kind == "MANUAL" else None,
            ordinal,
        )

    def locate(self):
        return self.service.locate(
            self.query, survey_id=self.survey,
            survey_version_id=self.version, question_id=self.question,
            source_ordinal=0,
        )

    def test_handover_returns_public_record_and_project_locations(self):
        self.sources.source = self.source("HANDOVER_ITEM")
        self.handover.target = HandoverSurveySourceLocation(
            self.analysis, self.version, self.item, "CONFIRMED", True,
            (self.evidence,),
        )
        result = self.locate()
        self.assertEqual("LOCATABLE", result.resolution_state)
        self.assertTrue(result.current_eligibility)
        self.assertEqual("HANDOVER_ITEM", result.record_ref.record_kind)
        self.assertEqual(["BUSINESS_RECORD", "EVIDENCE"],
                         [item.location_kind for item in result.locations])
        self.assertTrue(all(item.scope == "PROJECT" for item in result.locations))
        self.assertEqual("SURVEY_VERSION_GET",
                         self.authorization.kwargs["operation"])
        self.assertEqual(self.row,
                         self.handover.kwargs["analysis_item_row_id"])

    def test_historical_handover_is_locatable_but_not_current(self):
        self.sources.source = self.source("HANDOVER_ITEM")
        self.handover.target = HandoverSurveySourceLocation(
            self.analysis, self.version, self.item, "SUPERSEDED", False, (),
        )
        result = self.locate()
        self.assertEqual("LOCATABLE", result.resolution_state)
        self.assertFalse(result.current_eligibility)

    def test_capability_does_not_expand_global_locations(self):
        self.sources.source = self.source("CAPABILITY_ITEM")
        self.capabilities.target = CapabilitySurveySourceLocation(
            self.baseline, self.version, self.capability, "AVAILABLE", True,
            (CapabilityDocumentLocation(self.document, self.document_version),),
            (self.evidence,),
        )
        result = self.locate()
        self.assertEqual("PARTIALLY_LOCATABLE", result.resolution_state)
        self.assertEqual((), result.locations)
        self.assertEqual("NO_AUTHORIZED_LOCATION", result.unavailable_reason)
        self.assertEqual(self.capability, result.record_ref.item_id)

    def test_project_template_returns_fixed_document_location(self):
        self.sources.source = self.source("TEMPLATE_DOCUMENT_VERSION")
        self.documents.target = DocumentSurveySourceLocation(
            self.document, self.document_version, "PROJECT", self.project, True,
        )
        result = self.locate()
        self.assertEqual("LOCATABLE", result.resolution_state)
        self.assertEqual("DOCUMENT_VERSION", result.locations[0].location_kind)
        self.assertEqual(self.document_version, result.locations[0].version_id)

    def test_global_template_is_not_promoted_to_project_access(self):
        self.sources.source = self.source("TEMPLATE_DOCUMENT_VERSION")
        self.documents.target = DocumentSurveySourceLocation(
            self.document, self.document_version, "GLOBAL", None, True,
        )
        result = self.locate()
        self.assertEqual("PARTIALLY_LOCATABLE", result.resolution_state)
        self.assertEqual((), result.locations)
        self.assertEqual("NO_AUTHORIZED_LOCATION", result.unavailable_reason)

    def test_manual_and_missing_target_are_explicitly_unavailable(self):
        self.sources.source = self.source("MANUAL")
        result = self.locate()
        self.assertEqual("MANUAL_SOURCE_NOT_FIXED", result.unavailable_reason)
        self.sources.source = self.source("HANDOVER_ITEM")
        result = self.locate()
        self.assertEqual("SOURCE_TARGET_UNAVAILABLE", result.unavailable_reason)

    def test_missing_source_is_hidden_and_invalid_ordinal_rejected(self):
        with self.assertRaises(SurveySourceLocationError) as caught:
            self.locate()
        self.assertEqual("RESOURCE_NOT_FOUND", caught.exception.code)
        with self.assertRaises(SurveySourceLocationError) as caught:
            self.service.locate(
                self.query, survey_id=self.survey,
                survey_version_id=self.version, question_id=self.question,
                source_ordinal=100,
            )
        self.assertEqual("VALIDATION_FAILED", caught.exception.code)

    def test_session_token_is_redacted(self):
        self.assertNotIn("s" * 32, repr(self.query))


if __name__ == "__main__":
    unittest.main()

