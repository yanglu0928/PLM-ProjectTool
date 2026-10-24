import { SessionClient, SessionClientError } from "@/modules/auth/api/sessionClient";

export interface CapabilitySource { readonly document_id: string; readonly document_version_id: string; }
export interface CapabilityCreateInput { readonly baseline_code: string; readonly name: string;
  readonly description: string | null; readonly source_documents: readonly CapabilitySource[]; }
export interface CapabilityCreateReceipt { readonly baseline_id: string; readonly baseline_code: string;
  readonly name: string; readonly description: string | null; readonly state: "ACTIVE";
  readonly source_collection_ref: string; readonly current_approved_version_ref: null;
  readonly created_at: string; readonly etag: '"v0"'; }
const messages = {
  CAPABILITY_CREATE_INVALID: "请核对基线代码、名称和可用的固定来源。",
  CAPABILITY_CREATE_UNCERTAIN: "创建结果无法确认；请保留原操作号并核对基线列表。",
  AUTH_RELOGIN_REQUIRED: "请重新登录后提交。", AUTH_CLIENT_BUSY: "会话正在处理其他操作。",
  AUTH_SESSION_EXPIRED: "会话已失效。", AUTH_CSRF_INVALID: "登录状态已变化。",
  LICENSE_OPERATION_DENIED: "当前许可不允许创建标准能力基线。",
  RESOURCE_NOT_FOUND: "当前账户无权创建标准能力基线。",
  VALIDATION_FAILED: "基线字段或固定来源不符合要求。",
  CONFLICT_IDEMPOTENCY: "原操作号与当前内容冲突，请核对历史。",
  CONFLICT_STATE: "当前来源状态不允许创建基线。",
  SYSTEM_UNAVAILABLE: "服务暂不可用，请核对操作历史。",
} as const;
export type CapabilityCreateErrorCode = keyof typeof messages;
export class CapabilityCreateError extends Error {
  readonly uncertain: boolean;
  constructor(readonly code: CapabilityCreateErrorCode) {
    super(messages[code]); this.name = "CapabilityCreateError";
    this.uncertain = code === "CAPABILITY_CREATE_UNCERTAIN";
  }
}
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const codePattern = /^[A-Z][A-Z0-9_.-]{0,63}$/;
const sourcePattern = /^sha256:[0-9a-f]{64}$/;
const stamp = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$/;
const keyPattern = /^[\x20-\x7e]{16,128}$/;
function id(value: unknown): value is string { return typeof value === "string" && uuid.test(value)
  && value !== "00000000-0000-0000-0000-000000000000"; }
function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
function exact(value: Record<string, unknown>, fields: readonly string[]): boolean {
  return Object.keys(value).length === fields.length && fields.every(field => Object.hasOwn(value, field));
}
function invalid(): never { throw new CapabilityCreateError("CAPABILITY_CREATE_INVALID"); }
function uncertain(): never { throw new CapabilityCreateError("CAPABILITY_CREATE_UNCERTAIN"); }
export function normalizeCapabilitySources(value: unknown): readonly CapabilitySource[] {
  if (!Array.isArray(value) || value.length < 1 || value.length > 500) invalid();
  const items = value.map(item => {
    if (!record(item) || !exact(item, ["document_id", "document_version_id"])
      || !id(item.document_id) || !id(item.document_version_id)) invalid();
    return Object.freeze({ document_id: item.document_id, document_version_id: item.document_version_id });
  });
  if (new Set(items.map(item => item.document_id)).size !== items.length
    || new Set(items.map(item => item.document_version_id)).size !== items.length) invalid();
  return Object.freeze(items.sort((a, b) => a.document_version_id.localeCompare(b.document_version_id)));
}
function normalize(input: CapabilityCreateInput): CapabilityCreateInput {
  if (!record(input) || !exact(input, ["baseline_code", "name", "description", "source_documents"])
    || typeof input.baseline_code !== "string" || !codePattern.test(input.baseline_code)
    || typeof input.name !== "string" || input.name.length < 1 || input.name.length > 255
    || input.name !== input.name.trim() || /\p{C}/u.test(input.name)
    || input.description !== null && (typeof input.description !== "string"
      || input.description.length < 1 || input.description.length > 2000
      || input.description !== input.description.trim() || /\p{C}/u.test(input.description))) invalid();
  return Object.freeze({ baseline_code: input.baseline_code, name: input.name,
    description: input.description, source_documents: normalizeCapabilitySources(input.source_documents) });
}
export class CapabilityCreateClient {
  constructor(private readonly session: SessionClient) {
    if (!(session instanceof SessionClient)) invalid();
  }
  async create(input: CapabilityCreateInput, key: string): Promise<CapabilityCreateReceipt> {
    if (typeof key !== "string" || !keyPattern.test(key)) invalid();
    const body = normalize(input);
    const identity = this.session.view;
    if (!identity || identity.password_change_required || !this.session.canSubmit
      || identity.deployment_role !== "DEPLOYMENT_ADMIN") {
      throw new CapabilityCreateError("RESOURCE_NOT_FOUND");
    }
    let response: Response;
    try { response = await this.session.postGlobalCapabilityBaselineCreate(JSON.stringify(body), key); }
    catch (failure) {
      if (failure instanceof SessionClientError && (failure.code === "AUTH_RELOGIN_REQUIRED"
        || failure.code === "AUTH_CLIENT_BUSY")) throw new CapabilityCreateError(failure.code);
      return uncertain();
    }
    try {
      if (response.headers.get("content-type")?.split(";")[0].trim().toLowerCase() !== "application/json") uncertain();
      const payload: unknown = await response.json();
      if (!record(payload) || !id(payload.trace_id)) uncertain();
      if (response.status !== 201) {
        const errorCode = record(payload.error) ? payload.error.code : null;
        const statuses: Record<string, number> = { AUTH_SESSION_EXPIRED: 401, AUTH_CSRF_INVALID: 403,
          LICENSE_OPERATION_DENIED: 403, RESOURCE_NOT_FOUND: 404, VALIDATION_FAILED: 422,
          CONFLICT_IDEMPOTENCY: 409, CONFLICT_STATE: 409, SYSTEM_UNAVAILABLE: 503 };
        if (typeof errorCode === "string" && statuses[errorCode] === response.status) {
          throw new CapabilityCreateError(errorCode as CapabilityCreateErrorCode);
        }
        uncertain();
      }
      if (!exact(payload, ["data", "trace_id"]) || !record(payload.data)) uncertain();
      const value = payload.data;
      if (!exact(value, ["baseline_id", "baseline_code", "name", "description", "state",
        "source_collection_ref", "current_approved_version_ref", "created_at", "etag"])
        || !id(value.baseline_id) || value.baseline_code !== body.baseline_code
        || value.name !== body.name || value.description !== body.description || value.state !== "ACTIVE"
        || typeof value.source_collection_ref !== "string" || !sourcePattern.test(value.source_collection_ref)
        || value.current_approved_version_ref !== null || typeof value.created_at !== "string"
        || !stamp.test(value.created_at) || !Number.isFinite(Date.parse(value.created_at))
        || value.etag !== '"v0"' || response.headers.get("etag") !== '"v0"'
        || response.headers.get("location") !== `/api/v1/global/capability-baselines/${value.baseline_id}`
        || !/(?:^|,)\s*no-store\s*(?:,|$)/i.test(response.headers.get("cache-control") ?? "")) uncertain();
      return Object.freeze({ ...value }) as unknown as CapabilityCreateReceipt;
    } catch (failure) {
      if (failure instanceof CapabilityCreateError) throw failure;
      return uncertain();
    }
  }
}
