from __future__ import annotations

import copy
import unittest

from plm_assistant.modules.solution.application.structured_spec_payload import (
    StructuredSpecPayloadError,
    validate_structured_spec_payload,
)


def _base() -> dict[str, object]:
    return {"assumptions": ["客户确认角色归属"], "exclusions": ["不含外部系统改造"]}


def _process() -> dict[str, object]:
    return {
        **_base(),
        "nodes": [
            {"id": "start", "kind": "START", "role": "业务人员", "inputs": [], "outputs": ["申请"]},
            {"id": "review", "kind": "STEP", "role": "审批人", "inputs": ["申请"], "outputs": ["结果"]},
            {"id": "end", "kind": "END", "role": "业务人员", "inputs": ["结果"], "outputs": []},
        ],
        "edges": [{"from": "start", "to": "review"}, {"from": "review", "to": "end"}],
    }


def _interface() -> dict[str, object]:
    return {
        **_base(), "source_system": "PLM", "target_system": "ERP",
        "direction": "OUTBOUND", "data_owner": "产品经理", "frequency": "事件触发",
        "error_handling": "记录失败并通知管理员", "retry_policy": "指数退避最多三次",
        "authentication": "双向证书", "field_mappings": [
            {"source": "part_code", "target": "item_code"}],
    }


def _migration() -> dict[str, object]:
    return {
        **_base(), "source_system": "旧PLM", "target_system": "新PLM",
        "scope": "有效零件", "cleansing_rules": ["去除重复料号"],
        "field_mappings": [{"source": "legacy_id", "target": "part_id"}],
        "trial_plan": "先导入试点项目", "reconciliation_plan": "按料号和数量对账",
        "rollback_plan": "恢复迁移前快照", "acceptance_criteria": "差异项为零",
    }


def _permission() -> dict[str, object]:
    return {
        **_base(), "roles": ["申请人", "审批人"], "resources": ["变更单"],
        "grants": [{"role": "申请人", "resource": "变更单", "action": "CREATE", "scope": "OWN"},
                   {"role": "审批人", "resource": "变更单", "action": "APPROVE", "scope": "PROJECT"}],
        "default_deny": True,
        "separation_policy": "申请与批准由不同人员负责",
        "separation_of_duties": [{"left_role": "申请人", "right_role": "审批人"}],
    }


class StructuredSpecPayloadTests(unittest.TestCase):
    def denied(self, spec_type: object, payload: object, *, schema_version: object = 1) -> None:
        with self.assertRaisesRegex(StructuredSpecPayloadError, "VALIDATION_FAILED"):
            validate_structured_spec_payload(spec_type, payload, schema_version=schema_version)

    def test_four_types_are_canonical_immutable_snapshots(self) -> None:
        for spec_type, source in (
            ("PROCESS_MODEL", _process), ("INTERFACE_SPEC", _interface),
            ("MIGRATION_SPEC", _migration), ("PERMISSION_DESIGN", _permission),
        ):
            with self.subTest(spec_type=spec_type):
                payload = source()
                result = validate_structured_spec_payload(spec_type, payload)
                self.assertEqual(result.spec_type, spec_type)
                self.assertEqual(result.schema_version, 1)
                self.assertEqual(len(result.payload_fingerprint), 32)
                self.assertNotIn("客户确认角色归属", repr(result))
                same = validate_structured_spec_payload(spec_type, dict(reversed(list(payload.items()))))
                self.assertEqual(same.payload_fingerprint, result.payload_fingerprint)
                result.payload()["assumptions"].clear()
                payload["assumptions"].clear()
                self.assertEqual(result.payload()["assumptions"], ["客户确认角色归属"])

    def test_rejects_unknown_type_version_shape_and_unbounded_input(self) -> None:
        for spec_type, payload, version in (
            ("OTHER", _process(), 1), ("PROCESS_MODEL", _process(), True),
            ("PROCESS_MODEL", _process(), 2), ("PROCESS_MODEL", [], 1),
            ("PROCESS_MODEL", {**_process(), "surprise": "ignored?"}, 1),
            ("PROCESS_MODEL", {**_process(), "assumptions": ["bad\nline"]}, 1),
            ("PROCESS_MODEL", {**_process(), "assumptions": ["e\u0301"]}, 1),
            ("PROCESS_MODEL", {**_process(), "assumptions": ["x" * 1_000_000]}, 1),
            ("PROCESS_MODEL", {**_process(), "assumptions": [float("nan")]}, 1),
            ("PROCESS_MODEL", {**_process(), "assumptions": [{1: "bad"}]}, 1),
            ("PROCESS_MODEL", {**_process(), "assumptions": ("tuple",)}, 1),
        ):
            with self.subTest(spec_type=spec_type, version=version, payload=repr(payload)[:70]):
                self.denied(spec_type, payload, schema_version=version)

    def test_process_graph_rejects_duplicate_dangling_unreachable_and_missing_end(self) -> None:
        for mutate in (
            lambda p: p["nodes"].append(copy.deepcopy(p["nodes"][1])),
            lambda p: p["nodes"].pop(),
            lambda p: p["edges"].append(copy.deepcopy(p["edges"][0])),
            lambda p: p["edges"][0].update({"to": "missing"}),
            lambda p: p["edges"].pop(),
            lambda p: p["edges"].append({"from": "end", "to": "review"}),
            lambda p: p["nodes"][1].update({"kind": "START"}),
        ):
            payload = _process()
            mutate(payload)
            with self.subTest(payload=payload):
                self.denied("PROCESS_MODEL", payload)

    def test_process_can_have_multiple_documented_end_states(self) -> None:
        payload = _process()
        payload["nodes"].append({"id": "rejected", "kind": "END", "role": "审批人",
                                 "inputs": ["申请"], "outputs": ["退回意见"]})
        payload["edges"].append({"from": "review", "to": "rejected"})
        self.assertEqual(len(validate_structured_spec_payload(
            "PROCESS_MODEL", payload).payload()["nodes"]), 4)

    def test_interface_requires_boundary_policy_and_unique_mapping(self) -> None:
        for mutate in (
            lambda p: p.pop("authentication"),
            lambda p: p.update({"direction": "SIDEWAYS"}),
            lambda p: p.update({"source_system": ""}),
            lambda p: p.update({"retry_policy": " "}),
            lambda p: p["field_mappings"].append(copy.deepcopy(p["field_mappings"][0])),
            lambda p: p.update({"field_mappings": []}),
        ):
            payload = _interface()
            mutate(payload)
            with self.subTest(payload=payload):
                self.denied("INTERFACE_SPEC", payload)

    def test_migration_requires_trial_reconciliation_rollback_and_mapping(self) -> None:
        for mutate in (
            lambda p: p.pop("trial_plan"),
            lambda p: p.update({"reconciliation_plan": ""}),
            lambda p: p.update({"rollback_plan": " "}),
            lambda p: p.update({"cleansing_rules": []}),
            lambda p: p["field_mappings"].append(copy.deepcopy(p["field_mappings"][0])),
        ):
            payload = _migration()
            mutate(payload)
            with self.subTest(payload=payload):
                self.denied("MIGRATION_SPEC", payload)

    def test_same_system_boundary_is_explicit_not_artificially_rejected(self) -> None:
        interface = _interface()
        interface["target_system"] = "PLM"
        migration = _migration()
        migration["target_system"] = "旧PLM"
        self.assertEqual(validate_structured_spec_payload(
            "INTERFACE_SPEC", interface).spec_type, "INTERFACE_SPEC")
        self.assertEqual(validate_structured_spec_payload(
            "MIGRATION_SPEC", migration).spec_type, "MIGRATION_SPEC")

    def test_permission_requires_default_deny_known_roles_and_separation(self) -> None:
        for mutate in (
            lambda p: p.update({"default_deny": 1}),
            lambda p: p.update({"separation_policy": ""}),
            lambda p: p["grants"][0].update({"role": "unknown"}),
            lambda p: p["grants"].append(copy.deepcopy(p["grants"][0])),
            lambda p: p["separation_of_duties"][0].update({"right_role": "申请人"}),
            lambda p: p.update({"roles": ["申请人", "申请人"]}),
        ):
            payload = _permission()
            mutate(payload)
            with self.subTest(payload=payload):
                self.denied("PERMISSION_DESIGN", payload)

    def test_single_role_may_explicitly_have_no_separation_pair(self) -> None:
        payload = _permission()
        payload["roles"] = ["申请人"]
        payload["grants"] = payload["grants"][:1]
        payload["separation_policy"] = "单角色试点，不存在可分离的批准动作"
        payload["separation_of_duties"] = []
        self.assertEqual(validate_structured_spec_payload(
            "PERMISSION_DESIGN", payload).spec_type, "PERMISSION_DESIGN")


if __name__ == "__main__":
    unittest.main()
