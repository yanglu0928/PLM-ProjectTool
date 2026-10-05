export type HandoverActionState = "OPEN" | "IN_PROGRESS" | "SUBMITTED" | "VERIFIED" | "CLOSED" | "CANCELLED";
export type HandoverActionCursor = string & { readonly __family: "handover-actions" };
export interface HandoverActionSummary { readonly action_item_id: string; readonly source_kind: "ANALYSIS_ITEM" | "HUMAN";
  readonly action_type: "PROVIDE_INFO" | "CONFIRM_DECISION" | "RESOLVE_CONFLICT" | "MITIGATE_RISK" | "DEFINE_SCOPE" | "OTHER";
  readonly title: string; readonly owner_ref: string; readonly due_at: string; readonly priority: "LOW" | "MEDIUM" | "HIGH" | "URGENT";
  readonly action_state: HandoverActionState; readonly submitted_at: string | null; readonly verified_at: string | null;
  readonly closed_at: string | null; readonly resolution_trace_ref: string | null; readonly updated_at: string; readonly etag: string; }
export interface HandoverActionField { readonly name: string; readonly format: string; readonly example: string; readonly required: boolean; }
export interface HandoverActionDetail extends HandoverActionSummary { readonly source_analysis_version_ref: string | null;
  readonly source_item_id: string | null; readonly human_source_reason: string | null;
  readonly requested_input_spec: Readonly<{ fields: readonly HandoverActionField[] }>;
  readonly responses: readonly Readonly<{ document_id: string; document_version_id: string; ordinal: number }>[];
  readonly evidence: readonly Readonly<{ evidence_id: string; purpose: "SUBMISSION" | "VERIFICATION" | "RESOLUTION"; ordinal: number }>[];
  readonly created_by: string; readonly created_reason: string; readonly created_at: string; readonly verified_by: string | null;
  readonly current_event: Readonly<{ action_state_event_id: string; sequence_no: number; from_state: HandoverActionState | null;
    to_state: HandoverActionState; actor_id: string; reason: string; occurred_at: string }>; }
export interface HandoverActionPage { readonly items: readonly HandoverActionSummary[];
  readonly next_cursor: HandoverActionCursor | null; readonly has_more: boolean; }

const messages = { HANDOVER_ACTION_INVALID_INPUT: "项目、待办或翻页参数无效。", AUTH_SESSION_EXPIRED: "会话已失效，请重新登录。",
  LICENSE_OPERATION_DENIED: "当前许可不允许读取交接待办。", RESOURCE_NOT_FOUND: "待办不存在，或当前账户无权查看。",
  HANDOVER_ACTION_UNAVAILABLE: "暂时无法读取交接待办，请稍后重试。" } as const;
export type HandoverActionReadErrorCode = keyof typeof messages;
export class HandoverActionReadError extends Error { constructor(readonly code: HandoverActionReadErrorCode) {
  super(messages[code]); this.name = "HandoverActionReadError"; } }
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const cursor = /^[A-Za-z0-9_-]{1,1024}\.[A-Za-z0-9_-]{43}$/; const etag = /^"v(0|[1-9][0-9]*)"$/;
const states = new Set<HandoverActionState>(["OPEN", "IN_PROGRESS", "SUBMITTED", "VERIFIED", "CLOSED", "CANCELLED"]);
function record(v: unknown): v is Record<string, unknown> { return typeof v === "object" && v !== null && !Array.isArray(v); }
function exact(v: Record<string, unknown>, keys: readonly string[]) { return Object.keys(v).length === keys.length && keys.every(k => Object.hasOwn(v, k)); }
function id(v: unknown): v is string { return typeof v === "string" && uuid.test(v) && v !== "00000000-0000-0000-0000-000000000000"; }
function instant(v: unknown): v is string { return typeof v === "string" && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$/.test(v) && Number.isFinite(Date.parse(v)); }
function text(v: unknown, max: number): v is string { return typeof v === "string" && v.length > 0 && v.length <= max && v.trim() === v && !/\p{C}/u.test(v); }
function integer(v: unknown, min = 0): v is number { return typeof v === "number" && Number.isSafeInteger(v) && v >= min; }
function nullableId(v: unknown): v is string | null { return v === null || id(v); }
const summaryKeys = ["action_item_id", "source_kind", "action_type", "title", "owner_ref", "due_at", "priority", "action_state",
  "submitted_at", "verified_at", "closed_at", "resolution_trace_ref", "updated_at", "etag"] as const;
export function parseHandoverActionSummary(v: unknown, expectedId?: string): HandoverActionSummary {
  if (!record(v) || !exact(v, summaryKeys) || !id(v.action_item_id) || expectedId !== undefined && v.action_item_id !== expectedId
    || !["ANALYSIS_ITEM", "HUMAN"].includes(String(v.source_kind))
    || !["PROVIDE_INFO", "CONFIRM_DECISION", "RESOLVE_CONFLICT", "MITIGATE_RISK", "DEFINE_SCOPE", "OTHER"].includes(String(v.action_type))
    || !text(v.title, 255) || !id(v.owner_ref) || !instant(v.due_at) || !["LOW", "MEDIUM", "HIGH", "URGENT"].includes(String(v.priority))
    || !states.has(v.action_state as HandoverActionState) || v.submitted_at !== null && !instant(v.submitted_at)
    || v.verified_at !== null && !instant(v.verified_at) || v.closed_at !== null && !instant(v.closed_at)
    || !nullableId(v.resolution_trace_ref) || !instant(v.updated_at) || typeof v.etag !== "string" || !etag.test(v.etag))
    throw new HandoverActionReadError("HANDOVER_ACTION_UNAVAILABLE");
  if (v.action_state === "SUBMITTED" && v.submitted_at === null || v.action_state === "VERIFIED" && (v.submitted_at === null || v.verified_at === null)
    || v.action_state === "CLOSED" && (v.submitted_at === null || v.verified_at === null || v.closed_at === null || v.resolution_trace_ref === null))
    throw new HandoverActionReadError("HANDOVER_ACTION_UNAVAILABLE");
  return Object.freeze({ ...v }) as unknown as HandoverActionSummary;
}
export function parseHandoverActionDetail(v: unknown, actionId: string): HandoverActionDetail {
  if (!record(v)) throw new HandoverActionReadError("HANDOVER_ACTION_UNAVAILABLE");
  const summary = parseHandoverActionSummary(Object.fromEntries(summaryKeys.map(k => [k, v[k]])), actionId);
  const extra = ["source_analysis_version_ref", "source_item_id", "human_source_reason", "requested_input_spec", "responses", "evidence",
    "created_by", "created_reason", "created_at", "verified_by", "current_event"] as const;
  if (!exact(v, [...summaryKeys, ...extra]) || !nullableId(v.source_analysis_version_ref) || !nullableId(v.source_item_id)
    || v.human_source_reason !== null && !text(v.human_source_reason, 2000) || !record(v.requested_input_spec)
    || !exact(v.requested_input_spec, ["fields"]) || !Array.isArray(v.requested_input_spec.fields)
    || v.requested_input_spec.fields.length < 1 || v.requested_input_spec.fields.length > 32 || !Array.isArray(v.responses)
    || v.responses.length > 500 || !Array.isArray(v.evidence) || v.evidence.length > 1000 || !id(v.created_by)
    || !text(v.created_reason, 2000) || !instant(v.created_at) || !nullableId(v.verified_by) || !record(v.current_event))
    throw new HandoverActionReadError("HANDOVER_ACTION_UNAVAILABLE");
  if ((summary.source_kind === "ANALYSIS_ITEM") !== (id(v.source_analysis_version_ref) && id(v.source_item_id) && v.human_source_reason === null)
    || (summary.source_kind === "HUMAN") !== (v.source_analysis_version_ref === null && v.source_item_id === null && text(v.human_source_reason, 2000)))
    throw new HandoverActionReadError("HANDOVER_ACTION_UNAVAILABLE");
  const fields = v.requested_input_spec.fields.map(field => { if (!record(field) || !exact(field, ["name", "format", "example", "required"])
    || !text(field.name, 128) || !text(field.format, 128) || !text(field.example, 500) || typeof field.required !== "boolean")
    throw new HandoverActionReadError("HANDOVER_ACTION_UNAVAILABLE"); return Object.freeze({ name: field.name, format: field.format, example: field.example, required: field.required }); });
  const responses = v.responses.map((item, ordinal) => { if (!record(item) || !exact(item, ["document_id", "document_version_id", "ordinal"])
    || !id(item.document_id) || !id(item.document_version_id) || item.ordinal !== ordinal) throw new HandoverActionReadError("HANDOVER_ACTION_UNAVAILABLE");
    return Object.freeze({ document_id: item.document_id, document_version_id: item.document_version_id, ordinal }); });
  const evidence = v.evidence.map((item, ordinal) => { if (!record(item) || !exact(item, ["evidence_id", "purpose", "ordinal"])
    || !id(item.evidence_id) || !["SUBMISSION", "VERIFICATION", "RESOLUTION"].includes(String(item.purpose)) || item.ordinal !== ordinal)
    throw new HandoverActionReadError("HANDOVER_ACTION_UNAVAILABLE"); return Object.freeze({ evidence_id: item.evidence_id,
      purpose: item.purpose as "SUBMISSION" | "VERIFICATION" | "RESOLUTION", ordinal }); });
  const e = v.current_event; if (!exact(e, ["action_state_event_id", "sequence_no", "from_state", "to_state", "actor_id", "reason", "occurred_at"])
    || !id(e.action_state_event_id) || !integer(e.sequence_no) || e.from_state !== null && !states.has(e.from_state as HandoverActionState)
    || e.to_state !== summary.action_state || !id(e.actor_id) || !text(e.reason, 2000) || !instant(e.occurred_at))
    throw new HandoverActionReadError("HANDOVER_ACTION_UNAVAILABLE");
  return Object.freeze({ ...summary, source_analysis_version_ref: v.source_analysis_version_ref as string | null,
    source_item_id: v.source_item_id as string | null, human_source_reason: v.human_source_reason as string | null,
    requested_input_spec: Object.freeze({ fields: Object.freeze(fields) }), responses: Object.freeze(responses), evidence: Object.freeze(evidence),
    created_by: v.created_by as string, created_reason: v.created_reason as string, created_at: v.created_at as string,
    verified_by: v.verified_by as string | null, current_event: Object.freeze({ action_state_event_id: e.action_state_event_id as string,
      sequence_no: e.sequence_no as number, from_state: e.from_state as HandoverActionState | null, to_state: e.to_state as HandoverActionState,
      actor_id: e.actor_id as string, reason: e.reason as string, occurred_at: e.occurred_at as string }) });
}
export class HandoverActionReadClient {
  constructor(private readonly fetcher: typeof fetch = fetch, private readonly timeoutMs = 10_000) { if (!integer(timeoutMs, 1) || timeoutMs > 30_000) throw new HandoverActionReadError("HANDOVER_ACTION_INVALID_INPUT"); }
  async list(projectId: string, pageSize = 50, next: HandoverActionCursor | null = null): Promise<HandoverActionPage> {
    if (!id(projectId) || !integer(pageSize, 1) || pageSize > 200 || next !== null && !cursor.test(next)) throw new HandoverActionReadError("HANDOVER_ACTION_INVALID_INPUT");
    const q = new URLSearchParams({ page_size: String(pageSize) }); if (next) q.set("cursor", next); const data = await this.#get(`/api/v1/projects/${projectId}/handover-action-items?${q}`);
    if (!record(data) || !exact(data, ["items", "next_cursor", "has_more"]) || !Array.isArray(data.items) || data.items.length > pageSize
      || typeof data.has_more !== "boolean" || data.has_more && (data.items.length === 0 || typeof data.next_cursor !== "string" || !cursor.test(data.next_cursor) || data.next_cursor === next)
      || !data.has_more && data.next_cursor !== null) throw new HandoverActionReadError("HANDOVER_ACTION_UNAVAILABLE");
    const items = data.items.map(item => parseHandoverActionSummary(item)); if (new Set(items.map(item => item.action_item_id)).size !== items.length
      || items.some((item, i) => i > 0 && (items[i - 1]!.updated_at < item.updated_at || items[i - 1]!.updated_at === item.updated_at && items[i - 1]!.action_item_id <= item.action_item_id)))
      throw new HandoverActionReadError("HANDOVER_ACTION_UNAVAILABLE"); return Object.freeze({ items: Object.freeze(items), next_cursor: data.next_cursor as HandoverActionCursor | null, has_more: data.has_more }); }
  async get(projectId: string, actionId: string) { if (!id(projectId) || !id(actionId)) throw new HandoverActionReadError("HANDOVER_ACTION_INVALID_INPUT");
    const result = await this.#get(`/api/v1/projects/${projectId}/handover-action-items/${actionId}`, true); const item = parseHandoverActionDetail(result.data, actionId);
    if (result.etag !== item.etag) throw new HandoverActionReadError("HANDOVER_ACTION_UNAVAILABLE"); return item; }
  async #get(path: string, withEtag?: false): Promise<unknown>; async #get(path: string, withEtag: true): Promise<{ data: unknown; etag: string | null }>;
  async #get(path: string, withEtag = false): Promise<unknown> { const controller = new AbortController(); const timer = window.setTimeout(() => controller.abort(), this.timeoutMs);
    try { const fetcher = this.fetcher; const response = await fetcher(path, { method: "GET", credentials: "same-origin", cache: "no-store", redirect: "error", headers: { Accept: "application/json" }, signal: controller.signal });
      if (controller.signal.aborted || response.headers.get("content-type")?.split(";")[0].trim().toLowerCase() !== "application/json") throw new Error(); const body: unknown = await response.json();
      if (controller.signal.aborted || !record(body) || !id(body.trace_id)) throw new Error(); if (response.status !== 200) { const code = record(body.error) ? body.error.code : null;
        const expected: Record<string, number> = { AUTH_SESSION_EXPIRED: 401, LICENSE_OPERATION_DENIED: 403, RESOURCE_NOT_FOUND: 404 };
        if (typeof code === "string" && expected[code] === response.status) throw new HandoverActionReadError(code as HandoverActionReadErrorCode); throw new Error(); }
      return withEtag ? { data: body.data, etag: response.headers.get("etag") } : body.data;
    } catch (failure) { if (failure instanceof HandoverActionReadError) throw failure; throw new HandoverActionReadError("HANDOVER_ACTION_UNAVAILABLE"); }
    finally { window.clearTimeout(timer); } }
}
