"""Same-transaction fixed OutlineVersion order/source reproof.

This evaluator does not authorize a caller, persist an Audit result, or prove
requirement coverage. Its caller must hold the current Project/Outline access
transaction; coverage remains unavailable until its separate Owner exists.
"""

from __future__ import annotations

import uuid
from typing import Protocol

from .outline_version_history import OutlineVersionHistoryView
from .prove_outline_coverage import (
    CurrentOutlineCoverageProof,
    OutlineCoverageProofError,
)
from .outline_version_input import OutlineVersionDraftInput
from .outline_version_validation_contract import (
    OutlineVersionValidationContractError,
    OutlineVersionValidationFacts,
    OutlineVersionValidationSnapshot,
    ValidateOutlineVersion,
)
from .prove_outline_version_input import (
    CurrentOutlineVersionBase,
    OutlineVersionInputProofError,
    OutlineVersionInputProofService,
    ProvenOutlineVersionInput,
    ReferencePort,
    RequirementPort,
    SectionPort,
)


class OutlineVersionCurrentProofError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("OutlineVersion current proof unavailable")


def _id(value: object) -> bool:
    return type(value) is uuid.UUID and value.int != 0


class OutlineCoveragePort(Protocol):
    def prove(self, transaction: object, *, command: ValidateOutlineVersion,
              version: OutlineVersionHistoryView) -> CurrentOutlineCoverageProof: ...


class _FixedHistoricalBase:
    """Supply the immutable version coordinates, never dynamic next-version state."""

    def __init__(self, version: OutlineVersionHistoryView) -> None:
        self._version = version

    def current(self, transaction: object, *, project_id: uuid.UUID,
                outline_id: uuid.UUID) -> CurrentOutlineVersionBase | None:
        version = self._version
        if (transaction is None or project_id != version.project_id
                or outline_id != version.solution_outline_id):
            return None
        return CurrentOutlineVersionBase(
            version.project_id, version.solution_outline_id,
            version.version_no, version.supersedes_version_ref, 0)


class OutlineVersionCurrentFactsService:
    """Re-evaluate current sources against an immutable historical fingerprint."""

    def __init__(self, *, sections: SectionPort,
                 requirements: RequirementPort,
                 references: ReferencePort,
                 coverage: OutlineCoveragePort | None = None) -> None:
        if any(port is None for port in (sections, requirements, references)):
            raise ValueError("all current Outline source ports required")
        self._sections = sections
        self._requirements = requirements
        self._references = references
        self._coverage = coverage

    def facts(self, transaction: object, *, command: ValidateOutlineVersion,
              version: OutlineVersionHistoryView) -> OutlineVersionValidationFacts:
        if (transaction is None or type(command) is not ValidateOutlineVersion
                or type(version) is not OutlineVersionHistoryView
                or (version.project_id, version.solution_outline_id,
                    version.solution_outline_version_id) != (
                        command.project_id, command.solution_outline_id,
                        command.solution_outline_version_id)):
            raise OutlineVersionCurrentProofError()
        try:
            OutlineVersionValidationSnapshot(
                version.project_id, version.solution_outline_id,
                version.solution_outline_version_id, version.version_no,
                version.version_state, version.content_fingerprint,
                len(version.section_ids), len(version.requirement_refs),
                len(version.reference_refs))
        except (OutlineVersionValidationContractError, TypeError, AttributeError):
            raise OutlineVersionCurrentProofError() from None
        sections = version.section_ids
        if (type(sections) is not tuple or not 1 <= len(sections) <= 100
                or any(not _id(section_id) for section_id in sections)
                or len(set(sections)) != len(sections)):
            return OutlineVersionValidationFacts(order="FAIL")
        try:
            draft = OutlineVersionDraftInput(
                version.project_id, version.solution_outline_id,
                version.section_ids, version.requirement_refs,
                version.reference_refs, version.missing_declarations,
                version.conflict_declarations)
            proven = OutlineVersionInputProofService(
                bases=_FixedHistoricalBase(version),
                sections=self._sections,
                requirements=self._requirements,
                references=self._references).prove(
                    transaction, trace_id=command.trace_id, draft=draft)
            if (type(proven) is not ProvenOutlineVersionInput
                    or proven.next_version_no != version.version_no
                    or proven.supersedes_version_id != version.supersedes_version_ref
                    or proven.draft.project_id != version.project_id
                    or proven.draft.solution_outline_id != version.solution_outline_id):
                raise OutlineVersionCurrentProofError()
            source = ("PASS" if proven.content_fingerprint == version.content_fingerprint
                      else "FAIL")
        except OutlineVersionInputProofError as exc:
            source = "FAIL" if exc.code == "VALIDATION_FAILED" else "UNAVAILABLE"
        except Exception:
            source = "UNAVAILABLE"
        coverage = "UNAVAILABLE"
        if source == "PASS" and self._coverage is not None:
            try:
                proof = self._coverage.prove(
                    transaction, command=command, version=version)
                if (type(proof) is not CurrentOutlineCoverageProof
                        or proof.project_id != version.project_id
                        or proof.solution_outline_id != version.solution_outline_id
                        or proof.solution_outline_version_id
                           != version.solution_outline_version_id
                        or proof.requirement_refs != version.requirement_refs
                        or type(proof.section_version_ids) is not tuple
                        or len(proof.section_version_ids) != len(version.section_ids)
                        or any(not _id(value)
                               for value in proof.section_version_ids)
                        or len(set(proof.section_version_ids))
                           != len(proof.section_version_ids)
                        or type(proof.requirement_scope_fingerprint) is not bytes
                        or len(proof.requirement_scope_fingerprint) != 32):
                    raise OutlineVersionCurrentProofError()
                coverage = "PASS"
            except OutlineCoverageProofError as exc:
                if exc.code == "SOLUTION_COVERAGE_INCOMPLETE":
                    coverage = "FAIL"
            except Exception:
                pass
        return OutlineVersionValidationFacts(order="PASS", source=source,
                                             coverage=coverage)
