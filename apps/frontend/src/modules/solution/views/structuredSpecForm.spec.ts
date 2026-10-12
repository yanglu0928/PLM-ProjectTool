import { describe, expect, it } from "vitest";
import { buildStructuredSpecPayload, emptyStructuredSpecForm } from "./structuredSpecForm";

describe("structured spec human form", () => {
  it("builds migration and interface payloads without secret or raw JSON fields", () => {
    const migration = { ...emptyStructuredSpecForm(), sourceSystem: "旧 PLM", targetSystem: "新 PLM",
      scope: "零件", cleansingRules: "去重", fieldMappings: "old_id → part_id",
      trialPlan: "试点", reconciliationPlan: "对账", rollbackPlan: "恢复快照",
      acceptanceCriteria: "差异为零" };
    expect(buildStructuredSpecPayload("MIGRATION_SPEC", migration)).toMatchObject({
      source_system: "旧 PLM", field_mappings: [{ source: "old_id", target: "part_id" }],
      cleansing_rules: ["去重"], assumptions: [], exclusions: [] });
    const interfaceForm = { ...migration, dataOwner: "信息部", frequency: "每天",
      errorHandling: "告警", retryPolicy: "三次", authentication: "受控令牌" };
    expect(buildStructuredSpecPayload("INTERFACE_SPEC", interfaceForm)).toMatchObject({
      direction: "INBOUND", data_owner: "信息部", field_mappings: [{ source: "old_id", target: "part_id" }] });
  });
  it("builds a connected linear process and default-deny permission design", () => {
    const process = { ...emptyStructuredSpecForm(), startRole: "申请人", endRole: "申请人",
      processSteps: "review | 审核人 | 申请单 | 审核结果" };
    expect(buildStructuredSpecPayload("PROCESS_MODEL", process)).toMatchObject({
      nodes: [{ id: "start", kind: "START" }, { id: "review", kind: "STEP" },
        { id: "end", kind: "END" }],
      edges: [{ from: "start", to: "review" }, { from: "review", to: "end" }] });
    const permission = { ...emptyStructuredSpecForm(), roles: "申请人\n审批人",
      resources: "项目方案", grants: "审批人 | 项目方案 | 批准 | 当前项目",
      separationPolicy: "申请人与审批人不同", separationOfDuties: "申请人 | 审批人" };
    expect(buildStructuredSpecPayload("PERMISSION_DESIGN", permission)).toMatchObject({
      roles: ["申请人", "审批人"], resources: ["项目方案"], default_deny: true,
      separation_of_duties: [{ left_role: "申请人", right_role: "审批人" }] });
  });
  it("rejects missing required fields, malformed mappings and unknown roles", () => {
    expect(() => buildStructuredSpecPayload("MIGRATION_SPEC", emptyStructuredSpecForm())).toThrow();
    const migration = { ...emptyStructuredSpecForm(), sourceSystem: "old", targetSystem: "new",
      scope: "parts", cleansingRules: "dedupe", fieldMappings: "bad",
      trialPlan: "trial", reconciliationPlan: "reconcile", rollbackPlan: "rollback",
      acceptanceCriteria: "zero" };
    expect(() => buildStructuredSpecPayload("MIGRATION_SPEC", migration)).toThrow("来源 → 目标");
    const permission = { ...emptyStructuredSpecForm(), roles: "申请人", resources: "方案",
      grants: "审批人 | 方案 | 批准 | 当前项目", separationPolicy: "默认拒绝" };
    expect(() => buildStructuredSpecPayload("PERMISSION_DESIGN", permission)).toThrow("角色和资源");
  });
});
