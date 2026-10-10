"""Authorized minimal public locations for immutable Survey question sources."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from plm_assistant.modules.capability.application.survey_source_location import (
    CapabilitySurveySourceLocation, CapabilitySurveySourceLocationPort,
)
from plm_assistant.modules.document.application.survey_source_location import (
    DocumentSurveySourceLocation, DocumentSurveySourceLocationPort,
)
from plm_assistant.modules.handover.application.survey_source_location import (
    HandoverSurveySourceLocation, HandoverSurveySourceLocationPort,
)
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.project.application.authorization import (
    ProjectAuthorizationError, ProjectAuthorizationService,
)
from plm_assistant.modules.survey.application.read_surveys import SurveySourceView


class SurveySourceLocationError(RuntimeError):
    def __init__(self, code: str = "SURVEY_SOURCE_LOCATION_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class SurveySourceLocationQuery:
    session_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class SurveySourceRecordRef:
    record_kind: str
    primary_id: uuid.UUID
    version_id: uuid.UUID
    item_id: uuid.UUID | None


@dataclass(frozen=True, slots=True)
class SurveyPublicLocation:
    location_kind: str
    scope: str
    project_id: uuid.UUID | None
    primary_id: uuid.UUID
    version_id: uuid.UUID | None = None
    item_id: uuid.UUID | None = None


@dataclass(frozen=True, slots=True)
class SurveySourceLocationView:
    source_kind: str
    source_ordinal: int
    resolution_state: str
    current_eligibility: bool
    record_ref: SurveySourceRecordRef | None
    locations: tuple[SurveyPublicLocation, ...]
    unavailable_reason: str | None


class SurveySourceIdentityPort(Protocol):
    def get_source(
        self, transaction: object, *, project_id: uuid.UUID,
        survey_id: uuid.UUID, survey_version_id: uuid.UUID,
        question_id: uuid.UUID, source_ordinal: int,
    ) -> SurveySourceView | None: ...


class SurveySourceLocationService:
    def __init__(
        self, *, unit_of_work: Callable[[], object], access: object,
        license_guard: object, authorization: ProjectAuthorizationService,
        sources: SurveySourceIdentityPort,
        handover: HandoverSurveySourceLocationPort,
        capability: CapabilitySurveySourceLocationPort,
        documents: DocumentSurveySourceLocationPort,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if any(value is None for value in (
                unit_of_work, access, license_guard, authorization, sources,
                handover, capability, documents)):
            raise ValueError("Survey source location dependencies required")
        self._uow, self._access, self._guard = unit_of_work, access, license_guard
        self._authorization, self._sources = authorization, sources
        self._handover, self._capability, self._documents = (
            handover, capability, documents,
        )
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def locate(
        self, query: SurveySourceLocationQuery, *, survey_id: uuid.UUID,
        survey_version_id: uuid.UUID, question_id: uuid.UUID,
        source_ordinal: int,
    ) -> SurveySourceLocationView:
        self._validate(query, survey_id, survey_version_id, question_id, source_ordinal)
        try:
            self._guard.require_valid(trace_id=query.trace_id)
            with self._uow() as tx:
                now = self._clock()
                if (type(now) is not datetime or now.tzinfo is None
                        or now.utcoffset() is None):
                    raise SurveySourceLocationError()
                actor = self._access.authenticated_user(
                    tx, session_token=query.session_token,
                    now=now.astimezone(timezone.utc),
                )
                if type(actor) is not uuid.UUID or actor.int == 0:
                    raise SurveySourceLocationError("AUTH_ACCESS_DENIED")
                self._authorization.require_in_transaction(
                    tx, user_id=actor, project_id=query.project_id,
                    operation="SURVEY_VERSION_GET",
                )
                source = self._sources.get_source(
                    tx, project_id=query.project_id, survey_id=survey_id,
                    survey_version_id=survey_version_id, question_id=question_id,
                    source_ordinal=source_ordinal,
                )
                if type(source) is not SurveySourceView:
                    raise SurveySourceLocationError("RESOURCE_NOT_FOUND")
                if source.ordinal != source_ordinal:
                    raise SurveySourceLocationError()
                return self._resolve(tx, query.project_id, source)
        except SurveySourceLocationError:
            raise
        except ProjectAuthorizationError as error:
            raise SurveySourceLocationError(error.code) from None
        except RuntimeLicenseError:
            raise SurveySourceLocationError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise SurveySourceLocationError() from None

    def _resolve(self, tx: object, project_id: uuid.UUID,
                 source: SurveySourceView) -> SurveySourceLocationView:
        if source.source_kind == "HANDOVER_ITEM":
            target = self._handover.resolve(
                tx, project_id=project_id,
                analysis_item_row_id=self._required(source.handover_item_row_id),
                handover_analysis_version_id=self._required(
                    source.handover_analysis_version_id),
                handover_analysis_id=self._required(source.handover_analysis_id),
            )
            return self._handover_view(source, project_id, target)
        if source.source_kind == "CAPABILITY_ITEM":
            target = self._capability.resolve(
                tx, capability_item_row_id=self._required(
                    source.capability_item_row_id),
                baseline_version_id=self._required(
                    source.capability_baseline_version_id),
                baseline_id=self._required(source.capability_baseline_id),
            )
            return self._capability_view(source, target)
        if source.source_kind == "TEMPLATE_DOCUMENT_VERSION":
            target = self._documents.resolve(
                tx, path_project_id=project_id,
                document_id=self._required(source.template_document_id),
                document_version_id=self._required(
                    source.template_document_version_id),
            )
            return self._document_view(source, project_id, target)
        if source.source_kind == "MANUAL":
            return SurveySourceLocationView(
                "MANUAL", source.ordinal, "UNAVAILABLE", False, None, (),
                "MANUAL_SOURCE_NOT_FIXED",
            )
        raise SurveySourceLocationError()

    @staticmethod
    def _handover_view(source: SurveySourceView, project_id: uuid.UUID,
                       target: HandoverSurveySourceLocation | None,
                       ) -> SurveySourceLocationView:
        if target is None:
            return SurveySourceLocationService._missing(source)
        SurveySourceLocationService._ids(
            target.handover_analysis_id, target.handover_analysis_version_id,
            target.analysis_item_id,
        )
        if (target.item_state not in (
                "CANDIDATE", "CONFIRMED", "RESOLVED", "ACCEPTED_RISK",
                "REJECTED", "SUPERSEDED")
                or type(target.current_eligibility) is not bool
                or type(target.evidence_ids) is not tuple
                or len(target.evidence_ids) > 100):
            raise SurveySourceLocationError()
        SurveySourceLocationService._ids(*target.evidence_ids)
        record = SurveySourceRecordRef(
            "HANDOVER_ITEM", target.handover_analysis_id,
            target.handover_analysis_version_id, target.analysis_item_id,
        )
        locations = (SurveyPublicLocation(
            "BUSINESS_RECORD", "PROJECT", project_id,
            target.handover_analysis_id,
            target.handover_analysis_version_id, target.analysis_item_id,
        ),) + tuple(SurveyPublicLocation(
            "EVIDENCE", "PROJECT", project_id, evidence_id,
        ) for evidence_id in target.evidence_ids)
        return SurveySourceLocationView(
            source.source_kind, source.ordinal, "LOCATABLE",
            target.current_eligibility, record, locations, None,
        )

    @staticmethod
    def _capability_view(source: SurveySourceView,
                         target: CapabilitySurveySourceLocation | None,
                         ) -> SurveySourceLocationView:
        if target is None:
            return SurveySourceLocationService._missing(source)
        SurveySourceLocationService._ids(
            target.baseline_id, target.baseline_version_id,
            target.capability_item_id,
        )
        if (target.item_state not in ("AVAILABLE", "DEPRECATED", "WITHDRAWN")
                or type(target.current_eligibility) is not bool
                or type(target.document_refs) is not tuple
                or type(target.evidence_ids) is not tuple
                or len(target.document_refs) > 100 or len(target.evidence_ids) > 100):
            raise SurveySourceLocationError()
        for ref in target.document_refs:
            SurveySourceLocationService._ids(ref.document_id, ref.document_version_id)
        SurveySourceLocationService._ids(*target.evidence_ids)
        record = SurveySourceRecordRef(
            "CAPABILITY_ITEM", target.baseline_id,
            target.baseline_version_id, target.capability_item_id,
        )
        # Capability is GLOBAL. Project membership must not disclose GLOBAL locations.
        return SurveySourceLocationView(
            source.source_kind, source.ordinal, "PARTIALLY_LOCATABLE",
            target.current_eligibility, record, (), "NO_AUTHORIZED_LOCATION",
        )

    @staticmethod
    def _document_view(source: SurveySourceView, project_id: uuid.UUID,
                       target: DocumentSurveySourceLocation | None,
                       ) -> SurveySourceLocationView:
        if target is None:
            return SurveySourceLocationService._missing(source)
        SurveySourceLocationService._ids(target.document_id, target.document_version_id)
        if (target.scope not in ("GLOBAL", "PROJECT")
                or type(target.current_eligibility) is not bool
                or target.scope == "GLOBAL" and target.project_id is not None
                or target.scope == "PROJECT" and target.project_id != project_id):
            raise SurveySourceLocationError()
        record = SurveySourceRecordRef(
            "TEMPLATE_DOCUMENT_VERSION", target.document_id,
            target.document_version_id, None,
        )
        if target.scope == "GLOBAL":
            return SurveySourceLocationView(
                source.source_kind, source.ordinal, "PARTIALLY_LOCATABLE",
                target.current_eligibility, record, (), "NO_AUTHORIZED_LOCATION",
            )
        return SurveySourceLocationView(
            source.source_kind, source.ordinal, "LOCATABLE",
            target.current_eligibility, record,
            (SurveyPublicLocation(
                "DOCUMENT_VERSION", "PROJECT", project_id,
                target.document_id, target.document_version_id,
            ),), None,
        )

    @staticmethod
    def _missing(source: SurveySourceView) -> SurveySourceLocationView:
        return SurveySourceLocationView(
            source.source_kind, source.ordinal, "UNAVAILABLE", False, None, (),
            "SOURCE_TARGET_UNAVAILABLE",
        )

    @staticmethod
    def _required(value: uuid.UUID | None) -> uuid.UUID:
        if type(value) is not uuid.UUID or value.int == 0:
            raise SurveySourceLocationError()
        return value

    @staticmethod
    def _ids(*values: uuid.UUID) -> None:
        if any(type(value) is not uuid.UUID or value.int == 0 for value in values):
            raise SurveySourceLocationError()

    @classmethod
    def _validate(cls, query: SurveySourceLocationQuery, survey_id: uuid.UUID,
                  version_id: uuid.UUID, question_id: uuid.UUID,
                  ordinal: int) -> None:
        if (type(query) is not SurveySourceLocationQuery
                or type(query.session_token) is not bytes
                or len(query.session_token) != 32
                or type(query.trace_id) is not uuid.UUID or query.trace_id.int == 0
                or type(query.project_id) is not uuid.UUID or query.project_id.int == 0
                or type(ordinal) is not int or not 0 <= ordinal <= 99):
            raise SurveySourceLocationError("VALIDATION_FAILED")
        cls._ids(survey_id, version_id, question_id)

