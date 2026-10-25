/** Business-readable, type-specific SOL-06 detail; never fall back to raw JSON. */
import type { StructuredSpecDetail } from "../api/structuredSpecReadClient";

export interface SpecTable {
  readonly label: string;
  readonly headings: readonly string[];
  readonly rows: readonly (readonly string[])[];
}
export interface SpecPresentation {
  readonly title: string;
  readonly fields: readonly { readonly label: string; readonly value: string }[];
  readonly lists: readonly { readonly label: string; readonly items: readonly string[] }[];
  readonly tables: readonly SpecTable[];
}
function bad(): never { throw new Error("专项载荷无法安全展示，请联系管理员核对固定版本。"); }
function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
function exact(value: Record<string, unknown>, keys: readonly string[]): boolean {
  return Object.keys(value).length === keys.length && keys.every(key => Object.hasOwn(value, key));
}
function text(value: unknown): string {
  if (typeof value !== "string" || !value.trim() || value.length > 2000) bad();
  return value;
}
function optionalTextList(value: unknown): string[] {
  if (!Array.isArray(value) || value.length > 500) bad();
  return value.map(text);
}
function fields(payload: Record<string, unknown>, entries: readonly [string, string][]) {
  return entries.map(([key, label]) => ({ label, value: text(payload[key]) }));
}
function table(payload: Record<string, unknown>, key: string, label: string,
               columns: readonly [string, string][]): SpecTable {
  const raw = payload[key];
  if (!Array.isArray(raw) || raw.length > 500) bad();
  return { label, headings: columns.map(([, title]) => title), rows: raw.map(item => {
    if (!record(item) || !exact(item, columns.map(([name]) => name))) bad();
    return columns.map(([name]) => text(item[name]));
  }) };
}
function base(payload: Record<string, unknown>) {
  return [
    { label: "假设", items: optionalTextList(payload.assumptions) },
    { label: "排除项", items: optionalTextList(payload.exclusions) },
  ];
}

export function describeStructuredSpec(detail: StructuredSpecDetail): SpecPresentation {
  const p = detail.payload;
  if (!record(p)) bad();
  const common = ["assumptions", "exclusions"];
  const list = base(p);
  if (detail.spec_type === "MIGRATION_SPEC") {
    if (!exact(p, [...common, "source_system", "target_system", "scope",
      "cleansing_rules", "field_mappings", "trial_plan", "reconciliation_plan",
      "rollback_plan", "acceptance_criteria"])) bad();
    return { title: "数据迁移设计",
      fields: fields(p, [["source_system", "源系统"], ["target_system", "目标系统"],
        ["scope", "迁移范围"], ["trial_plan", "试迁移计划"],
        ["reconciliation_plan", "对账计划"], ["rollback_plan", "回滚计划"],
        ["acceptance_criteria", "验收标准"]]),
      lists: [...list, { label: "清洗规则", items: optionalTextList(p.cleansing_rules) }],
      tables: [table(p, "field_mappings", "字段映射", [["source", "来源字段"],
        ["target", "目标字段"]])],
    };
  }
  if (detail.spec_type === "INTERFACE_SPEC") {
    if (!exact(p, [...common, "source_system", "target_system", "direction",
      "data_owner", "frequency", "error_handling", "retry_policy",
      "authentication", "field_mappings"])) bad();
    if (!["INBOUND", "OUTBOUND", "BIDIRECTIONAL"].includes(p.direction as string)) bad();
    return { title: "接口设计",
      fields: [...fields(p, [["source_system", "源系统"], ["target_system", "目标系统"]]),
        { label: "数据方向", value: ({ INBOUND: "入站", OUTBOUND: "出站",
          BIDIRECTIONAL: "双向" } as Record<string, string>)[p.direction as string]! },
        ...fields(p, [["data_owner", "数据责任方"],
        ["frequency", "交换频率"], ["error_handling", "异常处理"],
        ["retry_policy", "重试策略"], ["authentication", "认证方式"]])],
      lists: list,
      tables: [table(p, "field_mappings", "字段映射", [["source", "来源字段"],
        ["target", "目标字段"]])],
    };
  }
  if (detail.spec_type === "PERMISSION_DESIGN") {
    if (!exact(p, [...common, "roles", "resources", "grants", "default_deny",
      "separation_policy", "separation_of_duties"]) || p.default_deny !== true) bad();
    return { title: "权限设计",
      fields: fields(p, [["separation_policy", "默认拒绝与职责分离策略"]]),
      lists: [...list, { label: "角色", items: optionalTextList(p.roles) },
        { label: "资源", items: optionalTextList(p.resources) },
        { label: "默认策略", items: ["未明确授予的操作一律拒绝"] }],
      tables: [table(p, "grants", "权限授予", [["role", "角色"],
        ["resource", "资源"], ["action", "操作"], ["scope", "范围"]]),
        table(p, "separation_of_duties", "互斥角色", [["left_role", "角色 A"],
          ["right_role", "角色 B"]])],
    };
  }
  if (detail.spec_type === "PROCESS_MODEL") {
    if (!exact(p, [...common, "nodes", "edges"])) bad();
    if (!Array.isArray(p.nodes) || p.nodes.length < 2 || p.nodes.length > 500) bad();
    const nodes = p.nodes.map(node => {
      if (!record(node) || !exact(node, ["id", "kind", "role", "inputs", "outputs"])) bad();
      if (!["START", "STEP", "END"].includes(node.kind as string)) bad();
      const kindLabels: Record<string, string> = { START: "开始", STEP: "步骤", END: "结束" };
      const kind = kindLabels[node.kind as string]!;
      return [text(node.id), kind, text(node.role),
        optionalTextList(node.inputs).join("、") || "—",
        optionalTextList(node.outputs).join("、") || "—"];
    });
    return { title: "业务流程模型", fields: [], lists: list,
      tables: [{ label: "流程节点", headings: ["节点", "类型", "责任角色", "输入", "输出"],
        rows: nodes }, table(p, "edges", "流程连接", [["from", "起点"], ["to", "终点"]])],
    };
  }
  return bad();
}
