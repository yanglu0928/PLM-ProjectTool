import type { EvidenceScope } from "./evidenceViewerClient";

export interface EvidenceSummary {
  readonly evidence_id: string;
  readonly document_id: string;
  readonly document_version_id: string;
  readonly display_label: string;
  readonly display_excerpt: string | null;
  readonly eligibility_state: "CANDIDATE" | "ELIGIBLE" | "INELIGIBLE" | "REVOKED";
  readonly created_at: string;
}
export interface EvidencePage {
  readonly items: readonly EvidenceSummary[];
  readonly next_cursor: string | null;
  readonly has_more: boolean;
}

const messages = {
  EVIDENCE_INVALID_SCOPE: "证据范围或项目标识无效。",
  EVIDENCE_INVALID_CURSOR: "证据列表翻页位置无效，请重新读取。",
  AUTH_SESSION_EXPIRED: "会话已失效，请重新登录。",
  LICENSE_OPERATION_DENIED: "当前许可不允许查看证据。",
  RESOURCE_NOT_FOUND: "项目不存在或无权查看。",
  EVIDENCE_LIST_UNAVAILABLE: "暂时无法读取证据，请稍后重试。",
} as const;
export type EvidenceListErrorCode = keyof typeof messages;
export class EvidenceListError extends Error {
  constructor(readonly code: EvidenceListErrorCode) {
    super(messages[code]); this.name = "EvidenceListError";
  }
}
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const cursorPattern = /^[A-Za-z0-9_-]{1,768}\.[A-Za-z0-9_-]{43}$/;
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
function base(scope: EvidenceScope): string {
  if (!record(scope)) throw new EvidenceListError("EVIDENCE_INVALID_SCOPE");
  if (scope.kind === "GLOBAL" && Object.keys(scope).length === 1) return "/api/v1/global/evidence";
  if (scope.kind === "PROJECT" && Object.keys(scope).length === 2 && id(scope.projectId)) {
    return `/api/v1/projects/${scope.projectId}/evidence`;
  }
  throw new EvidenceListError("EVIDENCE_INVALID_SCOPE");
}
function parseSummary(value: unknown): EvidenceSummary {
  if (!record(value) || !id(value.evidence_id) || !id(value.document_id)
    || !id(value.document_version_id) || !label(value.display_label, 255)
    || (value.display_excerpt !== null && !label(value.display_excerpt, 500))
    || !["CANDIDATE", "ELIGIBLE", "INELIGIBLE", "REVOKED"].includes(String(value.eligibility_state))
    || typeof value.created_at !== "string"
    || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$/.test(value.created_at)
    || !Number.isFinite(Date.parse(value.created_at))) {
    throw new EvidenceListError("EVIDENCE_LIST_UNAVAILABLE");
  }
  return Object.freeze({ evidence_id: value.evidence_id, document_id: value.document_id,
    document_version_id: value.document_version_id, display_label: value.display_label,
    display_excerpt: value.display_excerpt,
    eligibility_state: value.eligibility_state as EvidenceSummary["eligibility_state"],
    created_at: value.created_at });
}

export class EvidenceListClient {
  constructor(private readonly fetcher: typeof fetch = fetch, private readonly timeoutMs = 10_000) {
    if (!Number.isInteger(timeoutMs) || timeoutMs < 1 || timeoutMs > 30_000) {
      throw new EvidenceListError("EVIDENCE_LIST_UNAVAILABLE");
    }
  }
  async list(scope: EvidenceScope, cursor: string | null = null): Promise<EvidencePage> {
    const path = base(scope);
    if (cursor !== null && (typeof cursor !== "string" || !cursorPattern.test(cursor))) {
      throw new EvidenceListError("EVIDENCE_INVALID_CURSOR");
    }
    const query = new URLSearchParams({ page_size: "50" });
    if (cursor !== null) query.set("cursor", cursor);
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      const response = await this.fetcher(`${path}?${query}`, { method: "GET", credentials: "same-origin",
        cache: "no-store", redirect: "error", headers: { Accept: "application/json" },
        signal: controller.signal });
      if (controller.signal.aborted || response.headers.get("content-type")?.split(";")[0].trim().toLowerCase()
          !== "application/json") throw new EvidenceListError("EVIDENCE_LIST_UNAVAILABLE");
      const payload: unknown = await response.json();
      if (!record(payload) || !id(payload.trace_id)) throw new EvidenceListError("EVIDENCE_LIST_UNAVAILABLE");
      if (response.status !== 200) {
        const code = record(payload.error) ? payload.error.code : null;
        const statuses: Record<string, number> = { AUTH_SESSION_EXPIRED: 401,
          LICENSE_OPERATION_DENIED: 403, RESOURCE_NOT_FOUND: 404 };
        if (typeof code === "string" && Object.hasOwn(statuses, code) && response.status === statuses[code]) {
          throw new EvidenceListError(code as EvidenceListErrorCode);
        }
        throw new EvidenceListError("EVIDENCE_LIST_UNAVAILABLE");
      }
      const data = payload.data;
      if (!record(data) || !Array.isArray(data.items) || data.items.length > 50
        || typeof data.has_more !== "boolean"
        || data.has_more && (data.items.length === 0 || typeof data.next_cursor !== "string"
          || !cursorPattern.test(data.next_cursor) || data.next_cursor === cursor)
        || !data.has_more && data.next_cursor !== null) {
        throw new EvidenceListError("EVIDENCE_LIST_UNAVAILABLE");
      }
      const items = data.items.map(parseSummary);
      if (new Set(items.map((item) => item.evidence_id)).size !== items.length) {
        throw new EvidenceListError("EVIDENCE_LIST_UNAVAILABLE");
      }
      return Object.freeze({ items: Object.freeze(items),
        next_cursor: data.has_more ? data.next_cursor as string : null, has_more: data.has_more });
    } catch (failure) {
      if (failure instanceof EvidenceListError) throw failure;
      throw new EvidenceListError("EVIDENCE_LIST_UNAVAILABLE");
    } finally { window.clearTimeout(timer); }
  }
}
