/** Authorized GLOBAL Capability projections; the server chooses history or current-approved visibility. */
export interface CapabilityBaseline {
  readonly baseline_id: string; readonly baseline_code: string; readonly name: string;
  readonly description: string | null; readonly state: "ACTIVE" | "ARCHIVED";
  readonly source_collection_ref: string; readonly current_approved_version_ref: string | null;
  readonly created_at: string; readonly updated_at: string; readonly etag: string;
}
export interface CapabilityVersion {
  readonly baseline_version_id: string; readonly baseline_id: string; readonly version_no: number;
  readonly state: "DRAFT" | "IN_REVIEW" | "APPROVED" | "RETURNED" | "SUPERSEDED" | "RESTRICTED";
  readonly source_collection_ref: string; readonly content_fingerprint: string;
  readonly declared_item_count: number; readonly declared_document_ref_count: number;
  readonly declared_evidence_ref_count: number; readonly supersedes_version_ref: string | null;
  readonly review_ref: string | null; readonly review_round_ref: string | null;
  readonly created_at: string;
}
export interface CapabilityItem {
  readonly capability_item_id: string; readonly baseline_version_id: string; readonly baseline_id: string;
  readonly ordinal: number; readonly capability_code: string; readonly domain_name: string;
  readonly module_name: string; readonly feature_name: string; readonly name: string;
  readonly description: string; readonly boundary: string; readonly prerequisites: readonly string[];
  readonly interface_refs: readonly string[]; readonly state: "AVAILABLE" | "DEPRECATED" | "WITHDRAWN";
  readonly document_version_refs: readonly string[]; readonly evidence_refs: readonly string[];
}
export interface CapabilityPage<T> { readonly items: readonly T[]; readonly next_cursor: string | null; readonly has_more: boolean; }
const messages = {
  CAPABILITY_INVALID_ID: "能力基线标识无效。", CAPABILITY_INVALID_CURSOR: "列表位置无效，请从第一页重新读取。",
  AUTH_SESSION_EXPIRED: "会话已失效，请重新登录。", LICENSE_OPERATION_DENIED: "当前许可不允许读取能力基线。",
  RESOURCE_NOT_FOUND: "内容不存在或当前账户无权查看。", CAPABILITY_READ_UNAVAILABLE: "暂时无法读取能力基线。",
} as const;
export type CapabilityReadErrorCode = keyof typeof messages;
export class CapabilityReadError extends Error {
  constructor(readonly code: CapabilityReadErrorCode) { super(messages[code]); this.name = "CapabilityReadError"; }
}
const idPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const cursorPattern = /^[A-Za-z0-9_-]{1,512}\.[A-Za-z0-9_-]{43}$/;
const shaPattern = /^[0-9a-f]{64}$/; const sourcePattern = /^sha256:[0-9a-f]{64}$/;
const etagPattern = /^"v(0|[1-9][0-9]*)"$/;
const datePattern = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$/;
function record(value: unknown): value is Record<string, unknown> { return typeof value === "object" && value !== null && !Array.isArray(value); }
function identifier(value: unknown): value is string { return typeof value === "string" && idPattern.test(value)
  && value !== "00000000-0000-0000-0000-000000000000"; }
function text(value: unknown, max = 4000): value is string { return typeof value === "string" && value.length > 0
  && value.length <= max && value.trim() === value && !/\p{C}/u.test(value); }
function content(value: unknown): value is string { return typeof value === "string" && value.length <= 100_000; }
function instant(value: unknown): value is string { return typeof value === "string" && datePattern.test(value)
  && Number.isFinite(Date.parse(value)) && new Date(value).toISOString().slice(0, 19) === value.slice(0, 19); }
function exact(value: Record<string, unknown>, fields: readonly string[]): boolean {
  return Object.keys(value).length === fields.length && fields.every(field => Object.hasOwn(value, field));
}
function unavailable(): never { throw new CapabilityReadError("CAPABILITY_READ_UNAVAILABLE"); }
function parseBaseline(value: unknown): CapabilityBaseline {
  const fields = ["baseline_id", "baseline_code", "name", "description", "state", "source_collection_ref",
    "current_approved_version_ref", "created_at", "updated_at", "etag"];
  if (!record(value) || !exact(value, fields) || !identifier(value.baseline_id)
    || !text(value.baseline_code, 64) || !text(value.name, 255)
    || (value.description !== null && !content(value.description))
    || !["ACTIVE", "ARCHIVED"].includes(String(value.state))
    || typeof value.source_collection_ref !== "string" || !sourcePattern.test(value.source_collection_ref)
    || value.current_approved_version_ref !== null && !identifier(value.current_approved_version_ref)
    || !instant(value.created_at) || !instant(value.updated_at)
    || Date.parse(value.updated_at) < Date.parse(value.created_at)
    || typeof value.etag !== "string" || !etagPattern.test(value.etag)) unavailable();
  return Object.freeze({ ...value }) as unknown as CapabilityBaseline;
}
export function parseVersion(value: unknown, baselineId: string): CapabilityVersion {
  const fields = ["baseline_version_id", "baseline_id", "version_no", "state", "source_collection_ref",
    "content_fingerprint", "declared_item_count", "declared_document_ref_count", "declared_evidence_ref_count",
    "supersedes_version_ref", "review_ref", "review_round_ref", "created_at"];
  if (!record(value) || !exact(value, fields) || !identifier(value.baseline_version_id)
    || value.baseline_id !== baselineId || !Number.isSafeInteger(value.version_no) || Number(value.version_no) < 1
    || !["DRAFT", "IN_REVIEW", "APPROVED", "RETURNED", "SUPERSEDED", "RESTRICTED"].includes(String(value.state))
    || typeof value.source_collection_ref !== "string" || !sourcePattern.test(value.source_collection_ref)
    || typeof value.content_fingerprint !== "string" || !shaPattern.test(value.content_fingerprint)
    || [value.declared_item_count, value.declared_document_ref_count, value.declared_evidence_ref_count]
      .some(number => !Number.isSafeInteger(number) || Number(number) < 0)
    || [value.supersedes_version_ref, value.review_ref, value.review_round_ref]
      .some(ref => ref !== null && !identifier(ref)) || !instant(value.created_at)) unavailable();
  return Object.freeze({ ...value }) as unknown as CapabilityVersion;
}
export function parseItem(value: unknown, baselineId: string, versionId: string): CapabilityItem {
  const fields = ["capability_item_id", "baseline_version_id", "baseline_id", "ordinal", "capability_code",
    "domain_name", "module_name", "feature_name", "name", "description", "boundary", "prerequisites",
    "interface_refs", "state", "document_version_refs", "evidence_refs"];
  if (!record(value) || !exact(value, fields) || !identifier(value.capability_item_id)
    || value.baseline_id !== baselineId || value.baseline_version_id !== versionId
    || !Number.isSafeInteger(value.ordinal) || Number(value.ordinal) < 0
    || ![value.capability_code, value.domain_name, value.module_name, value.feature_name,
      value.name, value.description, value.boundary].every(item => content(item))
    || !["AVAILABLE", "DEPRECATED", "WITHDRAWN"].includes(String(value.state))
    || !Array.isArray(value.prerequisites) || value.prerequisites.some(item => !content(item))
    || !Array.isArray(value.interface_refs) || value.interface_refs.some(item => !content(item))
    || !Array.isArray(value.document_version_refs) || value.document_version_refs.some(item => !identifier(item))
    || !Array.isArray(value.evidence_refs) || value.evidence_refs.some(item => !identifier(item))) unavailable();
  return Object.freeze({ ...value }) as unknown as CapabilityItem;
}
export class CapabilityReadClient {
  constructor(private readonly fetcher: typeof fetch = fetch, private readonly timeoutMs = 10_000) {
    if (!Number.isInteger(timeoutMs) || timeoutMs < 1 || timeoutMs > 30_000) unavailable();
  }
  async #get(path: string): Promise<unknown> {
    const controller = new AbortController(); const timer = window.setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      const fetcher = this.fetcher;
      const response = await fetcher(path, { method: "GET", credentials: "same-origin", cache: "no-store",
        redirect: "error", headers: { Accept: "application/json" }, signal: controller.signal });
      if (controller.signal.aborted || response.headers.get("content-type")?.split(";")[0].trim().toLowerCase()
        !== "application/json") unavailable();
      const payload: unknown = await response.json();
      if (!record(payload) || !identifier(payload.trace_id)) unavailable();
      if (response.status !== 200) {
        const code = record(payload.error) ? payload.error.code : null;
        const statuses: Record<string, number> = { AUTH_SESSION_EXPIRED: 401, LICENSE_OPERATION_DENIED: 403,
          RESOURCE_NOT_FOUND: 404 };
        if (typeof code === "string" && Object.hasOwn(statuses, code) && statuses[code] === response.status) {
          throw new CapabilityReadError(code as CapabilityReadErrorCode);
        }
        unavailable();
      }
      if (!exact(payload, ["data", "trace_id"])) unavailable();
      return payload.data;
    } catch (failure) {
      if (failure instanceof CapabilityReadError) throw failure;
      return unavailable();
    } finally { window.clearTimeout(timer); }
  }
  #page<T>(value: unknown, cursor: string | null, key: (item: T) => string,
           parse: (item: unknown) => T): CapabilityPage<T> {
    if (!record(value) || !exact(value, ["items", "next_cursor", "has_more"])
      || !Array.isArray(value.items) || value.items.length > 50 || typeof value.has_more !== "boolean"
      || value.has_more && (value.items.length === 0 || typeof value.next_cursor !== "string"
        || !cursorPattern.test(value.next_cursor) || value.next_cursor === cursor)
      || !value.has_more && value.next_cursor !== null) unavailable();
    const items = value.items.map(parse);
    if (new Set(items.map(key)).size !== items.length) unavailable();
    return Object.freeze({ items: Object.freeze(items), next_cursor: value.next_cursor as string | null,
      has_more: value.has_more });
  }
  #cursor(value: string | null): string {
    if (value !== null && (typeof value !== "string" || !cursorPattern.test(value))) {
      throw new CapabilityReadError("CAPABILITY_INVALID_CURSOR");
    }
    const query = new URLSearchParams({ page_size: "50" }); if (value !== null) query.set("cursor", value);
    return `?${query}`;
  }
  listBaselines(cursor: string | null = null): Promise<CapabilityPage<CapabilityBaseline>> {
    return this.#get(`/api/v1/global/capability-baselines${this.#cursor(cursor)}`)
      .then(data => this.#page(data, cursor, item => item.baseline_id, parseBaseline));
  }
  async getBaseline(baselineId: string): Promise<CapabilityBaseline> {
    if (!identifier(baselineId)) throw new CapabilityReadError("CAPABILITY_INVALID_ID");
    const value = parseBaseline(await this.#get(`/api/v1/global/capability-baselines/${baselineId}`));
    if (value.baseline_id !== baselineId) unavailable(); return value;
  }
  listVersions(baselineId: string, cursor: string | null = null): Promise<CapabilityPage<CapabilityVersion>> {
    if (!identifier(baselineId)) throw new CapabilityReadError("CAPABILITY_INVALID_ID");
    return this.#get(`/api/v1/global/capability-baselines/${baselineId}/versions${this.#cursor(cursor)}`)
      .then(data => this.#page(data, cursor, item => item.baseline_version_id,
        value => parseVersion(value, baselineId)));
  }
  async getVersion(baselineId: string, versionId: string): Promise<CapabilityVersion> {
    if (!identifier(baselineId) || !identifier(versionId)) throw new CapabilityReadError("CAPABILITY_INVALID_ID");
    const value = parseVersion(await this.#get(
      `/api/v1/global/capability-baselines/${baselineId}/versions/${versionId}`), baselineId);
    if (value.baseline_version_id !== versionId) unavailable(); return value;
  }
  listItems(baselineId: string, versionId: string,
            cursor: string | null = null): Promise<CapabilityPage<CapabilityItem>> {
    if (!identifier(baselineId) || !identifier(versionId)) throw new CapabilityReadError("CAPABILITY_INVALID_ID");
    return this.#get(`/api/v1/global/capability-baselines/${baselineId}/versions/${versionId}/items${this.#cursor(cursor)}`)
      .then(data => this.#page(data, cursor, item => item.capability_item_id,
        value => parseItem(value, baselineId, versionId)));
  }
}
