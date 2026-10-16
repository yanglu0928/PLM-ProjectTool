"""Owned Windows 11 Edge fixture for Requirement aggregate Workflow UI."""

from __future__ import annotations

import importlib.util
import uuid
from datetime import datetime, timezone
from pathlib import Path

from plm_assistant.modules.workflow.application.checklist_qualification import (
    AggregateChecklistQualification, ChecklistQualificationEvidence,
    ChecklistQualificationRegistration, ChecklistQualificationRegistry,
    ChecklistQualificationReview, ChecklistQualificationSubject,
)


ROOT = Path(__file__).resolve().parents[2]


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


base = load(
    ROOT / "validation/sur-06-a07-workflow-edge/serve.py",
    "req01a12a07_browser_base",
)
original_registry = base.build_registry


class SyntheticRequirementOwner:
    """Browser-only proxy; the complete real Owner/PG chain is proven by A05."""

    def __init__(self, context) -> None:
        self.context = context
        self.subjects = tuple(
            (uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4())
            for _ in range(2)
        )

    def qualify_only_current_in_transaction(self, transaction, query):
        assert transaction is not None and query.project_id == self.context["project_id"]
        assert query.item_key in {
            "REQUIREMENT_FORMAL_VERSIONS", "REQUIREMENT_ACCEPTANCE",
        }
        now = datetime.now(timezone.utc)
        evidence = ChecklistQualificationEvidence(
            self.context["evidence_id"], query.project_id, 0,
            self.context["evidence_fingerprint"], now,
        )
        subjects = []
        for index, (subject_id, version_id, review_id, round_id) in enumerate(
                self.subjects, 1):
            fingerprint = bytes([index]) * 32
            review = ChecklistQualificationReview(
                review_id, round_id, query.project_id, subject_id, version_id,
                1, fingerprint, now, "REQ-03", "REQUIREMENT_ALL_V1",
            )
            subjects.append(ChecklistQualificationSubject(
                "REQ-03", subject_id, version_id, fingerprint,
                (evidence,), review,
            ))
        ordered = tuple(sorted(
            subjects, key=lambda value: (
                value.subject_type, value.subject_id.int,
                value.subject_version_id.int,
            ),
        ))
        scope = b"s" * 32
        return AggregateChecklistQualification(
            query.project_id, "REQUIREMENT", query.item_key, ordered, (),
            scope, bytes([1 if query.item_key.endswith("VERSIONS") else 2]) * 32,
        )


def build_registry(context):
    registry = original_registry(context)
    owners = registry._owners
    requirement = SyntheticRequirementOwner(context)
    return ChecklistQualificationRegistry((
        ChecklistQualificationRegistration(
            ("HANDOVER_BASELINE", "HANDOVER_ISSUES"),
            owners["HANDOVER_BASELINE"],
        ),
        ChecklistQualificationRegistration(
            ("SURVEY_ACTUAL_SOURCES", "SURVEY_CONCLUSION"),
            owners["SURVEY_ACTUAL_SOURCES"],
        ),
        ChecklistQualificationRegistration(
            ("REQUIREMENT_FORMAL_VERSIONS", "REQUIREMENT_ACCEPTANCE"),
            requirement,
        ),
    ))


def main() -> None:
    base.build_registry = build_registry
    base.FINAL_STAGE = "PROTOTYPE"
    base.FINAL_VERSION = 10
    base.FINAL_PASS_COUNT = 6
    base.FINAL_TRANSITION_COUNT = 3
    base.FINAL_GATE_COUNT = 6
    base.FINAL_RECEIPT_COUNT = 10
    base.READY_PREFIX = "REQ01_A12_A07_BROWSER_READY"
    base.PASS_PREFIX = "REQ_01_A12_A07_WORKFLOW_EDGE_PASS"
    base.review_fixture.main(base.verify_browser)
    print("REQ_01_A12_A07_OWNED_FIXTURE_CLEANUP_PASS")


if __name__ == "__main__":
    main()
