/** GLOBAL Reference reads expose historical fixed-source metadata, not current source eligibility. */
export interface GlobalReferenceSummary {
  readonly reference_solution_id: string; readonly reference_version_id: string;
  readonly scope: "GLOBAL"; readonly project_id: null; readonly name: string;
  readonly eligibility_state: "REFERENCE_ONLY" | "ELIGIBLE" | "RESTRICTED" | "REVOKED";
  readonly version_no: number; readonly version_state: "DRAFT";
  readonly created_at: string; readonly etag: string;
}
export interface GlobalReferenceDocumentRef {
  readonly document_id: string; readonly document_version_id: string;
}
export interface GlobalReferenceCurrent extends GlobalReferenceSummary {
  readonly eligibility_reason: string | null; readonly source_project_class: string;
  readonly deidentification_class: string; readonly applicability: Readonly<Record<string, unknown>>;
  readonly document_version_ids: readonly string[];
  readonly document_refs: readonly GlobalReferenceDocumentRef[];
  readonly evidence_ids: readonly string[]; readonly source_fingerprint: string;
  readonly content_fingerprint: string; readonly created_by: string;
  readonly version_created_by: string; readonly version_created_at: string;
}
export interface GlobalReferencePage {
  readonly items: readonly GlobalReferenceSummary[];
  readonly next_cursor: string | null; readonly has_more: boolean;
}

const messages = {
  GLOBAL_REFERENCE_INVALID_INPUT: "参考方案或翻页参数无效。",
  AUTH_SESSION_EXPIRED: "会话已失效，请重新登录。",
  LICENSE_OPERATION_DENIED: "当前许可不允许读取全局参考方案。",
  RESOURCE_NOT_FOUND: "全局参考方案不存在或无权查看。",
  GLOBAL_REFERENCE_UNAVAILABLE: "暂时无法读取全局参考方案，请稍后重试。",
} as const;
export type GlobalReferenceReadErrorCode = keyof typeof messages;
export class GlobalReferenceReadError extends Error {
  constructor(readonly code: GlobalReferenceReadErrorCode) {
    super(messages[code]); this.name = "GlobalReferenceReadError";
  }
}

const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const digest = /^[0-9a-f]{64}$/;
const etag = /^"v(0|[1-9][0-9]*)"$/;
const cursor = /^[A-Za-z0-9_-]{1,512}\.[A-Za-z0-9_-]{43}$/;
const stamp = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$/;
const summaryFields = ["reference_solution_id", "reference_version_id", "scope", "project_id", "name",
  "eligibility_state", "version_no", "version_state", "created_at", "etag"] as const;
const detailFields = [...summaryFields, "eligibility_reason", "source_project_class", "deidentification_class",
  "applicability", "document_version_ids", "document_refs", "evidence_ids", "source_fingerprint",
  "content_fingerprint", "created_by", "version_created_by", "version_created_at"] as const;

function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
function exact(value: Record<string, unknown>, fields: readonly string[]): boolean {
  return Object.keys(value).length === fields.length && fields.every(field => Object.hasOwn(value, field));
}
function id(value: unknown): value is string {
  return typeof value === "string" && uuid.test(value) && value !== "00000000-0000-0000-0000-000000000000";
}
function instant(value: unknown): value is string {
  return typeof value === "string" && stamp.test(value) && Number.isFinite(Date.parse(value))
    && new Date(value).toISOString().slice(0, 19) === value.slice(0, 19);
}
function label(value: unknown, max: number): value is string {
  return typeof value === "string" && value.length > 0 && value.length <= max
    && value.trim() === value && !/\p{C}/u.test(value);
}
function unavailable(): never { throw new GlobalReferenceReadError("GLOBAL_REFERENCE_UNAVAILABLE"); }

function summary(value: unknown, referenceId?: string, detail = false): GlobalReferenceSummary {
  if (!record(value) || !exact(value, detail ? detailFields : summaryFields)
    || !id(value.reference_solution_id)
    || referenceId !== undefined && value.reference_solution_id !== referenceId
    || !id(value.reference_version_id) || value.scope !== "GLOBAL" || value.project_id !== null
    || !label(value.name, 255)
    || !["REFERENCE_ONLY", "ELIGIBLE", "RESTRICTED", "REVOKED"].includes(value.eligibility_state as string)
    || !Number.isSafeInteger(value.version_no) || (value.version_no as number) < 1
    || value.version_state !== "DRAFT" || !instant(value.created_at)
    || typeof value.etag !== "string" || !etag.test(value.etag)) unavailable();
  return Object.freeze({ reference_solution_id: value.reference_solution_id as string,
    reference_version_id: value.reference_version_id as string, scope: "GLOBAL" as const,
    project_id: null, name: value.name as string,
    eligibility_state: value.eligibility_state as GlobalReferenceSummary["eligibility_state"],
    version_no: value.version_no as number, version_state: "DRAFT" as const,
    created_at: value.created_at as string, etag: value.etag as string });
}

function safeApplicability(value: unknown): Readonly<Record<string, unknown>> {
  if (!record(value) || new TextEncoder().encode(JSON.stringify(value)).length > 65_536) unavailable();
  let count = 0;
  const visit = (item: unknown, depth: number): unknown => {
    if (++count > 2000 || depth > 8) unavailable();
    if (item === null || typeof item === "boolean") return item;
    if (typeof item === "number" && Number.isFinite(item)) return item;
    if (typeof item === "string" && item.length <= 4096 && !/\p{C}/u.test(item)) return item;
    if (Array.isArray(item) && item.length <= 500) return Object.freeze(item.map(child => visit(child, depth + 1)));
    if (record(item) && Object.keys(item).length <= 500) {
      if (Object.keys(item).some(key => !/^[A-Za-z][A-Za-z0-9_.-]{0,63}$/.test(key)
        || ["__proto__", "constructor", "prototype", "script", "url", "href", "src"].includes(key.toLowerCase())
        || /^on[a-z]+$/i.test(key))) unavailable();
      return Object.freeze(Object.fromEntries(Object.entries(item).map(([key, child]) => [key, visit(child, depth + 1)])));
    }
    return unavailable();
  };
  return visit(value, 0) as Readonly<Record<string, unknown>>;
}

export function parseGlobalReferenceCurrent(value: unknown, referenceId: string): GlobalReferenceCurrent {
  const base = summary(value, referenceId, true);
  if (!record(value) || value.eligibility_reason !== null && !label(value.eligibility_reason, 1000)
    || !label(value.source_project_class, 128) || !label(value.deidentification_class, 128)
    || !Array.isArray(value.document_version_ids) || value.document_version_ids.length < 1
    || value.document_version_ids.length > 100 || !value.document_version_ids.every(id)
    || new Set(value.document_version_ids).size !== value.document_version_ids.length
    || !Array.isArray(value.document_refs) || value.document_refs.length !== value.document_version_ids.length
    || !value.document_refs.every((item, index) => record(item)
      && exact(item, ["document_id", "document_version_id"]) && id(item.document_id)
      && item.document_version_id === (value.document_version_ids as string[])[index])
    || !Array.isArray(value.evidence_ids) || value.evidence_ids.length > 500
    || !value.evidence_ids.every(id) || new Set(value.evidence_ids).size !== value.evidence_ids.length
    || typeof value.source_fingerprint !== "string" || !digest.test(value.source_fingerprint)
    || typeof value.content_fingerprint !== "string" || !digest.test(value.content_fingerprint)
    || !id(value.created_by) || !id(value.version_created_by) || !instant(value.version_created_at)) unavailable();
  return Object.freeze({ ...base, eligibility_reason: value.eligibility_reason as string | null,
    source_project_class: value.source_project_class as string,
    deidentification_class: value.deidentification_class as string,
    applicability: safeApplicability(value.applicability),
    document_version_ids: Object.freeze([...(value.document_version_ids as string[])]),
    document_refs: Object.freeze((value.document_refs as GlobalReferenceDocumentRef[])
      .map(item => Object.freeze({ ...item }))),
    evidence_ids: Object.freeze([...(value.evidence_ids as string[])]),
    source_fingerprint: value.source_fingerprint as string,
    content_fingerprint: value.content_fingerprint as string,
    created_by: value.created_by as string,
    version_created_by: value.version_created_by as string,
    version_created_at: value.version_created_at as string });
}

export function parseGlobalReferencePage(value: unknown, pageSize: number,
                                         previousCursor: string | null = null): GlobalReferencePage {
  if (!record(value) || !exact(value, ["items", "next_cursor", "has_more"])
    || !Array.isArray(value.items) || value.items.length > pageSize || typeof value.has_more !== "boolean"
    || value.has_more && (value.items.length === 0 || typeof value.next_cursor !== "string"
      || !cursor.test(value.next_cursor) || value.next_cursor === previousCursor)
    || !value.has_more && value.next_cursor !== null) unavailable();
  const items = value.items.map(item => summary(item));
  if (items.some((item, index) => index > 0
    && items[index - 1]!.reference_solution_id >= item.reference_solution_id)) unavailable();
  return Object.freeze({ items: Object.freeze(items), next_cursor: value.next_cursor as string | null,
    has_more: value.has_more });
}

export class GlobalReferenceReadClient {
  constructor(private readonly fetcher: typeof fetch = fetch, private readonly timeoutMs = 10_000) {}

  async list(pageSize = 50, next: string | null = null): Promise<GlobalReferencePage> {
    if (!Number.isSafeInteger(pageSize) || pageSize < 1 || pageSize > 100
      || next !== null && !cursor.test(next)) throw new GlobalReferenceReadError("GLOBAL_REFERENCE_INVALID_INPUT");
    const params = new URLSearchParams({ page_size: String(pageSize) });
    if (next !== null) params.set("cursor", next);
    return parseGlobalReferencePage(await this.get(`/api/v1/global/reference-solutions?${params}`), pageSize, next);
  }

  async current(referenceId: string): Promise<GlobalReferenceCurrent> {
    if (!id(referenceId)) throw new GlobalReferenceReadError("GLOBAL_REFERENCE_INVALID_INPUT");
    const resultEnvelope = await this.get(`/api/v1/global/reference-solutions/${referenceId}`, true);
    const { data, etag: header } = resultEnvelope as { data: unknown; etag: string };
    const result = parseGlobalReferenceCurrent(data, referenceId);
    if (header !== result.etag) unavailable();
    return result;
  }

  private async get(path: string, requireEtag = false): Promise<unknown> {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      const fetcher = this.fetcher;
      const response = await fetcher(path, { method: "GET", credentials: "same-origin", cache: "no-store",
        redirect: "error", headers: { Accept: "application/json" }, signal: controller.signal });
      if (controller.signal.aborted
        || response.headers.get("content-type")?.split(";")[0].trim().toLowerCase() !== "application/json") unavailable();
      const payload: unknown = await response.json();
      if (!record(payload) || !id(payload.trace_id)) unavailable();
      if (response.status !== 200) {
        const code = record(payload.error) ? payload.error.code : null;
        const statuses: Readonly<Record<string, number>> = { AUTH_SESSION_EXPIRED: 401,
          LICENSE_OPERATION_DENIED: 403, RESOURCE_NOT_FOUND: 404 };
        if (typeof code === "string" && statuses[code] === response.status) {
          throw new GlobalReferenceReadError(code as GlobalReferenceReadErrorCode);
        }
        unavailable();
      }
      if (!exact(payload, ["data", "trace_id"])) unavailable();
      if (!requireEtag) return payload.data;
      const header = response.headers.get("etag");
      if (header === null || !etag.test(header)) unavailable();
      return { data: payload.data, etag: header };
    } catch (error) {
      if (error instanceof GlobalReferenceReadError) throw error;
      return unavailable();
    } finally { clearTimeout(timer); }
  }
}
