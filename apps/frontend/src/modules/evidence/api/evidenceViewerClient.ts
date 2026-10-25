/** Fixed Evidence Viewer metadata only; source bytes use the separate authorized content endpoint. */
export type EvidenceScope = { readonly kind: "PROJECT"; readonly projectId: string } | { readonly kind: "GLOBAL" };
export interface EvidenceViewerDescriptor {
  readonly evidence_id: string;
  readonly document_id: string;
  readonly document_version_id: string;
  readonly document_version_no: number;
  readonly detected_mime: string;
  readonly size_bytes: number;
  readonly locator: Readonly<Record<string, unknown>>;
  readonly precision: "DOCUMENT" | "PARSED_NODE";
  readonly display_label: string;
  readonly short_preview: string | null;
  readonly content_url: string;
}

const messages = {
  EVIDENCE_INVALID_SCOPE: "证据范围或项目标识无效。",
  EVIDENCE_INVALID_ID: "证据标识无效。",
  AUTH_SESSION_EXPIRED: "会话已失效，请重新登录。",
  LICENSE_OPERATION_DENIED: "当前许可不允许查看证据。",
  RESOURCE_NOT_FOUND: "证据或原文不存在，或您无权查看。",
  EVIDENCE_FINGERPRINT_MISMATCH: "原文完整性验证未通过，无法定位。",
  EVIDENCE_CLIENT_UNAVAILABLE: "暂时无法定位原文，请稍后重试。",
} as const;
export type EvidenceViewerErrorCode = keyof typeof messages;
export class EvidenceViewerClientError extends Error {
  constructor(readonly code: EvidenceViewerErrorCode) {
    super(messages[code]); this.name = "EvidenceViewerClientError";
  }
}

const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const mime = /^[A-Za-z0-9!#$&^_.+-]+\/[A-Za-z0-9!#$&^_.+-]+$/;
function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
function id(value: unknown): value is string {
  return typeof value === "string" && uuid.test(value)
    && value !== "00000000-0000-0000-0000-000000000000";
}
function label(value: unknown, max: number): value is string {
  return typeof value === "string" && value.length > 0 && value.length <= max
    && value.trim() === value && !/\p{C}/u.test(value);
}
function keys(value: Record<string, unknown>, allowed: readonly string[], required: readonly string[] = []): boolean {
  return Object.keys(value).every((key) => allowed.includes(key))
    && required.every((key) => Object.hasOwn(value, key));
}
function positive(value: unknown): value is number {
  return typeof value === "number" && Number.isSafeInteger(value) && value > 0;
}
function bounds(value: unknown): value is readonly number[] {
  return Array.isArray(value) && value.length === 4
    && value.every((item) => typeof item === "number" && Number.isFinite(item) && item >= 0 && item <= 1)
    && value[0] < value[2] && value[1] < value[3];
}
function cell(value: unknown): readonly [number, number] | null {
  if (typeof value !== "string") return null;
  const match = /^([A-Z]{1,3})([1-9][0-9]{0,6})$/.exec(value);
  if (!match) return null;
  let column = 0;
  for (const char of match[1]!) column = column * 26 + char.charCodeAt(0) - 64;
  const row = Number(match[2]);
  return column <= 16_384 && row <= 1_048_576 ? [column, row] : null;
}
function validLocator(value: unknown, nested = false): value is Record<string, unknown> {
  if (!record(value)) return false;
  switch (value.locator_type) {
    case "DOCUMENT": return keys(value, ["locator_type"]);
    case "PAGE": return keys(value, ["locator_type", "page_no", "bbox"], ["page_no"])
      && positive(value.page_no) && (!Object.hasOwn(value, "bbox") || bounds(value.bbox));
    case "TEXT_RANGE": return keys(value, ["locator_type", "page_no", "section_path", "start_offset",
      "end_offset", "normalized_fingerprint"], ["start_offset", "end_offset", "normalized_fingerprint"])
      && (Object.hasOwn(value, "page_no") !== Object.hasOwn(value, "section_path"))
      && (!Object.hasOwn(value, "page_no") || positive(value.page_no))
      && (!Object.hasOwn(value, "section_path") || label(value.section_path, 1024))
      && typeof value.start_offset === "number" && Number.isSafeInteger(value.start_offset)
      && value.start_offset >= 0 && positive(value.end_offset) && value.end_offset > value.start_offset
      && typeof value.normalized_fingerprint === "string" && /^[0-9a-f]{64}$/.test(value.normalized_fingerprint);
    case "SECTION": return keys(value, ["locator_type", "section_path"], ["section_path"])
      && label(value.section_path, 1024);
    case "PARAGRAPH": return keys(value, ["locator_type", "page_no", "paragraph_index", "stable_anchor"])
      && (Object.hasOwn(value, "paragraph_index") !== Object.hasOwn(value, "stable_anchor"))
      && (!Object.hasOwn(value, "page_no") || positive(value.page_no))
      && (!Object.hasOwn(value, "paragraph_index") || positive(value.paragraph_index))
      && (!Object.hasOwn(value, "stable_anchor") || label(value.stable_anchor, 256));
    case "TABLE_CELL": return keys(value, ["locator_type", "table_anchor", "row_no", "column_no"],
      ["table_anchor", "row_no", "column_no"]) && label(value.table_anchor, 256)
      && positive(value.row_no) && positive(value.column_no);
    case "SHEET_RANGE": return keys(value, ["locator_type", "sheet_name", "start_cell", "end_cell"],
      ["sheet_name", "start_cell", "end_cell"]) && label(value.sheet_name, 128)
      && cell(value.start_cell) !== null && cell(value.end_cell) !== null
      && cell(value.end_cell)![0] >= cell(value.start_cell)![0]
      && cell(value.end_cell)![1] >= cell(value.start_cell)![1];
    case "SLIDE_SHAPE": return keys(value, ["locator_type", "slide_no", "shape_id", "bounds"],
      ["slide_no", "shape_id"]) && positive(value.slide_no) && label(value.shape_id, 256)
      && (!Object.hasOwn(value, "bounds") || bounds(value.bounds));
    case "STRUCTURED_NODE": return !nested && keys(value,
      ["locator_type", "parse_record_id", "node_id", "source_locator"],
      ["parse_record_id", "node_id", "source_locator"])
      && id(value.parse_record_id) && label(value.node_id, 256)
      && validLocator(value.source_locator, true);
    default: return false;
  }
}
function base(scope: EvidenceScope): string {
  if (!record(scope)) throw new EvidenceViewerClientError("EVIDENCE_INVALID_SCOPE");
  if (scope.kind === "GLOBAL" && Object.keys(scope).length === 1) return "/api/v1/global";
  if (scope.kind === "PROJECT" && Object.keys(scope).length === 2 && id(scope.projectId)) {
    return `/api/v1/projects/${scope.projectId}`;
  }
  throw new EvidenceViewerClientError("EVIDENCE_INVALID_SCOPE");
}
export function parseEvidenceViewer(value: unknown, scope: EvidenceScope,
                                    evidenceId: string): EvidenceViewerDescriptor {
  if (!record(value) || value.evidence_id !== evidenceId || !id(value.document_id)
    || !id(value.document_version_id) || !positive(value.document_version_no)
    || typeof value.detected_mime !== "string" || !mime.test(value.detected_mime)
    || typeof value.size_bytes !== "number" || !Number.isSafeInteger(value.size_bytes)
    || value.size_bytes < 0 || value.size_bytes > 100_000_000
    || !validLocator(value.locator)
    || (value.precision !== "DOCUMENT" && value.precision !== "PARSED_NODE")
    || (value.precision === "DOCUMENT") !== (value.locator.locator_type === "DOCUMENT")
    || !label(value.display_label, 255)
    || (value.short_preview !== null && !label(value.short_preview, 500))) {
    throw new EvidenceViewerClientError("EVIDENCE_CLIENT_UNAVAILABLE");
  }
  const expected = `${base(scope)}/documents/${value.document_id}/versions/${value.document_version_id}/content`;
  if (value.content_url !== expected) throw new EvidenceViewerClientError("EVIDENCE_CLIENT_UNAVAILABLE");
  return Object.freeze({ evidence_id: evidenceId, document_id: value.document_id,
    document_version_id: value.document_version_id, document_version_no: value.document_version_no,
    detected_mime: value.detected_mime, size_bytes: value.size_bytes,
    locator: Object.freeze(value.locator), precision: value.precision,
    display_label: value.display_label, short_preview: value.short_preview,
    content_url: expected });
}

export class EvidenceViewerClient {
  constructor(private readonly fetcher: typeof fetch = fetch, private readonly timeoutMs = 10_000) {
    if (!Number.isInteger(timeoutMs) || timeoutMs < 1 || timeoutMs > 30_000) {
      throw new EvidenceViewerClientError("EVIDENCE_CLIENT_UNAVAILABLE");
    }
  }

  async get(scope: EvidenceScope, evidenceId: string): Promise<EvidenceViewerDescriptor> {
    const path = base(scope);
    if (!id(evidenceId)) throw new EvidenceViewerClientError("EVIDENCE_INVALID_ID");
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      // Invoke a browser-native fetch as a standalone function. Binding the
      // EvidenceViewerClient instance as its receiver fails before any request
      // is emitted in Windows Edge.
      const fetcher = this.fetcher;
      const response = await fetcher(`${path}/evidence/${evidenceId}/viewer`, {
        method: "GET", credentials: "same-origin", cache: "no-store", redirect: "error",
        headers: { Accept: "application/json" }, signal: controller.signal,
      });
      if (controller.signal.aborted || response.headers.get("content-type")?.split(";")[0].trim().toLowerCase()
          !== "application/json") throw new EvidenceViewerClientError("EVIDENCE_CLIENT_UNAVAILABLE");
      const payload: unknown = await response.json();
      if (!record(payload) || !id(payload.trace_id)) {
        throw new EvidenceViewerClientError("EVIDENCE_CLIENT_UNAVAILABLE");
      }
      if (response.status !== 200) {
        const code = record(payload.error) ? payload.error.code : null;
        const expected: Record<string, number> = { AUTH_SESSION_EXPIRED: 401,
          LICENSE_OPERATION_DENIED: 403, RESOURCE_NOT_FOUND: 404,
          EVIDENCE_FINGERPRINT_MISMATCH: 409 };
        if (typeof code === "string" && Object.hasOwn(expected, code) && response.status === expected[code]) {
          throw new EvidenceViewerClientError(code as EvidenceViewerErrorCode);
        }
        throw new EvidenceViewerClientError("EVIDENCE_CLIENT_UNAVAILABLE");
      }
      return parseEvidenceViewer(payload.data, scope, evidenceId);
    } catch (failure) {
      if (failure instanceof EvidenceViewerClientError) throw failure;
      throw new EvidenceViewerClientError("EVIDENCE_CLIENT_UNAVAILABLE");
    } finally { window.clearTimeout(timer); }
  }
}
