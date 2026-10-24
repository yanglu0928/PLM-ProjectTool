"""Prototype-owned approval manifest and TraceLink projection."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Protocol

from plm_assistant.modules.trace.application.create_link import (
    StoredTraceLink,
    TraceCreateRepositoryPort,
)
from plm_assistant.modules.trace.domain.link_shape import (
    TraceEdgeShape,
    TraceShapeError,
    TraceVersionRef,
)

from .create_version import PrototypeVersionInitialView
from .current_version import (
    PrototypeVersionCurrentFacts,
    PrototypeVersionCurrentValidator,
)


class PrototypeApprovalTraceError(RuntimeError):
    """Safe failure to close an approval Trace manifest."""


@dataclass(frozen=True, slots=True)
class PrototypeApprovalTraceSource:
    ordinal: int
    source_kind: str
    source: TraceVersionRef
    relation_type: str
    trace_link_id: uuid.UUID

    def __post_init__(self) -> None:
        if (type(self.ordinal) is not int or self.ordinal < 1
                or self.source_kind not in {
                    "TEMPLATE_VERSION", "DOCUMENT_VERSION",
                    "REQUIREMENT_VERSION",
                }
                or type(self.source) is not TraceVersionRef
                or self.relation_type not in {"DERIVED_FROM", "IMPLEMENTS"}
                or not _uuid(self.trace_link_id)):
            raise PrototypeApprovalTraceError()


@dataclass(frozen=True, slots=True)
class PrototypeApprovalTraceManifest:
    prototype_version_id: uuid.UUID
    prototype_id: uuid.UUID
    project_id: uuid.UUID
    review_state_result_id: uuid.UUID
    review_id: uuid.UUID
    review_round_id: uuid.UUID
    template_id: uuid.UUID
    template_version_id: uuid.UUID
    content_fingerprint: bytes
    declared_artifact_count: int
    declared_requirement_count: int
    approved_by: uuid.UUID
    sources: tuple[PrototypeApprovalTraceSource, ...]

    def __post_init__(self) -> None:
        if (not _ids(
                self.prototype_version_id, self.prototype_id, self.project_id,
                self.review_state_result_id, self.review_id,
                self.review_round_id, self.template_id,
                self.template_version_id, self.approved_by,
                ) or type(self.content_fingerprint) is not bytes
                or len(self.content_fingerprint) != 32
                or type(self.declared_artifact_count) is not int
                or self.declared_artifact_count < 1
                or type(self.declared_requirement_count) is not int
                or self.declared_requirement_count < 1
                or type(self.sources) is not tuple
                or len(self.sources) != (
                    self.declared_artifact_count
                    + self.declared_requirement_count + 1)
                or tuple(item.ordinal for item in self.sources)
                   != tuple(range(1, len(self.sources) + 1))):
            raise PrototypeApprovalTraceError()


class PrototypeApprovalTraceRepositoryPort(Protocol):
    def insert_manifest(
        self, transaction: object, *, manifest: PrototypeApprovalTraceManifest,
    ) -> None: ...

    def manifest_matches(
        self, transaction: object, *, prototype_version_id: uuid.UUID,
        prototype_id: uuid.UUID, project_id: uuid.UUID,
        review_state_result_id: uuid.UUID, review_id: uuid.UUID,
        review_round_id: uuid.UUID, approved_by: uuid.UUID,
    ) -> bool: ...


class PrototypeApprovalTraceOwner:
    """Create exact generic Trace edges and the Prototype-owned manifest."""

    def __init__(self, *, current: PrototypeVersionCurrentValidator,
                 trace_links: TraceCreateRepositoryPort,
                 manifests: PrototypeApprovalTraceRepositoryPort) -> None:
        if any(item is None for item in (current, trace_links, manifests)):
            raise ValueError("Prototype approval Trace dependencies required")
        self._current = current
        self._trace_links = trace_links
        self._manifests = manifests

    def record_in_transaction(
        self, transaction: object, *, snapshot: PrototypeVersionInitialView,
        review_state_result_id: uuid.UUID, review_id: uuid.UUID,
        review_round_id: uuid.UUID, actor_id: uuid.UUID,
        trace_id: uuid.UUID,
    ) -> None:
        if (type(snapshot) is not PrototypeVersionInitialView
                or not _ids(review_state_result_id, review_id,
                            review_round_id, actor_id, trace_id)):
            raise PrototypeApprovalTraceError()
        facts = self._current.current_facts(transaction, snapshot)
        if type(facts) is not PrototypeVersionCurrentFacts:
            raise PrototypeApprovalTraceError()
        try:
            target = TraceVersionRef(
                "prototype", "PRT-03", snapshot.prototype_id,
                snapshot.prototype_version_id, "PROJECT", snapshot.project_id,
            )
            definitions = self._source_definitions(snapshot, facts)
            sources: list[PrototypeApprovalTraceSource] = []
            for ordinal, source_kind, source, relation in definitions:
                edge = TraceEdgeShape(source, target, relation)
                stored = self._trace_links.create_active(
                    transaction, edge=edge, actor_id=actor_id,
                    trace_id=trace_id,
                )
                if type(stored) is not StoredTraceLink or not _uuid(
                        stored.trace_link_id):
                    raise PrototypeApprovalTraceError()
                sources.append(PrototypeApprovalTraceSource(
                    ordinal, source_kind, source, relation,
                    stored.trace_link_id,
                ))
            manifest = PrototypeApprovalTraceManifest(
                snapshot.prototype_version_id, snapshot.prototype_id,
                snapshot.project_id, review_state_result_id, review_id,
                review_round_id, snapshot.template_id,
                snapshot.template_version_id,
                bytes.fromhex(snapshot.content_fingerprint),
                len(snapshot.artifact_refs), len(snapshot.requirement_refs),
                actor_id, tuple(sources),
            )
            self._manifests.insert_manifest(
                transaction, manifest=manifest,
            )
        except (AttributeError, TypeError, ValueError, TraceShapeError,
                PrototypeApprovalTraceError):
            raise PrototypeApprovalTraceError() from None

    def assert_recorded_in_transaction(
        self, transaction: object, *, prototype_version_id: uuid.UUID,
        prototype_id: uuid.UUID, project_id: uuid.UUID,
        review_state_result_id: uuid.UUID, review_id: uuid.UUID,
        review_round_id: uuid.UUID, actor_id: uuid.UUID,
    ) -> None:
        if (not _ids(
                prototype_version_id, prototype_id, project_id,
                review_state_result_id, review_id, review_round_id, actor_id,
                ) or self._manifests.manifest_matches(
                    transaction,
                    prototype_version_id=prototype_version_id,
                    prototype_id=prototype_id, project_id=project_id,
                    review_state_result_id=review_state_result_id,
                    review_id=review_id, review_round_id=review_round_id,
                    approved_by=actor_id,
                ) is not True):
            raise PrototypeApprovalTraceError()

    @staticmethod
    def _source_definitions(snapshot, facts):
        template = facts.template
        definitions: list[tuple[int, str, TraceVersionRef, str]] = [(
            1, "TEMPLATE_VERSION",
            TraceVersionRef(
                "prototype", "PRT-04",
                template.prototype_template_id,
                template.prototype_template_version_id,
                template.scope, template.project_id,
            ),
            "DERIVED_FROM",
        )]
        for proof in facts.documents:
            definitions.append((
                len(definitions) + 1, "DOCUMENT_VERSION",
                TraceVersionRef(
                    "document", "DOC-02", proof.document_id,
                    proof.document_version_id, proof.scope, proof.project_id,
                ),
                "DERIVED_FROM",
            ))
        for proof in facts.requirements:
            definitions.append((
                len(definitions) + 1, "REQUIREMENT_VERSION",
                TraceVersionRef(
                    "requirement", "REQ-03", proof.requirement_id,
                    proof.requirement_version_id, "PROJECT", proof.project_id,
                ),
                "IMPLEMENTS",
            ))
        if (len(facts.documents) != len(snapshot.artifact_refs)
                or len(facts.requirements) != len(snapshot.requirement_refs)):
            raise PrototypeApprovalTraceError()
        return tuple(definitions)


def _uuid(value: object) -> bool:
    return type(value) is uuid.UUID and value.int != 0


def _ids(*values: object) -> bool:
    return all(_uuid(value) for value in values)
