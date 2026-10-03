import { SessionClient, SessionClientError } from "@/modules/auth/api/sessionClient";

export interface AITaskParameterField { readonly name: string; readonly value_type: "STRING" | "INTEGER" | "BOOLEAN";
  readonly required: boolean; readonly max_length: number | null; readonly minimum: number | null;
  readonly maximum: number | null; readonly allowed_values: readonly string[]; }
export interface AITaskPolicyOption { readonly reference: string; readonly policy_version: number;
  readonly task_type: string; readonly purpose_ref: string; readonly output_schema_ref: string;
  readonly context_policy_ref: string; readonly parameter_fields: readonly AITaskParameterField[]; }
export interface AIEgressPolicyOption { readonly reference: string; readonly allowed_data_categories: readonly string[];
  readonly max_record_count: number; readonly max_payload_bytes: number; readonly max_input_tokens: number;
  readonly max_retry_attempts: number; readonly risk_codes: readonly string[]; readonly ttl_seconds: number; }
export interface AIRouteOption { readonly provider_id: string; readonly model_id: string;
  readonly provider_display_name: string; readonly data_region: string; readonly provider_model_key: string;
  readonly model_revision: string; }
export interface AISubmissionOptions { readonly task_policies: readonly AITaskPolicyOption[];
  readonly egress_policies: readonly AIEgressPolicyOption[]; readonly routes: readonly AIRouteOption[]; }
export interface AIInputRef { readonly resource_type: "DOC-02"; readonly resource_id: string; readonly version_id: string; }
export interface AITaskPlanInput { readonly task_type: string; readonly prompt_policy_ref: string;
  readonly output_schema_ref: string; readonly context_policy_ref: string;
  readonly task_parameters: Readonly<Record<string, string | number | boolean>>; }
export interface AIEgressPreviewInput { readonly purpose_ref: string; readonly provider_id: string;
  readonly model_id: string; readonly source_refs: readonly AIInputRef[];
  readonly allowed_data_categories: readonly string[]; readonly minimal_payload_policy_ref: string;
  readonly max_payload_bytes: number; readonly max_input_tokens: number; readonly max_retry_attempts: number;
  readonly ai_task_plan: AITaskPlanInput; }
export interface AIEgressPreviewView extends AIEgressPreviewInput { readonly preview_id: string;
  readonly project_id: string; readonly provider_config_version_id: string; readonly data_region: string;
  readonly estimated_record_count: number; readonly payload_fingerprint: string;
  readonly source_refs_fingerprint: string; readonly preview_fingerprint: string;
  readonly risk_codes: readonly string[]; readonly created_at: string; readonly expires_at: string; }
export interface AIEgressAuthorizationView { readonly authorization_id: string; readonly preview_id: string;
  readonly project_id: string; readonly preview_fingerprint: string; readonly approved_by: string;
  readonly approved_role: string; readonly approved_at: string; readonly valid_until: string;
  readonly state: "AUTHORIZED"; readonly etag: string; }
export interface AICreatedTask { readonly ai_task_id: string; readonly job_id: string; }

const messages = {
  AI_SUBMISSION_INVALID_INPUT: "请重新读取选项和固定文档版本后再操作。",
  AUTH_RELOGIN_REQUIRED: "提交AI任务前请重新登录。", AUTH_CLIENT_BUSY: "正在处理另一项会话操作，请稍候。",
  AUTH_SESSION_EXPIRED: "会话已失效，请重新登录。", AUTH_CSRF_INVALID: "登录状态已变化，请重新登录。",
  LICENSE_OPERATION_DENIED: "当前许可不允许执行AI任务。", RESOURCE_NOT_FOUND: "资源不存在或当前账户无权操作。",
  CONFLICT_VERSION: "外发预览状态已变化，请重新预览。", CONFLICT_IDEMPOTENCY: "原操作号对应不同输入，已停止。",
  AI_PROVIDER_UNAVAILABLE: "当前没有可用AI服务。", AI_PROMPT_VERSION_INVALID: "当前分析策略不可用，请刷新选项。",
  AI_EGRESS_AUTHORIZATION_REQUIRED: "本轮外发授权无效或已过期，请重新预览并授权。",
  AI_SUBMISSION_UNCERTAIN: "操作结果无法确认。请保留原操作号并核对任务列表，切勿直接换号重试。",
} as const;
export type AISubmissionErrorCode = keyof typeof messages;
export class AISubmissionError extends Error { readonly uncertain: boolean;
  constructor(readonly code: AISubmissionErrorCode) { super(messages[code]); this.name = "AISubmissionError";
    this.uncertain = code === "AI_SUBMISSION_UNCERTAIN"; } }

const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const ref = /^[A-Za-z][A-Za-z0-9._:/-]{0,127}$/; const code = /^[A-Z][A-Z0-9_]{0,63}$/;
const hash = /^[0-9a-f]{64}$/; const etag = /^"v(0|[1-9][0-9]*)"$/;
function record(value: unknown): value is Record<string, unknown> { return typeof value === "object" && value !== null && !Array.isArray(value); }
function id(value: unknown): value is string { return typeof value === "string" && uuid.test(value) && value !== "00000000-0000-0000-0000-000000000000"; }
function positive(value: unknown, zero = false): value is number { return typeof value === "number" && Number.isSafeInteger(value) && value >= (zero ? 0 : 1); }
function instant(value: unknown): value is string { return typeof value === "string" && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$/.test(value) && Number.isFinite(Date.parse(value)); }
function label(value: unknown, max = 128): value is string { return typeof value === "string" && value === value.trim() && value.length > 0 && value.length <= max && !/\p{C}/u.test(value); }
function strings(value: unknown, matcher: RegExp, max = 64): readonly string[] {
  if (!Array.isArray(value) || value.length > max || value.some(item => typeof item !== "string" || !matcher.test(item))
    || new Set(value).size !== value.length) throw new AISubmissionError("AI_SUBMISSION_UNCERTAIN");
  return Object.freeze([...value]) as readonly string[];
}
function envelope(payload: unknown, status: number): { data: unknown; trace: string; error: string | null } {
  if (!record(payload) || !id(payload.trace_id)) throw new AISubmissionError("AI_SUBMISSION_UNCERTAIN");
  if (status >= 200 && status < 300) return { data: payload.data, trace: payload.trace_id, error: null };
  return { data: null, trace: payload.trace_id, error: record(payload.error) && typeof payload.error.code === "string" ? payload.error.code : null };
}
function mapError(status: number, server: string | null): AISubmissionError {
  const expected: Readonly<Record<string, number>> = { AUTH_SESSION_EXPIRED: 401, AUTH_CSRF_INVALID: 403,
    LICENSE_OPERATION_DENIED: 403, RESOURCE_NOT_FOUND: 404, CONFLICT_VERSION: 409,
    CONFLICT_IDEMPOTENCY: 409, AI_PROVIDER_UNAVAILABLE: 503, AI_PROMPT_VERSION_INVALID: 422,
    AI_EGRESS_AUTHORIZATION_REQUIRED: 403 };
  if (server && expected[server] === status) return new AISubmissionError(server as AISubmissionErrorCode);
  if (["REQUEST_MALFORMED", "VALIDATION_FAILED", "CONFLICT_VERSION_REQUIRED"].includes(server ?? "")) {
    return new AISubmissionError("AI_SUBMISSION_INVALID_INPUT");
  }
  return new AISubmissionError("AI_SUBMISSION_UNCERTAIN");
}
function key(value: string) { if (!/^[\x20-\x7e]{16,128}$/.test(value)) throw new AISubmissionError("AI_SUBMISSION_INVALID_INPUT"); }
function inputRefs(value: readonly AIInputRef[]): readonly AIInputRef[] {
  if (!Array.isArray(value) || value.length < 1 || value.length > 1000) throw new AISubmissionError("AI_SUBMISSION_INVALID_INPUT");
  const result = value.map(item => { if (!record(item) || item.resource_type !== "DOC-02" || !id(item.resource_id) || !id(item.version_id)) throw new AISubmissionError("AI_SUBMISSION_INVALID_INPUT");
    return Object.freeze({ resource_type: "DOC-02" as const, resource_id: item.resource_id, version_id: item.version_id }); });
  if (new Set(result.map(item => `${item.resource_id}:${item.version_id}`)).size !== result.length) throw new AISubmissionError("AI_SUBMISSION_INVALID_INPUT");
  return Object.freeze(result);
}
function parseOptions(value: unknown): AISubmissionOptions {
  if (!record(value) || !Array.isArray(value.task_policies) || !Array.isArray(value.egress_policies) || !Array.isArray(value.routes)) throw new AISubmissionError("AI_SUBMISSION_UNCERTAIN");
  const tasks = value.task_policies.map(raw => { if (!record(raw) || !ref.test(String(raw.reference)) || !positive(raw.policy_version)
    || !label(raw.task_type) || !ref.test(String(raw.purpose_ref)) || !ref.test(String(raw.output_schema_ref)) || !ref.test(String(raw.context_policy_ref)) || !Array.isArray(raw.parameter_fields) || raw.parameter_fields.length > 16) throw new AISubmissionError("AI_SUBMISSION_UNCERTAIN");
    const fields = raw.parameter_fields.map(field => { if (!record(field) || typeof field.name !== "string" || !/^[a-z][a-z0-9_]{0,63}$/.test(field.name) || !["STRING", "INTEGER", "BOOLEAN"].includes(String(field.value_type)) || typeof field.required !== "boolean" || (field.max_length !== null && !positive(field.max_length)) || (field.minimum !== null && !Number.isSafeInteger(field.minimum)) || (field.maximum !== null && !Number.isSafeInteger(field.maximum))) throw new AISubmissionError("AI_SUBMISSION_UNCERTAIN");
      const allowed = strings(field.allowed_values, /^.{1,4096}$/u); return Object.freeze({ name: field.name, value_type: field.value_type as AITaskParameterField["value_type"], required: field.required, max_length: field.max_length as number | null, minimum: field.minimum as number | null, maximum: field.maximum as number | null, allowed_values: allowed }); });
    return Object.freeze({ reference: raw.reference as string, policy_version: raw.policy_version as number, task_type: raw.task_type as string, purpose_ref: raw.purpose_ref as string, output_schema_ref: raw.output_schema_ref as string, context_policy_ref: raw.context_policy_ref as string, parameter_fields: Object.freeze(fields) }); });
  const egress = value.egress_policies.map(raw => { if (!record(raw) || !ref.test(String(raw.reference)) || !positive(raw.max_record_count, true) || !positive(raw.max_payload_bytes) || !positive(raw.max_input_tokens) || !positive(raw.max_retry_attempts) || !positive(raw.ttl_seconds)) throw new AISubmissionError("AI_SUBMISSION_UNCERTAIN");
    return Object.freeze({ reference: raw.reference as string, allowed_data_categories: strings(raw.allowed_data_categories, code), max_record_count: raw.max_record_count as number, max_payload_bytes: raw.max_payload_bytes as number, max_input_tokens: raw.max_input_tokens as number, max_retry_attempts: raw.max_retry_attempts as number, risk_codes: strings(raw.risk_codes, code), ttl_seconds: raw.ttl_seconds as number }); });
  const routes = value.routes.map(raw => { if (!record(raw) || !id(raw.provider_id) || !id(raw.model_id) || !label(raw.provider_display_name, 120) || !/^[a-z][a-z0-9-]{0,63}$/.test(String(raw.data_region)) || !label(raw.provider_model_key) || !label(raw.model_revision)) throw new AISubmissionError("AI_SUBMISSION_UNCERTAIN");
    return Object.freeze({ provider_id: raw.provider_id, model_id: raw.model_id, provider_display_name: raw.provider_display_name as string, data_region: raw.data_region as string, provider_model_key: raw.provider_model_key as string, model_revision: raw.model_revision as string }); });
  if (!tasks.length || !egress.length || new Set(tasks.map(item => item.reference)).size !== tasks.length || new Set(egress.map(item => item.reference)).size !== egress.length || new Set(routes.map(item => `${item.provider_id}:${item.model_id}`)).size !== routes.length) throw new AISubmissionError("AI_SUBMISSION_UNCERTAIN");
  return Object.freeze({ task_policies: Object.freeze(tasks), egress_policies: Object.freeze(egress), routes: Object.freeze(routes) });
}

export class AISubmissionClient {
  constructor(private readonly session: SessionClient, private readonly fetcher: typeof fetch = fetch, private readonly timeoutMs = 10_000) {
    if (!(session instanceof SessionClient) || !Number.isInteger(timeoutMs) || timeoutMs < 1 || timeoutMs > 30_000) throw new AISubmissionError("AI_SUBMISSION_INVALID_INPUT");
  }
  async options(projectId: string): Promise<AISubmissionOptions> {
    if (!id(projectId)) throw new AISubmissionError("AI_SUBMISSION_INVALID_INPUT");
    const controller = new AbortController(); const timer = window.setTimeout(() => controller.abort(), this.timeoutMs);
    try { const response = await this.fetcher(`/api/v1/projects/${projectId}/ai-task-options`, { method: "GET", credentials: "same-origin", cache: "no-store", redirect: "error", headers: { Accept: "application/json" }, signal: controller.signal });
      if (controller.signal.aborted || response.headers.get("content-type")?.split(";")[0].trim().toLowerCase() !== "application/json") throw new AISubmissionError("AI_SUBMISSION_UNCERTAIN");
      const result = envelope(await response.json(), response.status); if (response.status !== 200) throw mapError(response.status, result.error); return parseOptions(result.data);
    } catch (failure) { if (failure instanceof AISubmissionError) throw failure; throw new AISubmissionError("AI_SUBMISSION_UNCERTAIN"); }
    finally { window.clearTimeout(timer); }
  }
  async createPreview(projectId: string, input: AIEgressPreviewInput, idempotencyKey: string): Promise<AIEgressPreviewView> {
    key(idempotencyKey); const source_refs = inputRefs(input.source_refs);
    if (!id(projectId) || !record(input) || !ref.test(input.purpose_ref) || !id(input.provider_id) || !id(input.model_id) || !ref.test(input.minimal_payload_policy_ref) || !positive(input.max_payload_bytes) || !positive(input.max_input_tokens) || !positive(input.max_retry_attempts)) throw new AISubmissionError("AI_SUBMISSION_INVALID_INPUT");
    const body = JSON.stringify({ ...input, source_refs, operation_type: "AI_TASK" });
    return this.#write(() => this.session.postProjectAIEgressPreview(projectId, body, idempotencyKey), 201, data => {
      if (!record(data) || !id(data.preview_id) || data.project_id !== projectId || data.purpose_ref !== input.purpose_ref || data.operation_type !== "AI_TASK" || data.provider_id !== input.provider_id || data.model_id !== input.model_id || !id(data.provider_config_version_id) || !hash.test(String(data.preview_fingerprint)) || !hash.test(String(data.payload_fingerprint)) || !hash.test(String(data.source_refs_fingerprint)) || !positive(data.estimated_record_count, true) || !instant(data.created_at) || !instant(data.expires_at) || Date.parse(data.expires_at) <= Date.parse(data.created_at)) throw new AISubmissionError("AI_SUBMISSION_UNCERTAIN");
      return Object.freeze({ ...input, preview_id: data.preview_id, project_id: data.project_id as string, provider_config_version_id: data.provider_config_version_id, data_region: data.data_region as string, estimated_record_count: data.estimated_record_count, payload_fingerprint: data.payload_fingerprint as string, source_refs_fingerprint: data.source_refs_fingerprint as string, preview_fingerprint: data.preview_fingerprint as string, risk_codes: strings(data.risk_codes, code), created_at: data.created_at, expires_at: data.expires_at });
    });
  }
  async authorize(projectId: string, preview: AIEgressPreviewView, validUntil: string, idempotencyKey: string): Promise<AIEgressAuthorizationView> {
    key(idempotencyKey); if (!id(projectId) || !record(preview) || preview.project_id !== projectId || !id(preview.preview_id) || !hash.test(preview.preview_fingerprint) || !instant(validUntil) || Date.parse(validUntil) > Date.parse(preview.expires_at)) throw new AISubmissionError("AI_SUBMISSION_INVALID_INPUT");
    const body = JSON.stringify({ expected_preview_fingerprint: preview.preview_fingerprint, allowed_data_categories: preview.allowed_data_categories, max_record_count: preview.estimated_record_count, max_payload_bytes: preview.max_payload_bytes, max_input_tokens: preview.max_input_tokens, max_retry_attempts: preview.max_retry_attempts, valid_until: validUntil });
    return this.#write(() => this.session.postProjectAIEgressDecision(projectId, preview.preview_id, "authorize", body, '"v0"', idempotencyKey), 201, (data, response) => {
      if (!record(data) || !id(data.authorization_id) || data.preview_id !== preview.preview_id || data.project_id !== projectId || data.preview_fingerprint !== preview.preview_fingerprint || !id(data.approved_by) || !label(data.approved_role) || !instant(data.approved_at) || data.valid_until !== validUntil || data.state !== "AUTHORIZED" || data.etag !== '"v0"' || response.headers.get("etag") !== '"v0"') throw new AISubmissionError("AI_SUBMISSION_UNCERTAIN");
      return Object.freeze({ authorization_id: data.authorization_id, preview_id: data.preview_id as string, project_id: data.project_id as string, preview_fingerprint: data.preview_fingerprint as string, approved_by: data.approved_by, approved_role: data.approved_role as string, approved_at: data.approved_at, valid_until: data.valid_until, state: "AUTHORIZED" as const, etag: '"v0"' });
    });
  }
  async createTask(projectId: string, plan: AITaskPlanInput, refs: readonly AIInputRef[], authorization: AIEgressAuthorizationView, idempotencyKey: string): Promise<AICreatedTask> {
    key(idempotencyKey); const input_refs = inputRefs(refs); if (!id(projectId) || authorization.project_id !== projectId || authorization.state !== "AUTHORIZED" || !id(authorization.authorization_id)) throw new AISubmissionError("AI_SUBMISSION_INVALID_INPUT");
    const body = JSON.stringify({ ...plan, input_refs, egress_authorization_ref: authorization.authorization_id });
    return this.#write(() => this.session.postProjectAITaskCreate(projectId, body, idempotencyKey), 202, (data, response) => {
      if (!record(data) || !id(data.ai_task_id) || !id(data.job_id) || response.headers.get("location") !== `/api/v1/projects/${projectId}/ai-tasks/${data.ai_task_id}`) throw new AISubmissionError("AI_SUBMISSION_UNCERTAIN");
      return Object.freeze({ ai_task_id: data.ai_task_id, job_id: data.job_id });
    });
  }
  async revoke(projectId: string, authorization: AIEgressAuthorizationView, reason: string, idempotencyKey: string): Promise<void> {
    key(idempotencyKey); const summary = reason.normalize("NFKC").trim(); if (!id(projectId) || authorization.project_id !== projectId || authorization.state !== "AUTHORIZED" || !etag.test(authorization.etag) || !summary || summary.length > 1024 || /\p{C}/u.test(summary)) throw new AISubmissionError("AI_SUBMISSION_INVALID_INPUT");
    const body = JSON.stringify({ reason_code: "USER_REVOKED", reason_summary: summary });
    await this.#write(() => this.session.postProjectAIEgressDecision(projectId, authorization.authorization_id, "revoke", body, authorization.etag, idempotencyKey), 200, (data, response) => {
      if (!record(data) || data.authorization_id !== authorization.authorization_id || data.state !== "REVOKED" || data.etag !== '"v1"' || response.headers.get("etag") !== '"v1"' || !instant(data.revoked_at)) throw new AISubmissionError("AI_SUBMISSION_UNCERTAIN"); return undefined;
    });
  }
  async #write<T>(send: () => Promise<Response>, expectedStatus: number, parse: (data: unknown, response: Response) => T): Promise<T> {
    let response: Response; try { response = await send(); } catch (failure) { if (failure instanceof SessionClientError && (failure.code === "AUTH_RELOGIN_REQUIRED" || failure.code === "AUTH_CLIENT_BUSY")) throw new AISubmissionError(failure.code); throw new AISubmissionError("AI_SUBMISSION_UNCERTAIN"); }
    try { if (response.headers.get("content-type")?.split(";")[0].trim().toLowerCase() !== "application/json") throw new AISubmissionError("AI_SUBMISSION_UNCERTAIN"); const result = envelope(await response.json(), response.status); if (response.status !== expectedStatus) throw mapError(response.status, result.error); return parse(result.data, response); }
    catch (failure) { if (failure instanceof AISubmissionError) throw failure; throw new AISubmissionError("AI_SUBMISSION_UNCERTAIN"); }
  }
}
