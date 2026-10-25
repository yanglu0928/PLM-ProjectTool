import { SessionClient, SessionClientError } from "@/modules/auth/api/sessionClient";

export interface GlobalEvidenceCreateInput {
  readonly document_id: string;
  readonly document_version_id: string;
  readonly locator: Readonly<{ locator_type: "DOCUMENT" }>;
  readonly display_label: string;
  readonly display_excerpt: string | null;
}
export interface GlobalEvidenceCreateReceipt {
  readonly evidence_id: string;
  readonly document_id: string;
  readonly document_version_id: string;
  readonly locator: Readonly<{ locator_type: "DOCUMENT" }>;
  readonly content_fingerprint: string;
  readonly display_label: string;
  readonly display_excerpt: string | null;
  readonly eligibility_state: "CANDIDATE";
  readonly created_at: string;
  readonly etag: '"v0"';
}
const messages = {
  EVIDENCE_CREATE_INVALID: "请核对固定文档、标签与整文档定位。",
  EVIDENCE_CREATE_UNCERTAIN: "创建结果无法确认；请保留原操作号并核对全局证据列表。",
  AUTH_RELOGIN_REQUIRED: "请重新登录后提交。", AUTH_CLIENT_BUSY: "会话正在处理其他操作。",
  AUTH_SESSION_EXPIRED: "会话已失效。", AUTH_CSRF_INVALID: "登录状态已变化。",
  RESOURCE_NOT_FOUND: "当前账户无权创建全局证据。",
  LICENSE_OPERATION_DENIED: "当前许可不允许创建全局证据。",
  VALIDATION_FAILED: "证据来源或标签不符合要求。",
  EVIDENCE_LOCATOR_INVALID: "当前仅支持整文档定位。",
  EVIDENCE_FINGERPRINT_MISMATCH: "固定文档内容校验失败。",
  CONFLICT_IDEMPOTENCY: "原操作号与当前内容冲突，请核对历史。",
  SYSTEM_UNAVAILABLE: "服务暂不可用，请核对操作历史。",
} as const;
export type GlobalEvidenceCreateErrorCode = keyof typeof messages;
export class GlobalEvidenceCreateError extends Error {
  readonly uncertain: boolean;
  constructor(readonly code: GlobalEvidenceCreateErrorCode) {
    super(messages[code]); this.name = "GlobalEvidenceCreateError";
    this.uncertain = code === "EVIDENCE_CREATE_UNCERTAIN" || code === "SYSTEM_UNAVAILABLE";
  }
}
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const sha256 = /^[0-9a-f]{64}$/;
const stamp = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$/;
function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
function exact(value: Record<string, unknown>, fields: readonly string[]): boolean {
  return Object.keys(value).length === fields.length && fields.every(field => Object.hasOwn(value, field));
}
function id(value: unknown): value is string { return typeof value === "string" && uuid.test(value)
  && value !== "00000000-0000-0000-0000-000000000000"; }
function label(value: unknown, max: number): value is string { return typeof value === "string"
  && value.length > 0 && value.length <= max && value === value.trim() && !/\p{C}/u.test(value); }
function invalid(): never { throw new GlobalEvidenceCreateError("EVIDENCE_CREATE_INVALID"); }
function uncertain(): never { throw new GlobalEvidenceCreateError("EVIDENCE_CREATE_UNCERTAIN"); }
export function normalizeGlobalEvidenceCreate(value: unknown): GlobalEvidenceCreateInput {
  if (!record(value) || !exact(value, ["document_id", "document_version_id", "locator",
    "display_label", "display_excerpt"])
    || !id(value.document_id) || !id(value.document_version_id)
    || !record(value.locator) || !exact(value.locator, ["locator_type"])
    || value.locator.locator_type !== "DOCUMENT" || !label(value.display_label, 255)
    || value.display_excerpt !== null && !label(value.display_excerpt, 500)) invalid();
  return Object.freeze({ document_id: value.document_id, document_version_id: value.document_version_id,
    locator: Object.freeze({ locator_type: "DOCUMENT" }), display_label: value.display_label,
    display_excerpt: value.display_excerpt });
}
export class GlobalEvidenceCreateClient {
  constructor(private readonly session: SessionClient) {
    if (!(session instanceof SessionClient)) invalid();
  }
  async create(input: GlobalEvidenceCreateInput, key: string): Promise<GlobalEvidenceCreateReceipt> {
    if (typeof key !== "string" || !/^[\x20-\x7e]{16,128}$/.test(key)) invalid();
    const body = normalizeGlobalEvidenceCreate(input);
    const identity = this.session.view;
    if (!identity || identity.password_change_required || !this.session.canSubmit
      || identity.deployment_role !== "DEPLOYMENT_ADMIN") {
      throw new GlobalEvidenceCreateError("RESOURCE_NOT_FOUND");
    }
    let response: Response;
    try { response = await this.session.postGlobalEvidenceCreate(JSON.stringify(body), key); }
    catch (failure) {
      if (failure instanceof SessionClientError && ["AUTH_RELOGIN_REQUIRED", "AUTH_CLIENT_BUSY"].includes(failure.code)) {
        throw new GlobalEvidenceCreateError(failure.code as "AUTH_RELOGIN_REQUIRED" | "AUTH_CLIENT_BUSY");
      }
      return uncertain();
    }
    try {
      if (response.headers.get("content-type")?.split(";")[0].trim().toLowerCase() !== "application/json") uncertain();
      const payload: unknown = await response.json();
      if (!record(payload) || !id(payload.trace_id)) uncertain();
      if (response.status !== 201) {
        const code = record(payload.error) ? payload.error.code : null;
        const statuses: Record<string, number> = {
          AUTH_SESSION_EXPIRED: 401, AUTH_CSRF_INVALID: 403, RESOURCE_NOT_FOUND: 404,
          LICENSE_OPERATION_DENIED: 403, VALIDATION_FAILED: 422, EVIDENCE_LOCATOR_INVALID: 422,
          EVIDENCE_FINGERPRINT_MISMATCH: 409, CONFLICT_IDEMPOTENCY: 409, SYSTEM_UNAVAILABLE: 503,
        };
        if (typeof code === "string" && statuses[code] === response.status) {
          throw new GlobalEvidenceCreateError(code as GlobalEvidenceCreateErrorCode);
        }
        uncertain();
      }
      if (!exact(payload, ["data", "trace_id"]) || !record(payload.data)) uncertain();
      const result = payload.data;
      if (!exact(result, ["evidence_id", "document_id", "document_version_id", "locator",
        "content_fingerprint", "display_label", "display_excerpt", "eligibility_state", "created_at", "etag"])
        || !id(result.evidence_id) || result.document_id !== body.document_id
        || result.document_version_id !== body.document_version_id
        || !record(result.locator) || !exact(result.locator, ["locator_type"])
        || result.locator.locator_type !== "DOCUMENT" || !sha256.test(String(result.content_fingerprint))
        || result.display_label !== body.display_label || result.display_excerpt !== body.display_excerpt
        || result.eligibility_state !== "CANDIDATE" || typeof result.created_at !== "string"
        || !stamp.test(result.created_at) || !Number.isFinite(Date.parse(result.created_at))
        || result.etag !== '"v0"' || response.headers.get("etag") !== '"v0"'
        || response.headers.get("location") !== `/api/v1/global/evidence/${result.evidence_id}`
        || !/(?:^|,)\s*no-store\s*(?:,|$)/i.test(response.headers.get("cache-control") ?? "")) uncertain();
      return Object.freeze({ ...result, locator: Object.freeze({ locator_type: "DOCUMENT" }) }) as unknown as GlobalEvidenceCreateReceipt;
    } catch (failure) {
      if (failure instanceof GlobalEvidenceCreateError) throw failure;
      return uncertain();
    }
  }
}
