from __future__ import annotations

import copy
import uuid
import unittest
from dataclasses import replace

from plm_assistant.modules.solution.application.structured_spec_input import (
    SpecRequirementRef,
    SpecSectionRef,
    StructuredSpecDraftInput,
    StructuredSpecInputError,
    validate_structured_spec_draft,
)


def _payload() -> dict[str, object]:
    return {
        "assumptions": ["试迁移前确认来源字段"], "exclusions": [],
        "source_system": "旧系统", "target_system": "新系统", "scope": "零件主数据",
        "cleansing_rules": ["按料号去重"],
        "field_mappings": [{"source": "legacy_no", "target": "part_no"}],
        "trial_plan": "试点项目先导入", "reconciliation_plan": "按料号与总数核对",
        "rollback_plan": "恢复迁移前快照", "acceptance_criteria": "差异清零",
    }


class StructuredSpecInputTests(unittest.TestCase):
    def setUp(self) -> None:
        self.req1 = SpecRequirementRef(uuid.uuid4(), uuid.uuid4())
        self.req2 = SpecRequirementRef(uuid.uuid4(), uuid.uuid4())
        self.section1 = SpecSectionRef(uuid.uuid4(), uuid.uuid4())
        self.section2 = SpecSectionRef(uuid.uuid4(), uuid.uuid4())
        self.evidence1, self.evidence2 = uuid.uuid4(), uuid.uuid4()
        self.artifact = uuid.uuid4()
        self.value = StructuredSpecDraftInput(
            project_id=uuid.uuid4(), spec_series_id=None,
            supersedes_version_ref=None, spec_type="MIGRATION_SPEC", payload=_payload(),
            requirement_refs=(self.req1, self.req2),
            section_refs=(self.section1, self.section2),
            evidence_ids=(self.evidence1, self.evidence2),
            artifact_ids=(self.artifact,),
        )

    def denied(self, value: object) -> None:
        with self.assertRaisesRegex(StructuredSpecInputError, "VALIDATION_FAILED"):
            validate_structured_spec_draft(value)

    def test_initial_and_revision_have_stable_ordered_snapshots(self) -> None:
        initial = validate_structured_spec_draft(self.value)
        self.assertIsNone(initial.spec_series_id)
        self.assertIsNone(initial.supersedes_version_ref)
        self.assertEqual(len(initial.request_fingerprint), 32)
        self.assertEqual(len(initial.payload_fingerprint), 32)
        self.assertNotIn("试迁移前确认来源字段", repr(initial))
        payload = copy.deepcopy(self.value.payload)
        payload["source_system"] = "changed"
        self.assertEqual(initial.payload()["source_system"], "旧系统")
        initial.payload()["source_system"] = "mutated"
        self.assertEqual(initial.payload()["source_system"], "旧系统")
        equivalent = replace(self.value, payload=dict(reversed(list(self.value.payload.items()))))
        self.assertEqual(initial.request_fingerprint,
                         validate_structured_spec_draft(equivalent).request_fingerprint)
        self.assertNotEqual(initial.request_fingerprint,
                            validate_structured_spec_draft(replace(
                                self.value, requirement_refs=(self.req2, self.req1)
                            )).request_fingerprint)
        self.assertNotEqual(initial.request_fingerprint,
                            validate_structured_spec_draft(replace(
                                self.value, section_refs=(self.section2, self.section1)
                            )).request_fingerprint)
        self.assertNotEqual(initial.request_fingerprint,
                            validate_structured_spec_draft(replace(
                                self.value, evidence_ids=(self.evidence2, self.evidence1)
                            )).request_fingerprint)
        revision = replace(self.value, spec_series_id=uuid.uuid4(),
                           supersedes_version_ref=uuid.uuid4())
        revised = validate_structured_spec_draft(revision)
        self.assertNotEqual(initial.request_fingerprint, revised.request_fingerprint)
        self.assertEqual(revised.spec_series_id, revision.spec_series_id)

    def test_rejects_invalid_project_and_revision_pair(self) -> None:
        for altered in (
            replace(self.value, project_id=uuid.UUID(int=0)),
            replace(self.value, project_id="not-id"),
            replace(self.value, spec_series_id=uuid.uuid4()),
            replace(self.value, supersedes_version_ref=uuid.uuid4()),
            replace(self.value, spec_series_id=uuid.UUID(int=0),
                    supersedes_version_ref=uuid.uuid4()),
            replace(self.value, spec_series_id=uuid.uuid4(),
                    supersedes_version_ref=uuid.UUID(int=0)),
        ):
            with self.subTest(altered=altered):
                self.denied(altered)

    def test_rejects_empty_malformed_and_duplicate_fixed_versions(self) -> None:
        for altered in (
            replace(self.value, requirement_refs=()),
            replace(self.value, section_refs=()),
            replace(self.value, requirement_refs=[self.req1]),
            replace(self.value, section_refs=(SpecSectionRef(uuid.UUID(int=0), uuid.uuid4()),)),
            replace(self.value, requirement_refs=(self.req1, self.req1)),
            replace(self.value, requirement_refs=(
                self.req1, SpecRequirementRef(self.req1.requirement_id, uuid.uuid4()))),
            replace(self.value, requirement_refs=(
                self.req1, SpecRequirementRef(uuid.uuid4(), self.req1.requirement_version_id))),
            replace(self.value, section_refs=(self.section1, self.section1)),
            replace(self.value, section_refs=(
                self.section1, SpecSectionRef(self.section1.solution_section_id, uuid.uuid4()))),
            replace(self.value, section_refs=(
                self.section1, SpecSectionRef(uuid.uuid4(), self.section1.solution_section_version_id))),
            replace(self.value, evidence_ids=(self.evidence1, self.evidence1)),
            replace(self.value, artifact_ids=(self.artifact, self.artifact)),
            replace(self.value, evidence_ids=(uuid.UUID(int=0),)),
            replace(self.value, artifact_ids=("not-id",)),
        ):
            with self.subTest(altered=repr(altered)[:130]):
                self.denied(altered)

    def test_payload_errors_fail_closed_and_order_changes_fingerprint(self) -> None:
        broken = _payload()
        broken.pop("rollback_plan")
        self.denied(replace(self.value, payload=broken))
        self.denied(replace(self.value, spec_type="PROCESS_MODEL"))
        self.assertNotEqual(
            validate_structured_spec_draft(self.value).request_fingerprint,
            validate_structured_spec_draft(replace(self.value, artifact_ids=())).request_fingerprint)
        changed = _payload()
        changed["trial_plan"] = "全量试迁移"
        self.assertNotEqual(
            validate_structured_spec_draft(self.value).request_fingerprint,
            validate_structured_spec_draft(replace(self.value, payload=changed)).request_fingerprint)

    def test_optional_evidence_and_artifact_refs_do_not_create_false_proof(self) -> None:
        without_optional = replace(self.value, evidence_ids=(), artifact_ids=())
        result = validate_structured_spec_draft(without_optional)
        self.assertEqual(result.evidence_ids, ())
        self.assertEqual(result.artifact_ids, ())
        self.assertNotEqual(result.request_fingerprint,
                            validate_structured_spec_draft(self.value).request_fingerprint)


if __name__ == "__main__":
    unittest.main()
