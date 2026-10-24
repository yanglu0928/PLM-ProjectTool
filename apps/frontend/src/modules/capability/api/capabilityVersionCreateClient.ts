import { SessionClient, SessionClientError } from "@/modules/auth/api/sessionClient";

export interface CapabilityVersionItemDraft {
  readonly stable_item_id: string; readonly capability_code: string;
  readonly domain_name: string; readonly module_name: string; readonly feature_name: string;
  readonly name: string; readonly description: string; readonly boundary: string;
  readonly prerequisites: readonly string[]; readonly interface_refs: readonly string[];
  readonly document_refs: readonly { readonly document_id: string; readonly document_version_id: string }[];
  readonly evidence_refs: readonly string[];
  readonly item_state: "AVAILABLE" | "DEPRECATED" | "WITHDRAWN";
}
export interface CapabilityVersionCreateReceipt {
  readonly baseline_version_id: string; readonly baseline_id: string; readonly version_no: number;
  readonly state: "DRAFT"; readonly source_collection_ref: string;
  readonly content_fingerprint: string; readonly supersedes_version_ref: string | null;
  readonly created_at: string; readonly baseline_etag: string;
}
const messages = {
  CAP_VERSION_INVALID: "请核对基线版本条目、来源和证据引用。",
  CAP_VERSION_UNCERTAIN: "版本写入结果无法确认；请保留原操作号并核对版本列表。",
  AUTH_RELOGIN_REQUIRED: "请重新登录后提交。", AUTH_CLIENT_BUSY: "会话正在处理其他操作。",
  AUTH_SESSION_EXPIRED: "会话已失效。", AUTH_CSRF_INVALID: "登录状态已变化。",
  LICENSE_OPERATION_DENIED: "当前许可不允许创建能力版本。",
  RESOURCE_NOT_FOUND: "基线不存在或当前账户无权创建版本。",
  VALIDATION_FAILED: "版本条目不符合要求。", CAPABILITY_EVIDENCE_REQUIRED: "须先为同源证据完成人工资格确认。",
  CONFLICT_VERSION: "基线已变化，请刷新后重新确认。",
  CONFLICT_STATE: "当前基线或来源状态不允许写入。",
  CONFLICT_IDEMPOTENCY: "原操作号与当前内容冲突，请核对历史。",
  SYSTEM_UNAVAILABLE: "服务暂不可用，请核对版本列表。",
} as const;
export type CapabilityVersionCreateErrorCode = keyof typeof messages;
export class CapabilityVersionCreateError extends Error {
  readonly uncertain: boolean;
  constructor(readonly code: CapabilityVersionCreateErrorCode) {
    super(messages[code]); this.name = "CapabilityVersionCreateError";
    this.uncertain = code === "CAP_VERSION_UNCERTAIN";
  }
}
const idPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const codePattern = /^[A-Z][A-Z0-9_.-]{0,63}$/;
const etagPattern = /^"v(0|[1-9][0-9]*)"$/;
const sourcePattern = /^sha256:[0-9a-f]{64}$/;
const shaPattern = /^[0-9a-f]{64}$/;
const stampPattern = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$/;
const keyPattern = /^[\x20-\x7e]{16,128}$/;
function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
function exact(value: Record<string, unknown>, fields: readonly string[]): boolean {
  return Object.keys(value).length === fields.length && fields.every(field => Object.hasOwn(value, field));
}
function id(value: unknown): value is string {
  return typeof value === "string" && idPattern.test(value)
    && value !== "00000000-0000-0000-0000-000000000000";
}
function text(value: unknown, max: number): value is string {
  return typeof value === "string" && value.length >= 1 && value.length <= max
    && value === value.trim() && !/\p{C}/u.test(value);
}
function strings(value: unknown): value is readonly string[] {
  return Array.isArray(value) && value.length <= 100
    && value.every(item => text(item, 255)) && new Set(value).size === value.length;
}
function invalid(): never { throw new CapabilityVersionCreateError("CAP_VERSION_INVALID"); }
function uncertain(): never { throw new CapabilityVersionCreateError("CAP_VERSION_UNCERTAIN"); }
function validateItems(value: unknown): readonly CapabilityVersionItemDraft[] {
  if (!Array.isArray(value) || value.length < 1 || value.length > 500) invalid();
  const stable = new Set<string>(); const codes = new Set<string>();
  for (const item of value) {
    if (!record(item) || !exact(item, ["stable_item_id", "capability_code", "domain_name",
      "module_name", "feature_name", "name", "description", "boundary", "prerequisites",
      "interface_refs", "document_refs", "evidence_refs", "item_state"])
      || !id(item.stable_item_id) || stable.has(item.stable_item_id)
      || typeof item.capability_code !== "string" || !codePattern.test(item.capability_code)
      || codes.has(item.capability_code)
      || ![item.domain_name, item.module_name, item.feature_name, item.name].every(part => text(part, 255))
      || !text(item.description, 2000) || !text(item.boundary, 2000)
      || !strings(item.prerequisites) || !strings(item.interface_refs)
      || !["AVAILABLE", "DEPRECATED", "WITHDRAWN"].includes(String(item.item_state))
      || !Array.isArray(item.document_refs) || item.document_refs.length < 1
      || item.document_refs.length > 100 || !Array.isArray(item.evidence_refs)
      || item.evidence_refs.length < 1 || item.evidence_refs.length > 200) invalid();
    const docs = new Set<string>(); const versions = new Set<string>();
    for (const ref of item.document_refs) {
      if (!record(ref) || !exact(ref, ["document_id", "document_version_id"])
        || !id(ref.document_id) || !id(ref.document_version_id)
        || docs.has(ref.document_id) || versions.has(ref.document_version_id)) invalid();
      docs.add(ref.document_id); versions.add(ref.document_version_id);
    }
    if (item.evidence_refs.some(ref => !id(ref))
      || new Set(item.evidence_refs).size !== item.evidence_refs.length) invalid();
    stable.add(item.stable_item_id); codes.add(item.capability_code);
  }
  return value as readonly CapabilityVersionItemDraft[];
}
export class CapabilityVersionCreateClient {
  constructor(private readonly session: SessionClient) {
    if (!(session instanceof SessionClient)) invalid();
  }
  async create(baselineId: string, baselineEtag: string, items: readonly CapabilityVersionItemDraft[],
    key: string): Promise<CapabilityVersionCreateReceipt> {
    const baselineVersion = typeof baselineEtag === "string" && etagPattern.test(baselineEtag)
      ? Number(baselineEtag.slice(2, -1)) : null;
    if (!id(baselineId) || baselineVersion === null || !Number.isSafeInteger(baselineVersion)
      || baselineVersion >= Number.MAX_SAFE_INTEGER || typeof key !== "string" || !keyPattern.test(key)) invalid();
    const body = JSON.stringify({ items: validateItems(items) });
    const identity = this.session.view;
    if (!identity || identity.password_change_required || !this.session.canSubmit
      || identity.deployment_role !== "DEPLOYMENT_ADMIN") {
      throw new CapabilityVersionCreateError("RESOURCE_NOT_FOUND");
    }
    let response: Response;
    try { response = await this.session.postGlobalCapabilityVersionCreate(baselineId, body, baselineEtag, key); }
    catch (failure) {
      if (failure instanceof SessionClientError && (failure.code === "AUTH_RELOGIN_REQUIRED"
        || failure.code === "AUTH_CLIENT_BUSY")) throw new CapabilityVersionCreateError(failure.code);
      return uncertain();
    }
    try {
      if (response.headers.get("content-type")?.split(";")[0].trim().toLowerCase() !== "application/json") uncertain();
      const payload: unknown = await response.json();
      if (!record(payload) || !id(payload.trace_id)) uncertain();
      if (response.status !== 201) {
        const code = record(payload.error) ? payload.error.code : null;
        const statuses: Record<string, number> = { AUTH_SESSION_EXPIRED: 401, AUTH_CSRF_INVALID: 403,
          LICENSE_OPERATION_DENIED: 403, RESOURCE_NOT_FOUND: 404, VALIDATION_FAILED: 422,
          CAPABILITY_EVIDENCE_REQUIRED: 422, CONFLICT_VERSION: 409, CONFLICT_STATE: 409,
          CONFLICT_IDEMPOTENCY: 409, SYSTEM_UNAVAILABLE: 503 };
        if (typeof code === "string" && statuses[code] === response.status) {
          throw new CapabilityVersionCreateError(code as CapabilityVersionCreateErrorCode);
        }
        uncertain();
      }
      if (!exact(payload, ["data", "trace_id"]) || !record(payload.data)) uncertain();
      const data = payload.data;
      if (!exact(data, ["baseline_version_id", "baseline_id", "version_no", "state",
        "source_collection_ref", "content_fingerprint", "supersedes_version_ref",
        "created_at", "baseline_etag"])
        || !id(data.baseline_version_id) || data.baseline_id !== baselineId
        || !Number.isSafeInteger(data.version_no) || Number(data.version_no) < 1
        || data.state !== "DRAFT" || typeof data.source_collection_ref !== "string"
        || !sourcePattern.test(data.source_collection_ref)
        || typeof data.content_fingerprint !== "string" || !shaPattern.test(data.content_fingerprint)
        || data.supersedes_version_ref !== null && !id(data.supersedes_version_ref)
        || typeof data.created_at !== "string" || !stampPattern.test(data.created_at)
        || !Number.isFinite(Date.parse(data.created_at))
        || data.baseline_etag !== `"v${baselineVersion + 1}"`
        || response.headers.get("etag") !== data.baseline_etag
        || response.headers.get("location") !== `/api/v1/global/capability-baselines/${baselineId}/versions/${data.baseline_version_id}`
        || !/(?:^|,)\s*no-store\s*(?:,|$)/i.test(response.headers.get("cache-control") ?? "")) uncertain();
      return Object.freeze({ ...data }) as unknown as CapabilityVersionCreateReceipt;
    } catch (failure) {
      if (failure instanceof CapabilityVersionCreateError) throw failure;
      return uncertain();
    }
  }
}
