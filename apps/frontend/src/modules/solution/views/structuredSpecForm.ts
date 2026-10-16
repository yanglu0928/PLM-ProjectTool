/** Human-readable SOL-06 form fields; the server remains the schema authority. */
import { stableStructuredSpecValue, type SpecType } from "../api/structuredSpecCreateClient";

export interface StructuredSpecForm {
  assumptions: string; exclusions: string;
  sourceSystem: string; targetSystem: string;
  direction: "INBOUND" | "OUTBOUND" | "BIDIRECTIONAL";
  dataOwner: string; frequency: string; errorHandling: string;
  retryPolicy: string; authentication: string;
  scope: string; cleansingRules: string; fieldMappings: string;
  trialPlan: string; reconciliationPlan: string; rollbackPlan: string;
  acceptanceCriteria: string;
  startRole: string; endRole: string; processSteps: string;
  roles: string; resources: string; grants: string; separationPolicy: string;
  separationOfDuties: string;
}

export function emptyStructuredSpecForm(): StructuredSpecForm {
  return { assumptions: "", exclusions: "", sourceSystem: "", targetSystem: "",
    direction: "INBOUND", dataOwner: "", frequency: "", errorHandling: "",
    retryPolicy: "", authentication: "", scope: "", cleansingRules: "",
    fieldMappings: "", trialPlan: "", reconciliationPlan: "", rollbackPlan: "",
    acceptanceCriteria: "", startRole: "", endRole: "", processSteps: "",
    roles: "", resources: "", grants: "", separationPolicy: "",
    separationOfDuties: "" };
}
export class StructuredSpecFormError extends Error {
  constructor(message: string) { super(message); this.name = "StructuredSpecFormError"; }
}
function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
function stringValue(value: unknown): string {
  if (typeof value !== "string") throw new StructuredSpecFormError("固定专项正文结构无效，已停止修订。");
  return value;
}
function stringList(value: unknown): string[] {
  if (!Array.isArray(value) || !value.every(item => typeof item === "string")) {
    throw new StructuredSpecFormError("固定专项正文结构无效，已停止修订。");
  }
  return value;
}
function objectRows(value: unknown, keys: readonly string[]): Record<string, unknown>[] {
  if (!Array.isArray(value) || !value.every(item => record(item)
    && Object.keys(item).length === keys.length && keys.every(key => Object.hasOwn(item, key)))) {
    throw new StructuredSpecFormError("固定专项正文结构无效，已停止修订。");
  }
  return value as Record<string, unknown>[];
}
function text(value: string, label: string, maximum = 500): string {
  const item = value.trim().normalize("NFC");
  if (!item || item.length > maximum || /[\p{Cc}\p{Cs}]/u.test(item)) {
    throw new StructuredSpecFormError(`${label}不能为空、超长或含控制字符。`);
  }
  return item;
}
function lines(value: string, label: string, required = false): string[] {
  const result = value.split(/\r?\n/).map(item => item.trim()).filter(Boolean)
    .map(item => text(item, label));
  if (result.length > 500 || required && result.length === 0
    || new Set(result).size !== result.length) {
    throw new StructuredSpecFormError(`${label}至少需一条、最多 500 条且不能重复。`);
  }
  return result;
}
function pairs(value: string, label: string): { source: string; target: string }[] {
  const rows = lines(value, label, true).map(row => {
    const cells = row.split(/\s*(?:→|->)\s*/);
    if (cells.length !== 2) throw new StructuredSpecFormError(`${label}每行请写“来源 → 目标”。`);
    return { source: text(cells[0]!, "来源字段"), target: text(cells[1]!, "目标字段") };
  });
  if (new Set(rows.map(row => `${row.source}\0${row.target}`)).size !== rows.length) {
    throw new StructuredSpecFormError(`${label}不能重复。`);
  }
  return rows;
}
function columns(value: string, label: string, count: number, required = false,
                 optional: readonly number[] = []): string[][] {
  return lines(value, label, required).map(row => {
    const cells = row.split("|").map((item, index) => optional.includes(index)
      ? item.trim().normalize("NFC") : text(item, label));
    if (cells.length !== count) throw new StructuredSpecFormError(`${label}每行应有 ${count} 栏，以“|”分隔。`);
    if (cells.some(item => item.length > 500 || /[\p{Cc}\p{Cs}]/u.test(item))) {
      throw new StructuredSpecFormError(`${label}含无效字符或字段过长。`);
    }
    return cells;
  });
}
function commaItems(value: string): string[] {
  if (!value.trim()) return [];
  const items = value.split(/[，,]/).map(item => text(item, "输入/输出字段"));
  if (new Set(items).size !== items.length) throw new StructuredSpecFormError("输入/输出字段不能重复。");
  return items;
}
export function buildStructuredSpecPayload(
  kind: SpecType, form: StructuredSpecForm,
): Readonly<Record<string, unknown>> {
  const base = { assumptions: lines(form.assumptions, "假设"),
    exclusions: lines(form.exclusions, "排除项") };
  if (kind === "MIGRATION_SPEC") {
    return { ...base, source_system: text(form.sourceSystem, "源系统"),
      target_system: text(form.targetSystem, "目标系统"),
      scope: text(form.scope, "迁移范围", 2000),
      cleansing_rules: lines(form.cleansingRules, "清洗规则", true),
      field_mappings: pairs(form.fieldMappings, "字段映射"),
      trial_plan: text(form.trialPlan, "试迁移计划", 2000),
      reconciliation_plan: text(form.reconciliationPlan, "对账计划", 2000),
      rollback_plan: text(form.rollbackPlan, "回滚计划", 2000),
      acceptance_criteria: text(form.acceptanceCriteria, "验收标准", 2000) };
  }
  if (kind === "INTERFACE_SPEC") {
    return { ...base, source_system: text(form.sourceSystem, "源系统"),
      target_system: text(form.targetSystem, "目标系统"),
      direction: form.direction,
      data_owner: text(form.dataOwner, "数据责任方", 2000),
      frequency: text(form.frequency, "交换频率", 2000),
      error_handling: text(form.errorHandling, "异常处理", 2000),
      retry_policy: text(form.retryPolicy, "重试策略", 2000),
      authentication: text(form.authentication, "认证方式", 2000),
      field_mappings: pairs(form.fieldMappings, "字段映射") };
  }
  if (kind === "PROCESS_MODEL") {
    const start = { id: "start", kind: "START", role: text(form.startRole, "发起角色", 128),
      inputs: [] as string[], outputs: [] as string[] };
    const end = { id: "end", kind: "END", role: text(form.endRole, "结束角色", 128),
      inputs: [] as string[], outputs: [] as string[] };
    const steps = columns(form.processSteps, "流程步骤", 4, true, [2, 3]).map(([id, role, inputs, outputs]) => ({
      id: text(id!, "节点标识", 128), kind: "STEP", role: text(role!, "责任角色", 128),
      inputs: commaItems(inputs!), outputs: commaItems(outputs!),
    }));
    if (steps.some(item => item.id === "start" || item.id === "end")
      || new Set(steps.map(item => item.id)).size !== steps.length) {
      throw new StructuredSpecFormError("流程节点标识必须唯一，且不可使用 start/end。");
    }
    const nodes = [start, ...steps, end];
    const edges = nodes.slice(0, -1).map((node, index) => ({ from: node.id, to: nodes[index + 1]!.id }));
    return { ...base, nodes, edges };
  }
  if (kind === "PERMISSION_DESIGN") {
    const roles = lines(form.roles, "角色", true);
    const resources = lines(form.resources, "资源", true);
    const grants = columns(form.grants, "权限授予", 4, true).map(([role, resource, action, scope]) => ({
      role, resource, action, scope,
    }));
    if (grants.some(item => !roles.includes(item.role!) || !resources.includes(item.resource!))) {
      throw new StructuredSpecFormError("权限授予中的角色和资源须先列在上方。");
    }
    const separation = columns(form.separationOfDuties, "职责分离", 2).map(([left_role, right_role]) => ({
      left_role, right_role,
    }));
    if (separation.some(item => item.left_role === item.right_role
      || !roles.includes(item.left_role!) || !roles.includes(item.right_role!))) {
      throw new StructuredSpecFormError("职责分离须选择两个不同的已列角色。");
    }
    return { ...base, roles, resources, grants, default_deny: true,
      separation_policy: text(form.separationPolicy, "默认拒绝/职责分离策略", 2000),
      separation_of_duties: separation };
  }
  throw new StructuredSpecFormError("专项类型无效。");
}

/** Convert only payloads that this human form can reproduce byte-for-byte semantically. */
export function structuredSpecFormFromPayload(
  kind: SpecType, payload: Readonly<Record<string, unknown>>,
): StructuredSpecForm {
  if (!record(payload)) throw new StructuredSpecFormError("固定专项正文结构无效，已停止修订。");
  const form = emptyStructuredSpecForm();
  form.assumptions = stringList(payload.assumptions).join("\n");
  form.exclusions = stringList(payload.exclusions).join("\n");
  if (kind === "MIGRATION_SPEC") {
    form.sourceSystem = stringValue(payload.source_system);
    form.targetSystem = stringValue(payload.target_system);
    form.scope = stringValue(payload.scope);
    form.cleansingRules = stringList(payload.cleansing_rules).join("\n");
    form.fieldMappings = objectRows(payload.field_mappings, ["source", "target"])
      .map(item => `${stringValue(item.source)} → ${stringValue(item.target)}`).join("\n");
    form.trialPlan = stringValue(payload.trial_plan);
    form.reconciliationPlan = stringValue(payload.reconciliation_plan);
    form.rollbackPlan = stringValue(payload.rollback_plan);
    form.acceptanceCriteria = stringValue(payload.acceptance_criteria);
  } else if (kind === "INTERFACE_SPEC") {
    form.sourceSystem = stringValue(payload.source_system);
    form.targetSystem = stringValue(payload.target_system);
    if (!["INBOUND", "OUTBOUND", "BIDIRECTIONAL"].includes(payload.direction as string)) {
      throw new StructuredSpecFormError("固定专项正文结构无效，已停止修订。");
    }
    form.direction = payload.direction as StructuredSpecForm["direction"];
    form.dataOwner = stringValue(payload.data_owner);
    form.frequency = stringValue(payload.frequency);
    form.errorHandling = stringValue(payload.error_handling);
    form.retryPolicy = stringValue(payload.retry_policy);
    form.authentication = stringValue(payload.authentication);
    form.fieldMappings = objectRows(payload.field_mappings, ["source", "target"])
      .map(item => `${stringValue(item.source)} → ${stringValue(item.target)}`).join("\n");
  } else if (kind === "PROCESS_MODEL") {
    const nodes = objectRows(payload.nodes, ["id", "kind", "role", "inputs", "outputs"]);
    const edges = objectRows(payload.edges, ["from", "to"]);
    if (nodes.length < 3 || stringValue(nodes[0]!.id) !== "start"
      || stringValue(nodes[0]!.kind) !== "START"
      || stringValue(nodes.at(-1)!.id) !== "end"
      || stringValue(nodes.at(-1)!.kind) !== "END"
      || stringList(nodes[0]!.inputs).length || stringList(nodes[0]!.outputs).length
      || stringList(nodes.at(-1)!.inputs).length || stringList(nodes.at(-1)!.outputs).length
      || nodes.slice(1, -1).some(node => stringValue(node.kind) !== "STEP")
      || edges.length !== nodes.length - 1
      || edges.some((edge, index) => stringValue(edge.from) !== stringValue(nodes[index]!.id)
        || stringValue(edge.to) !== stringValue(nodes[index + 1]!.id))) {
      throw new StructuredSpecFormError("该流程包含分支或当前页面不能安全编辑的结构，已停止修订；原历史未被修改。");
    }
    form.startRole = stringValue(nodes[0]!.role);
    form.endRole = stringValue(nodes.at(-1)!.role);
    form.processSteps = nodes.slice(1, -1).map(node => [stringValue(node.id), stringValue(node.role),
      stringList(node.inputs).join("，"), stringList(node.outputs).join("，")].join(" | ")).join("\n");
  } else if (kind === "PERMISSION_DESIGN") {
    if (payload.default_deny !== true) {
      throw new StructuredSpecFormError("固定权限设计不是默认拒绝，已停止修订；原历史未被修改。");
    }
    form.roles = stringList(payload.roles).join("\n");
    form.resources = stringList(payload.resources).join("\n");
    form.grants = objectRows(payload.grants, ["role", "resource", "action", "scope"])
      .map(item => ["role", "resource", "action", "scope"]
        .map(key => stringValue(item[key])).join(" | ")).join("\n");
    form.separationPolicy = stringValue(payload.separation_policy);
    form.separationOfDuties = objectRows(payload.separation_of_duties,
      ["left_role", "right_role"]).map(item =>
      `${stringValue(item.left_role)} | ${stringValue(item.right_role)}`).join("\n");
  } else {
    throw new StructuredSpecFormError("专项类型无效。");
  }
  try {
    if (stableStructuredSpecValue(buildStructuredSpecPayload(kind, form))
      !== stableStructuredSpecValue(payload)) {
      throw new Error("lossy");
    }
  } catch (failure) {
    if (failure instanceof StructuredSpecFormError) throw failure;
    throw new StructuredSpecFormError("该固定专项包含当前页面不能安全编辑的结构，已停止修订；原历史未被修改。");
  }
  return form;
}
