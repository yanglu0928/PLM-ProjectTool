/** Authorized Document metadata only; content and storage locations never enter this client. */
export type DocumentScope = { readonly kind: "PROJECT"; readonly projectId: string } | { readonly kind: "GLOBAL" };

export interface DocumentView {
  readonly document_id: string;
  readonly scope: "PROJECT" | "GLOBAL";
  readonly category: "CONTRACTUAL" | "PROJECT_RECORD" | "STANDARD_CAPABILITY" | "REFERENCE_MATERIAL"
    | "TEMPLATE" | "GENERATED_ARTIFACT" | "OTHER";
  readonly subtype: string | null;
  readonly title: string;
  readonly display_name: string;
  readonly state: "ACTIVE" | "ARCHIVED";
  readonly latest_version_ref: string | null;
  readonly effective_version_ref: string | null;
  readonly created_at: string;
  readonly etag: string;
}

export interface DocumentPage {
  readonly items: readonly DocumentView[];
  readonly next_cursor: string | null;
  readonly has_more: boolean;
}

/** AVAILABLE version metadata only; no file locator, content, or download URL. */
export interface DocumentVersionView {
  readonly document_version_id: string;
  readonly version_no: number;
  readonly content_sha256: string;
  readonly size_bytes: number;
  readonly detected_mime: string;
  readonly availability_state: "AVAILABLE";
  readonly supersedes_version_ref: string | null;
  readonly created_at: string;
  readonly integrity_checked_at: string | null;
}

export interface DocumentVersionPage {
  readonly items: readonly DocumentVersionView[];
  readonly next_cursor: string | null;
  readonly has_more: boolean;
}

/** A fixed-version parse attempt is status metadata, not parsed content or Evidence. */
export interface DocumentParseRecordView {
  readonly parse_record_id: string;
  readonly parser_profile: string;
  readonly parser_version: string;
  readonly parse_state: "PENDING" | "RUNNING" | "SUCCEEDED" | "FAILED" | "CANCELLED";
  readonly attempt_no: number;
  readonly job_ref: string;
  readonly result_ref: string | null;
  readonly error_code: string | null;
  readonly retryable: boolean | null;
  readonly created_at: string;
  readonly started_at: string | null;
  readonly completed_at: string | null;
}

export interface DocumentParseRecordPage {
  readonly items: readonly DocumentParseRecordView[];
  readonly next_cursor: string | null;
  readonly has_more: boolean;
}

const messages = {
  DOCUMENT_INVALID_SCOPE: "文档范围或项目标识无效。",
  DOCUMENT_INVALID_ID: "文档标识无效。",
  DOCUMENT_INVALID_VERSION_ID: "文档版本标识无效。",
  DOCUMENT_INVALID_CURSOR: "文档列表翻页位置无效，请从第一页重新读取。",
  AUTH_SESSION_EXPIRED: "会话已失效，请重新登录。",
  LICENSE_OPERATION_DENIED: "当前许可不允许读取文档。",
  RESOURCE_NOT_FOUND: "文档不存在或无权查看。",
  DOCUMENT_CLIENT_UNAVAILABLE: "暂时无法读取文档，请稍后重试。",
} as const;
export type DocumentReadErrorCode = keyof typeof messages;
export class DocumentReadError extends Error {
  constructor(readonly code: DocumentReadErrorCode) {
    super(messages[code]); this.name = "DocumentReadError";
  }
}

const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const cursorToken = /^[A-Za-z0-9_-]{1,512}\.[A-Za-z0-9_-]{43}$/;
const parseCursorToken = /^[A-Za-z0-9_-]{1,1024}\.[A-Za-z0-9_-]{43}$/;
const strongEtag = /^"v(0|[1-9][0-9]*)"$/;
const sha256 = /^[0-9a-f]{64}$/;
const errorCode = /^[A-Z][A-Z0-9_]{0,63}$/;
const categories = new Set(["CONTRACTUAL", "PROJECT_RECORD", "STANDARD_CAPABILITY", "REFERENCE_MATERIAL",
  "TEMPLATE", "GENERATED_ARTIFACT", "OTHER"]);
function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
function identifier(value: unknown): value is string {
  return typeof value === "string" && uuid.test(value)
    && value !== "00000000-0000-0000-0000-000000000000";
}
function label(value: unknown, max: number): value is string {
  return typeof value === "string" && value.length > 0 && value.length <= max
    && value.trim() === value && !/\p{C}/u.test(value);
}
function instant(value: unknown): value is string {
  if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$/.test(value)) return false;
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) && new Date(parsed).toISOString().slice(0, 19) === value.slice(0, 19);
}
function safeVersion(value: string): boolean {
  return strongEtag.test(value) && Number.isSafeInteger(Number(value.slice(2, -1)));
}
function base(scope: DocumentScope): string {
  if (!record(scope)) throw new DocumentReadError("DOCUMENT_INVALID_SCOPE");
  if (scope.kind === "GLOBAL" && Object.keys(scope).length === 1) return "/api/v1/global/documents";
  if (scope.kind === "PROJECT" && Object.keys(scope).length === 2 && identifier(scope.projectId)) {
    return `/api/v1/projects/${scope.projectId}/documents`;
  }
  throw new DocumentReadError("DOCUMENT_INVALID_SCOPE");
}
export function parseDocument(value: unknown, scope: DocumentScope): DocumentView {
  if (!record(value) || !identifier(value.document_id) || value.scope !== scope.kind
    || typeof value.category !== "string" || !categories.has(value.category)
    || (value.subtype !== null && !label(value.subtype, 128))
    || (value.category === "OTHER" && value.subtype === null)
    || !label(value.title, 255) || !label(value.display_name, 255)
    || (value.state !== "ACTIVE" && value.state !== "ARCHIVED")
    || (value.latest_version_ref !== null && !identifier(value.latest_version_ref))
    || (value.effective_version_ref !== null && !identifier(value.effective_version_ref))
    || (value.effective_version_ref !== null && value.latest_version_ref === null)
    || !instant(value.created_at) || typeof value.etag !== "string" || !safeVersion(value.etag)) {
    throw new DocumentReadError("DOCUMENT_CLIENT_UNAVAILABLE");
  }
  return Object.freeze({ document_id: value.document_id, scope: scope.kind,
    category: value.category as DocumentView["category"], subtype: value.subtype,
    title: value.title, display_name: value.display_name, state: value.state,
    latest_version_ref: value.latest_version_ref, effective_version_ref: value.effective_version_ref,
    created_at: value.created_at, etag: value.etag });
}

export function parseDocumentVersion(value: unknown): DocumentVersionView {
  if (!record(value) || !identifier(value.document_version_id)
    || typeof value.version_no !== "number" || !Number.isSafeInteger(value.version_no) || value.version_no <= 0
    || typeof value.content_sha256 !== "string" || !sha256.test(value.content_sha256)
    || typeof value.size_bytes !== "number" || !Number.isSafeInteger(value.size_bytes) || value.size_bytes < 0
    || !label(value.detected_mime, 255) || value.availability_state !== "AVAILABLE"
    || (value.supersedes_version_ref !== null && !identifier(value.supersedes_version_ref))
    || !instant(value.created_at)
    || (value.integrity_checked_at !== null && !instant(value.integrity_checked_at))) {
    throw new DocumentReadError("DOCUMENT_CLIENT_UNAVAILABLE");
  }
  return Object.freeze({ document_version_id: value.document_version_id,
    version_no: value.version_no, content_sha256: value.content_sha256,
    size_bytes: value.size_bytes, detected_mime: value.detected_mime,
    availability_state: "AVAILABLE", supersedes_version_ref: value.supersedes_version_ref,
    created_at: value.created_at, integrity_checked_at: value.integrity_checked_at });
}

function parseDocumentParseRecord(value: unknown): DocumentParseRecordView {
  if (!record(value) || !identifier(value.parse_record_id)
    || !label(value.parser_profile, 128) || !label(value.parser_version, 64)
    || typeof value.parse_state !== "string"
    || !["PENDING", "RUNNING", "SUCCEEDED", "FAILED", "CANCELLED"].includes(value.parse_state)
    || typeof value.attempt_no !== "number" || !Number.isSafeInteger(value.attempt_no) || value.attempt_no <= 0
    || !identifier(value.job_ref)
    || (value.result_ref !== null && !identifier(value.result_ref))
    || (value.error_code !== null && (typeof value.error_code !== "string" || !errorCode.test(value.error_code)))
    || (value.retryable !== null && typeof value.retryable !== "boolean")
    || !instant(value.created_at)
    || (value.started_at !== null && !instant(value.started_at))
    || (value.completed_at !== null && !instant(value.completed_at))) {
    throw new DocumentReadError("DOCUMENT_CLIENT_UNAVAILABLE");
  }
  const state = value.parse_state;
  if (state === "PENDING" && (value.started_at !== null || value.completed_at !== null
      || value.result_ref !== null || value.error_code !== null || value.retryable !== null)
    || state === "RUNNING" && (value.started_at === null || value.completed_at !== null
      || value.result_ref !== null || value.error_code !== null || value.retryable !== null)
    || state === "SUCCEEDED" && (value.started_at === null || value.completed_at === null
      || value.result_ref === null || value.error_code !== null || value.retryable !== false)
    || state === "FAILED" && (value.started_at === null || value.completed_at === null
      || value.result_ref !== null || value.error_code === null || typeof value.retryable !== "boolean")
    || state === "CANCELLED" && (value.completed_at === null || value.result_ref !== null
      || value.error_code !== null || value.retryable !== false)
    || value.started_at !== null && value.completed_at !== null
      && Date.parse(value.completed_at as string) < Date.parse(value.started_at as string)) {
    throw new DocumentReadError("DOCUMENT_CLIENT_UNAVAILABLE");
  }
  return Object.freeze({ parse_record_id: value.parse_record_id, parser_profile: value.parser_profile,
    parser_version: value.parser_version, parse_state: state as DocumentParseRecordView["parse_state"],
    attempt_no: value.attempt_no, job_ref: value.job_ref, result_ref: value.result_ref,
    error_code: value.error_code, retryable: value.retryable, created_at: value.created_at,
    started_at: value.started_at, completed_at: value.completed_at });
}

export class DocumentReadClient {
  constructor(private readonly fetcher: typeof fetch = fetch, private readonly timeoutMs = 10_000) {
    if (!Number.isInteger(timeoutMs) || timeoutMs < 1 || timeoutMs > 30_000) {
      throw new DocumentReadError("DOCUMENT_CLIENT_UNAVAILABLE");
    }
  }

  async #get(path: string): Promise<{ data: unknown; etag: string | null }> {
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      const fetcher = this.fetcher;
      const response = await fetcher(path, { method: "GET", credentials: "same-origin", cache: "no-store",
        redirect: "error", headers: { Accept: "application/json" }, signal: controller.signal });
      if (controller.signal.aborted || response.headers.get("content-type")?.split(";")[0].trim().toLowerCase() !== "application/json") {
        throw new DocumentReadError("DOCUMENT_CLIENT_UNAVAILABLE");
      }
      const payload: unknown = await response.json();
      if (controller.signal.aborted || !record(payload) || !identifier(payload.trace_id)) {
        throw new DocumentReadError("DOCUMENT_CLIENT_UNAVAILABLE");
      }
      if (response.status !== 200) {
        const code = record(payload.error) ? payload.error.code : null;
        const expected: Record<string, number> = { AUTH_SESSION_EXPIRED: 401,
          LICENSE_OPERATION_DENIED: 403, RESOURCE_NOT_FOUND: 404 };
        if (typeof code === "string" && Object.hasOwn(expected, code) && response.status === expected[code]) {
          throw new DocumentReadError(code as DocumentReadErrorCode);
        }
        throw new DocumentReadError("DOCUMENT_CLIENT_UNAVAILABLE");
      }
      return { data: payload.data, etag: response.headers.get("etag") };
    } catch (failure) {
      if (failure instanceof DocumentReadError) throw failure;
      throw new DocumentReadError("DOCUMENT_CLIENT_UNAVAILABLE");
    } finally { window.clearTimeout(timer); }
  }

  async list(scope: DocumentScope, cursor: string | null = null): Promise<DocumentPage> {
    const path = base(scope);
    if (cursor !== null && (typeof cursor !== "string" || !cursorToken.test(cursor))) {
      throw new DocumentReadError("DOCUMENT_INVALID_CURSOR");
    }
    const query = new URLSearchParams({ page_size: "50" });
    if (cursor !== null) query.set("cursor", cursor);
    const { data } = await this.#get(`${path}?${query}`);
    if (!record(data) || !Array.isArray(data.items) || data.items.length > 50
      || typeof data.has_more !== "boolean"
      || (data.has_more && (data.items.length === 0 || typeof data.next_cursor !== "string"
        || !cursorToken.test(data.next_cursor) || data.next_cursor === cursor))
      || (!data.has_more && data.next_cursor !== null)) {
      throw new DocumentReadError("DOCUMENT_CLIENT_UNAVAILABLE");
    }
    const items = data.items.map((item) => parseDocument(item, scope));
    if (new Set(items.map((item) => item.document_id)).size !== items.length) {
      throw new DocumentReadError("DOCUMENT_CLIENT_UNAVAILABLE");
    }
    return Object.freeze({ items: Object.freeze(items),
      next_cursor: data.has_more ? data.next_cursor as string : null, has_more: data.has_more });
  }

  async get(scope: DocumentScope, documentId: string): Promise<DocumentView> {
    const path = base(scope);
    if (!identifier(documentId)) throw new DocumentReadError("DOCUMENT_INVALID_ID");
    const { data, etag } = await this.#get(`${path}/${documentId}`);
    const document = parseDocument(data, scope);
    if (document.document_id !== documentId || document.etag !== etag) {
      throw new DocumentReadError("DOCUMENT_CLIENT_UNAVAILABLE");
    }
    return document;
  }

  async listVersions(scope: DocumentScope, documentId: string,
                     cursor: string | null = null): Promise<DocumentVersionPage> {
    const path = base(scope);
    if (!identifier(documentId)) throw new DocumentReadError("DOCUMENT_INVALID_ID");
    if (cursor !== null && (typeof cursor !== "string" || !cursorToken.test(cursor))) {
      throw new DocumentReadError("DOCUMENT_INVALID_CURSOR");
    }
    const query = new URLSearchParams({ page_size: "50" });
    if (cursor !== null) query.set("cursor", cursor);
    const { data } = await this.#get(`${path}/${documentId}/versions?${query}`);
    if (!record(data) || !Array.isArray(data.items) || data.items.length > 50
      || typeof data.has_more !== "boolean"
      || (data.has_more && (data.items.length === 0 || typeof data.next_cursor !== "string"
        || !cursorToken.test(data.next_cursor) || data.next_cursor === cursor))
      || (!data.has_more && data.next_cursor !== null)) {
      throw new DocumentReadError("DOCUMENT_CLIENT_UNAVAILABLE");
    }
    const items = data.items.map(parseDocumentVersion);
    if (new Set(items.map((item) => item.document_version_id)).size !== items.length
      || items.some((item, index) => index > 0 && item.version_no >= items[index - 1]!.version_no)) {
      throw new DocumentReadError("DOCUMENT_CLIENT_UNAVAILABLE");
    }
    return Object.freeze({ items: Object.freeze(items),
      next_cursor: data.has_more ? data.next_cursor as string : null, has_more: data.has_more });
  }

  async getVersion(scope: DocumentScope, documentId: string,
                   versionId: string): Promise<DocumentVersionView> {
    const path = base(scope);
    if (!identifier(documentId)) throw new DocumentReadError("DOCUMENT_INVALID_ID");
    if (!identifier(versionId)) throw new DocumentReadError("DOCUMENT_INVALID_VERSION_ID");
    const { data } = await this.#get(`${path}/${documentId}/versions/${versionId}`);
    const version = parseDocumentVersion(data);
    if (version.document_version_id !== versionId) {
      throw new DocumentReadError("DOCUMENT_CLIENT_UNAVAILABLE");
    }
    return version;
  }

  async listParses(scope: DocumentScope, documentId: string, versionId: string,
                   cursor: string | null = null): Promise<DocumentParseRecordPage> {
    const path = base(scope);
    if (!identifier(documentId)) throw new DocumentReadError("DOCUMENT_INVALID_ID");
    if (!identifier(versionId)) throw new DocumentReadError("DOCUMENT_INVALID_VERSION_ID");
    if (cursor !== null && (typeof cursor !== "string" || !parseCursorToken.test(cursor))) {
      throw new DocumentReadError("DOCUMENT_INVALID_CURSOR");
    }
    const query = new URLSearchParams({ page_size: "50" });
    if (cursor !== null) query.set("cursor", cursor);
    const { data } = await this.#get(`${path}/${documentId}/versions/${versionId}/parses?${query}`);
    if (!record(data) || !Array.isArray(data.items) || data.items.length > 50
      || typeof data.has_more !== "boolean"
      || data.has_more && (data.items.length === 0 || typeof data.next_cursor !== "string"
        || !parseCursorToken.test(data.next_cursor) || data.next_cursor === cursor)
      || !data.has_more && data.next_cursor !== null) {
      throw new DocumentReadError("DOCUMENT_CLIENT_UNAVAILABLE");
    }
    const items = data.items.map(parseDocumentParseRecord);
    if (new Set(items.map((item) => item.parse_record_id)).size !== items.length) {
      throw new DocumentReadError("DOCUMENT_CLIENT_UNAVAILABLE");
    }
    return Object.freeze({ items: Object.freeze(items),
      next_cursor: data.has_more ? data.next_cursor as string : null, has_more: data.has_more });
  }

  /** Fixed same-origin attachment URL; server rechecks Session, scope, License and file integrity. */
  contentUrl(scope: DocumentScope, documentId: string, versionId: string): string {
    const path = base(scope);
    if (!identifier(documentId)) throw new DocumentReadError("DOCUMENT_INVALID_ID");
    if (!identifier(versionId)) throw new DocumentReadError("DOCUMENT_INVALID_VERSION_ID");
    return `${path}/${documentId}/versions/${versionId}/content`;
  }
}
