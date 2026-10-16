import { describe, expect, it } from "vitest";
import { buildStructuredSpecPayload, emptyStructuredSpecForm,
  structuredSpecFormFromPayload } from "./structuredSpecForm";

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
  it("round-trips every form-supported payload without changing its meaning", () => {
    const forms = {
      MIGRATION_SPEC: { ...emptyStructuredSpecForm(), assumptions: "已冻结", exclusions: "附件",
        sourceSystem: "旧 PLM", targetSystem: "新 PLM", scope: "零件与 BOM",
        cleansingRules: "去重\n补齐分类", fieldMappings: "old_id → part_id",
        trialPlan: "先试点", reconciliationPlan: "逐项核对", rollbackPlan: "恢复快照",
        acceptanceCriteria: "关键字段差异为零" },
      INTERFACE_SPEC: { ...emptyStructuredSpecForm(), sourceSystem: "ERP", targetSystem: "PLM",
        direction: "BIDIRECTIONAL" as const, dataOwner: "信息部", frequency: "每小时",
        errorHandling: "告警并转人工", retryPolicy: "三次", authentication: "受控令牌",
        fieldMappings: "material → part" },
      PROCESS_MODEL: { ...emptyStructuredSpecForm(), startRole: "申请人", endRole: "申请人",
        processSteps: "review | 审核人 | 申请单，附件 | 审核结果\npublish | 发布人 | 审核结果 | 发布记录" },
      PERMISSION_DESIGN: { ...emptyStructuredSpecForm(), roles: "申请人\n审批人",
        resources: "项目方案", grants: "审批人 | 项目方案 | 批准 | 当前项目",
        separationPolicy: "默认拒绝且申请审批分离", separationOfDuties: "申请人 | 审批人" },
    } as const;
    for (const kind of Object.keys(forms) as (keyof typeof forms)[]) {
      const payload = buildStructuredSpecPayload(kind, forms[kind]);
      expect(buildStructuredSpecPayload(kind,
        structuredSpecFormFromPayload(kind, payload))).toEqual(payload);
    }
  });
  it("refuses a branched process instead of silently flattening its history", () => {
    const payload = { assumptions: [], exclusions: [], nodes: [
      { id: "start", kind: "START", role: "申请人", inputs: [], outputs: [] },
      { id: "a", kind: "STEP", role: "审核人", inputs: [], outputs: [] },
      { id: "b", kind: "STEP", role: "复核人", inputs: [], outputs: [] },
      { id: "end", kind: "END", role: "申请人", inputs: [], outputs: [] },
    ], edges: [{ from: "start", to: "a" }, { from: "start", to: "b" },
      { from: "a", to: "end" }, { from: "b", to: "end" }] };
    expect(() => structuredSpecFormFromPayload("PROCESS_MODEL", payload)).toThrow("分支");
  });
});
