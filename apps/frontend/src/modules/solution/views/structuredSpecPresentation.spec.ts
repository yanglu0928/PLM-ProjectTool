import { describe, expect, it } from "vitest";
import type { StructuredSpecDetail } from "../api/structuredSpecReadClient";
import { describeStructuredSpec } from "./structuredSpecPresentation";

function detail(spec_type: StructuredSpecDetail["spec_type"], payload: Record<string, unknown>) {
  return { spec_type, payload } as StructuredSpecDetail;
}
const base = { assumptions: ["待确认现场规模"], exclusions: [] };

describe("structured spec business presentation", () => {
  it("shows migration and interface fields without raw JSON", () => {
    const migration = describeStructuredSpec(detail("MIGRATION_SPEC", { ...base,
      source_system: "旧", target_system: "新", scope: "零件", cleansing_rules: ["去重"],
      field_mappings: [{ source: "old_id", target: "part_id" }],
      trial_plan: "试点", reconciliation_plan: "核对", rollback_plan: "恢复",
      acceptance_criteria: "零差异" }));
    expect(migration.title).toBe("数据迁移设计");
    expect(migration.fields).toContainEqual({ label: "迁移范围", value: "零件" });
    expect(migration.tables[0]?.rows).toEqual([["old_id", "part_id"]]);
    const interfaceSpec = describeStructuredSpec(detail("INTERFACE_SPEC", { ...base,
      source_system: "旧", target_system: "新", direction: "INBOUND",
      data_owner: "实施方", frequency: "每日", error_handling: "告警",
      retry_policy: "最多三次", authentication: "证书",
      field_mappings: [{ source: "a", target: "b" }] }));
    expect(interfaceSpec.title).toBe("接口设计");
    expect(interfaceSpec.fields).toContainEqual({ label: "认证方式", value: "证书" });
  });

  it("shows full process graph and permission grants", () => {
    const process = describeStructuredSpec(detail("PROCESS_MODEL", { ...base,
      nodes: [{ id: "start", kind: "START", role: "申请人", inputs: [], outputs: [] },
        { id: "end", kind: "END", role: "审批人", inputs: [], outputs: [] }],
      edges: [{ from: "start", to: "end" }] }));
    expect(process.tables[0]?.rows).toHaveLength(2);
    expect(process.tables[1]?.rows).toEqual([["start", "end"]]);
    const permission = describeStructuredSpec(detail("PERMISSION_DESIGN", { ...base,
      roles: ["申请人"], resources: ["申请单"], default_deny: true,
      separation_policy: "审批人与申请人分离",
      grants: [{ role: "申请人", resource: "申请单", action: "创建", scope: "本人" }],
      separation_of_duties: [] }));
    expect(permission.tables[0]?.rows).toEqual([["申请人", "申请单", "创建", "本人"]]);
    expect(permission.lists).toContainEqual({ label: "默认策略", items: ["未明确授予的操作一律拒绝"] });
  });

  it("rejects malformed and unknown payload rather than dumping JSON", () => {
    expect(() => describeStructuredSpec(detail("MIGRATION_SPEC", { ...base,
      source_system: "旧" }))).toThrow("无法安全展示");
    expect(() => describeStructuredSpec(detail("PROCESS_MODEL", { ...base,
      nodes: [{ id: "start", kind: "START", role: "申请人", inputs: "bad", outputs: [] }],
      edges: [] }))).toThrow("无法安全展示");
  });
});
