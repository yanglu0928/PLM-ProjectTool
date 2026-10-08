"""Current-fact validation for an immutable PrototypeVersion."""

from __future__ import annotations

import hmac
import re
from dataclasses import dataclass

from plm_assistant.modules.document.application.prototype_artifact_proof import (
    PrototypeVersionDocumentArtifactProof,
)
from plm_assistant.modules.platform.application.idempotency import (
    canonical_payload_fingerprint,
)
from plm_assistant.modules.requirement.application.prototype_version_proof import (
    PrototypeApprovedRequirementVersionProof,
)

from .create_version import (
    PrototypeVersionCreateError,
    PrototypeVersionCreateService,
    PrototypeVersionInitialView,
)
from .version_input_proofs import PrototypeVersionTemplateProof


_ORDER = (
    "STRUCTURE_INVALID",
    "TEMPLATE_UNAVAILABLE",
    "REQUIREMENT_UNAVAILABLE",
    "ARTIFACT_UNAVAILABLE",
    "CONTENT_FINGERPRINT_MISMATCH",
)


@dataclass(frozen=True, slots=True)
class PrototypeVersionCurrentFacts:
    """Exact external version facts re-proved in the caller transaction."""

    template: PrototypeVersionTemplateProof
    documents: tuple[PrototypeVersionDocumentArtifactProof, ...]
    requirements: tuple[PrototypeApprovedRequirementVersionProof, ...]

    def __post_init__(self) -> None:
        if (type(self.template) is not PrototypeVersionTemplateProof
                or type(self.documents) is not tuple
                or type(self.requirements) is not tuple
                or any(type(item) is not PrototypeVersionDocumentArtifactProof
                       for item in self.documents)
                or any(type(item) is not PrototypeApprovedRequirementVersionProof
                       for item in self.requirements)):
            raise ValueError("invalid PrototypeVersion current facts")


class PrototypeVersionCurrentValidator:
    """Reprove every external input and the aggregate digest in the caller tx."""

    def __init__(self, *, templates: object, requirements: object,
                 documents: object) -> None:
        if any(value is None for value in (templates, requirements, documents)):
            raise ValueError("Prototype current proof dependencies required")
        self._templates = templates
        self._requirements = requirements
        self._documents = documents

    def current_issues(
        self, transaction: object, snapshot: PrototypeVersionInitialView,
    ) -> tuple[str, ...]:
        return self._evaluate(transaction, snapshot)[0]

    def current_facts(
        self, transaction: object, snapshot: PrototypeVersionInitialView,
    ) -> PrototypeVersionCurrentFacts | None:
        """Return exact ordered facts only when every current check passes."""

        issues, facts = self._evaluate(transaction, snapshot)
        return facts if not issues else None

    def _evaluate(
        self, transaction: object, snapshot: PrototypeVersionInitialView,
    ) -> tuple[tuple[str, ...], PrototypeVersionCurrentFacts | None]:
        found: set[str] = set()
        try:
            self._require_snapshot(snapshot)
            artifacts = PrototypeVersionCreateService._artifacts(
                snapshot.artifact_refs,
            )
            requirements = PrototypeVersionCreateService._requirement_refs(
                snapshot.requirement_refs,
            )
            interaction = PrototypeVersionCreateService._object(
                snapshot.interaction_spec,
            )
            coverage = PrototypeVersionCreateService._object(
                snapshot.coverage_summary,
            )
            if (artifacts != snapshot.artifact_refs
                    or requirements != snapshot.requirement_refs):
                raise ValueError("non-canonical owned set")
        except (AttributeError, TypeError, ValueError,
                PrototypeVersionCreateError):
            return ("STRUCTURE_INVALID",), None

        template = self._templates.prove(
            transaction, project_id=snapshot.project_id,
            prototype_template_id=snapshot.template_id,
            prototype_template_version_id=snapshot.template_version_id,
        )
        if not self._valid_template(snapshot, template):
            found.add("TEMPLATE_UNAVAILABLE")

        documents: list[PrototypeVersionDocumentArtifactProof] = []
        artifact_proofs: list[tuple[str, str, str]] = []
        for item in artifacts:
            proof = None
            if item.artifact_kind == "DOCUMENT_VERSION":
                proof = self._documents.prove_for_prototype_version(
                    transaction, project_id=snapshot.project_id,
                    document_version_id=item.target_id,
                )
            if not self._valid_document(snapshot, item.target_id, proof):
                found.add("ARTIFACT_UNAVAILABLE")
                continue
            artifact_proofs.append((
                item.artifact_kind, str(item.target_id), proof.content_sha256,
            ))
            documents.append(proof)

        requirement_facts: list[PrototypeApprovedRequirementVersionProof] = []
        requirement_proofs: list[tuple[str, str, str]] = []
        for item in requirements:
            proof = self._requirements.prove(
                transaction, project_id=snapshot.project_id,
                requirement_id=item.requirement_id,
                requirement_version_id=item.requirement_version_id,
            )
            if not self._valid_requirement(snapshot, item, proof):
                found.add("REQUIREMENT_UNAVAILABLE")
                continue
            requirement_proofs.append((
                str(item.requirement_id), str(item.requirement_version_id),
                proof.content_fingerprint,
            ))
            requirement_facts.append(proof)

        if not found:
            payload = {
                "project_id": str(snapshot.project_id),
                "prototype_id": str(snapshot.prototype_id),
                "expected_lock_version": snapshot.expected_lock_version,
                "template_id": str(snapshot.template_id),
                "template_version_id": str(snapshot.template_version_id),
                "artifact_refs": [
                    (item.artifact_kind, str(item.target_id))
                    for item in artifacts
                ],
                "requirement_refs": [
                    (str(item.requirement_id), str(item.requirement_version_id))
                    for item in requirements
                ],
                "interaction_spec": interaction,
                "coverage_summary": coverage,
                "template_fingerprint": template.content_fingerprint,
                "artifact_proofs": artifact_proofs,
                "requirement_proofs": requirement_proofs,
            }
            actual = bytes.fromhex(snapshot.content_fingerprint)
            expected = canonical_payload_fingerprint(payload)
            if not hmac.compare_digest(actual, expected):
                found.add("CONTENT_FINGERPRINT_MISMATCH")
        issues = tuple(code for code in _ORDER if code in found)
        if issues:
            return issues, None
        try:
            facts = PrototypeVersionCurrentFacts(
                template, tuple(documents), tuple(requirement_facts),
            )
        except ValueError:
            return ("STRUCTURE_INVALID",), None
        return (), facts

    @staticmethod
    def _require_snapshot(snapshot: object) -> None:
        if (type(snapshot) is not PrototypeVersionInitialView
                or snapshot.version_state not in {
                    "DRAFT", "IN_REVIEW", "APPROVED", "RETURNED",
                    "SUPERSEDED", "RESTRICTED",
                }
                or type(snapshot.version_no) is not int
                or snapshot.version_no < 1
                or type(snapshot.expected_lock_version) is not int
                or snapshot.expected_lock_version < 0
                or re.fullmatch(
                    r"[0-9a-f]{64}", snapshot.content_fingerprint,
                ) is None):
            raise ValueError("invalid PrototypeVersion snapshot")

    @staticmethod
    def _valid_template(snapshot, proof) -> bool:
        return (
            type(proof) is PrototypeVersionTemplateProof
            and proof.prototype_template_id == snapshot.template_id
            and proof.prototype_template_version_id
            == snapshot.template_version_id
            and (proof.scope == "GLOBAL" and proof.project_id is None
                 or proof.scope == "PROJECT"
                 and proof.project_id == snapshot.project_id)
        )

    @staticmethod
    def _valid_document(snapshot, target_id, proof) -> bool:
        return (
            type(proof) is PrototypeVersionDocumentArtifactProof
            and proof.document_version_id == target_id
            and (proof.scope == "GLOBAL" and proof.project_id is None
                 or proof.scope == "PROJECT"
                 and proof.project_id == snapshot.project_id)
        )

    @staticmethod
    def _valid_requirement(snapshot, item, proof) -> bool:
        return (
            type(proof) is PrototypeApprovedRequirementVersionProof
            and proof.project_id == snapshot.project_id
            and proof.requirement_id == item.requirement_id
            and proof.requirement_version_id == item.requirement_version_id
        )
