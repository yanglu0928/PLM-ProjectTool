/** Frozen Handover DRAFT version command. Inputs are user-confirmed candidates, never AI facts. */
import { SessionClient, SessionClientError } from "@/modules/auth/api/sessionClient";
import { normalizeHandoverSources, type HandoverCreateSource } from "./handoverCreateClient";

export interface HandoverInputField {
  readonly name: string; readonly format: string; readonly example: string; readonly required: boolean;
}
export interface HandoverVersionItemDraft {
  readonly analysis_item_id: string;
  readonly item_type: "GAP" | "MISSING" | "CONFLICT" | "RISK" | "SCOPE" | "NEED_CONFIRM";
  readonly title: string; readonly statement: string; readonly impact: string;
  readonly severity: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
  readonly priority: "LOW" | "MEDIUM" | "HIGH" | "URGENT";
  readonly recommendation: string | null; readonly confirmation_question: string | null;
  readonly required_input_spec: { readonly fields: readonly HandoverInputField[] } | Record<string, never>;
  readonly source_missing: boolean; readonly evidence_refs: readonly string[];
  readonly capability_refs: readonly string[];
  readonly options: readonly { readonly option_code: string; readonly label: string;
    readonly description: string | null }[];
}
export interface HandoverVersionCreateInput {
  readonly source_documents: readonly HandoverCreateSource[];
  readonly capability_baseline_id: string; readonly capability_baseline_version_id: string;
  readonly items: readonly HandoverVersionItemDraft[]; readonly ai_task_refs: readonly string[];
}
export interface HandoverVersionCreateReceipt {
  readonly handover_analysis_version_id: string; readonly handover_analysis_id: string;
  readonly project_id: string; readonly version_no: number; readonly state: "DRAFT";
  readonly source_set_ref: string; readonly capability_baseline_id: string;
  readonly capability_baseline_version_ref: string; readonly content_fingerprint: string;
  readonly supersedes_version_ref: string | null; readonly created_at: string;
  readonly analysis_etag: string;
}
const messages = {
  HANDOVER_VERSION_INVALID: "请核对交接来源、已批准标准能力和有证据的问题内容。",
  HANDOVER_VERSION_UNCERTAIN: "版本提交结果无法确认；请保留原操作号、原内容和版本标记，核对版本列表。",
  AUTH_RELOGIN_REQUIRED: "请重新登录后提交。", AUTH_CLIENT_BUSY: "会话正在处理其他操作。",
  AUTH_SESSION_EXPIRED: "会话已失效。", AUTH_CSRF_INVALID: "登录状态已变化。",
  LICENSE_OPERATION_DENIED: "当前许可不允许创建交接版本。",
  RESOURCE_NOT_FOUND: "分析不存在或当前账户无权创建版本。",
  HANDOVER_SOURCE_REQUIRED: "固定文档集不匹配或已不可用，请核对分析最初来源。",
  HANDOVER_ITEM_INCOMPLETE: "问题的同项目证据未合格，请先核对资格与固定版本。",
  VALIDATION_FAILED: "当前批准标准能力或问题字段不符合要求。",
  CONFLICT_VERSION: "分析版本已变化，请刷新后重新确认。",
  CONFLICT_STATE: "分析当前状态不允许新增版本。",
  CONFLICT_IDEMPOTENCY: "原操作号与当前内容冲突，请核对历史。",
  PROJECT_ARCHIVED: "项目已归档，不能新增交接版本。",
  SYSTEM_UNAVAILABLE: "服务暂不可用，请保留原操作并核对版本列表。",
} as const;
export type HandoverVersionCreateErrorCode = keyof typeof messages;
export class HandoverVersionCreateError extends Error {
  readonly uncertain: boolean;
  constructor(readonly code: HandoverVersionCreateErrorCode) {
    super(messages[code]); this.name = "HandoverVersionCreateError";
    this.uncertain = code === "HANDOVER_VERSION_UNCERTAIN";
  }
}
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const etag = /^"v(0|[1-9][0-9]*)"$/;
const keyPattern = /^[\x20-\x7e]{16,128}$/;
const sourceSet = /^sha256:[0-9a-f]{64}$/;
const sha = /^[0-9a-f]{64}$/;
const stamp = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$/;
function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
function exact(value: Record<string, unknown>, fields: readonly string[]): boolean {
  return Object.keys(value).length === fields.length && fields.every(field => Object.hasOwn(value, field));
}
function id(value: unknown): value is string {
  return typeof value === "string" && uuid.test(value) && value !== "00000000-0000-0000-0000-000000000000";
}
function text(value: unknown, max: number): value is string {
  return typeof value === "string" && value.length >= 1 && value.length <= max
    && value === value.trim() && !/\p{C}/u.test(value);
}
function ids(value: unknown, max: number, allowEmpty: boolean): value is readonly string[] {
  return Array.isArray(value) && value.length <= max && (allowEmpty || value.length > 0)
    && value.every(id) && new Set(value).size === value.length;
}
function invalid(): never { throw new HandoverVersionCreateError("HANDOVER_VERSION_INVALID"); }
function uncertain(): never { throw new HandoverVersionCreateError("HANDOVER_VERSION_UNCERTAIN"); }

export function normalizeHandoverVersionItems(value: unknown): readonly HandoverVersionItemDraft[] {
  if (!Array.isArray(value) || value.length < 1 || value.length > 500) invalid();
  const stable = new Set<string>();
  for (const item of value) {
    if (!record(item) || !exact(item, ["analysis_item_id", "item_type", "title", "statement", "impact",
      "severity", "priority", "recommendation", "confirmation_question", "required_input_spec",
      "source_missing", "evidence_refs", "capability_refs", "options"])
      || !id(item.analysis_item_id) || stable.has(item.analysis_item_id)
      || !["GAP", "MISSING", "CONFLICT", "RISK", "SCOPE", "NEED_CONFIRM"].includes(String(item.item_type))
      || !text(item.title, 255) || !text(item.statement, 4000) || !text(item.impact, 2000)
      || !["LOW", "MEDIUM", "HIGH", "CRITICAL"].includes(String(item.severity))
      || !["LOW", "MEDIUM", "HIGH", "URGENT"].includes(String(item.priority))
      || item.recommendation !== null && !text(item.recommendation, 2000)
      || item.confirmation_question !== null && !text(item.confirmation_question, 2000)
      || typeof item.source_missing !== "boolean"
      || !ids(item.evidence_refs, 200, item.source_missing)
      || !ids(item.capability_refs, 200, true)
      || !record(item.required_input_spec) || !Array.isArray(item.options) || item.options.length > 20) invalid();
    if (item.item_type === "NEED_CONFIRM") {
      if (!exact(item.required_input_spec, ["fields"]) || !Array.isArray(item.required_input_spec.fields)
        || item.required_input_spec.fields.length < 1 || item.required_input_spec.fields.length > 32
        || !text(item.confirmation_question, 2000) || !text(item.recommendation, 2000)
        || item.options.length < 2) invalid();
      for (const field of item.required_input_spec.fields) {
        if (!record(field) || !exact(field, ["name", "format", "example", "required"])
          || !text(field.name, 128) || !text(field.format, 128) || !text(field.example, 500)
          || typeof field.required !== "boolean") invalid();
      }
    } else if (item.confirmation_question !== null || Object.keys(item.required_input_spec).length
      || item.options.length) invalid();
    const optionCodes = new Set<string>();
    for (const option of item.options) {
      if (!record(option) || !exact(option, ["option_code", "label", "description"])
        || typeof option.option_code !== "string" || !/^[A-Z][A-Z0-9_-]{0,31}$/.test(option.option_code)
        || optionCodes.has(option.option_code) || !text(option.label, 255)
        || option.description !== null && !text(option.description, 2000)) invalid();
      optionCodes.add(option.option_code);
    }
    stable.add(item.analysis_item_id);
  }
  return value as readonly HandoverVersionItemDraft[];
}

export class HandoverVersionCreateClient {
  constructor(private readonly session: SessionClient) {
    if (!(session instanceof SessionClient)) invalid();
  }
  async create(projectId: string, analysisId: string, analysisEtag: string,
    input: HandoverVersionCreateInput, key: string): Promise<HandoverVersionCreateReceipt> {
    const lock = typeof analysisEtag === "string" && etag.test(analysisEtag)
      ? Number(analysisEtag.slice(2, -1)) : null;
    if (!id(projectId) || !id(analysisId) || lock === null || !Number.isSafeInteger(lock)
      || lock >= Number.MAX_SAFE_INTEGER || typeof key !== "string" || !keyPattern.test(key)
      || !record(input) || !exact(input, ["source_documents", "capability_baseline_id",
        "capability_baseline_version_id", "items", "ai_task_refs"])
      || !id(input.capability_baseline_id) || !id(input.capability_baseline_version_id)
      || !ids(input.ai_task_refs, 100, true)) invalid();
    let sources: readonly HandoverCreateSource[];
    try { sources = normalizeHandoverSources(input.source_documents); } catch { return invalid(); }
    const items = normalizeHandoverVersionItems(input.items);
    const identity = this.session.view;
    if (!identity || identity.password_change_required || !this.session.canSubmit
      || !identity.authorized_projects.some(project => project.project_id === projectId
        && (project.role === "PROJECT_MANAGER" || project.role === "IMPLEMENTATION_MEMBER"))) {
      throw new HandoverVersionCreateError("RESOURCE_NOT_FOUND");
    }
    const body = JSON.stringify({ source_documents: sources,
      capability_baseline_id: input.capability_baseline_id,
      capability_baseline_version_id: input.capability_baseline_version_id,
      items, ai_task_refs: input.ai_task_refs });
    let response: Response;
    try {
      response = await this.session.postProjectHandoverVersionCreate(projectId, analysisId,
        body, analysisEtag, key);
    } catch (failure) {
      if (failure instanceof SessionClientError && (failure.code === "AUTH_RELOGIN_REQUIRED"
        || failure.code === "AUTH_CLIENT_BUSY")) throw new HandoverVersionCreateError(failure.code);
      return uncertain();
    }
    try {
      if (response.headers.get("content-type")?.split(";")[0].trim().toLowerCase() !== "application/json") uncertain();
      const payload: unknown = await response.json();
      if (!record(payload) || !id(payload.trace_id)) uncertain();
      if (response.status !== 201) {
        const code = record(payload.error) ? payload.error.code : null;
        const statuses: Record<string, number> = { AUTH_SESSION_EXPIRED: 401, AUTH_CSRF_INVALID: 403,
          LICENSE_OPERATION_DENIED: 403, RESOURCE_NOT_FOUND: 404, HANDOVER_SOURCE_REQUIRED: 422,
          HANDOVER_ITEM_INCOMPLETE: 422, VALIDATION_FAILED: 422, CONFLICT_VERSION: 409,
          CONFLICT_STATE: 409, CONFLICT_IDEMPOTENCY: 409, PROJECT_ARCHIVED: 409,
          SYSTEM_UNAVAILABLE: 503 };
        if (typeof code === "string" && statuses[code] === response.status) {
          throw new HandoverVersionCreateError(code as HandoverVersionCreateErrorCode);
        }
        uncertain();
      }
      if (!exact(payload, ["data", "trace_id"]) || !record(payload.data)) uncertain();
      const data = payload.data;
      if (!exact(data, ["handover_analysis_version_id", "handover_analysis_id", "project_id",
        "version_no", "state", "source_set_ref", "capability_baseline_id",
        "capability_baseline_version_ref", "content_fingerprint", "supersedes_version_ref",
        "created_at", "analysis_etag"])
        || !id(data.handover_analysis_version_id) || data.handover_analysis_id !== analysisId
        || data.project_id !== projectId || !Number.isSafeInteger(data.version_no)
        || Number(data.version_no) < 1 || data.state !== "DRAFT"
        || typeof data.source_set_ref !== "string" || !sourceSet.test(data.source_set_ref)
        || data.capability_baseline_id !== input.capability_baseline_id
        || data.capability_baseline_version_ref !== input.capability_baseline_version_id
        || typeof data.content_fingerprint !== "string" || !sha.test(data.content_fingerprint)
        || data.supersedes_version_ref !== null && !id(data.supersedes_version_ref)
        || typeof data.created_at !== "string" || !stamp.test(data.created_at)
        || !Number.isFinite(Date.parse(data.created_at))
        || data.analysis_etag !== `"v${lock + 1}"`
        || response.headers.get("etag") !== data.analysis_etag
        || response.headers.get("location") !== `/api/v1/projects/${projectId}/handover-analyses/${analysisId}/versions/${data.handover_analysis_version_id}`
        || !/(?:^|,)\s*no-store\s*(?:,|$)/i.test(response.headers.get("cache-control") ?? "")) uncertain();
      return Object.freeze({ ...data }) as unknown as HandoverVersionCreateReceipt;
    } catch (failure) {
      if (failure instanceof HandoverVersionCreateError) throw failure;
      return uncertain();
    }
  }
}
