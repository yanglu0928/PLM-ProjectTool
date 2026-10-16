/** Fixed OutlineVersion history reads; historical refs are not current eligibility. */
import type { OutlineReferenceRef, OutlineRequirementRef } from "./outlineVersionCreateClient";

export interface OutlineVersionSummary {
  readonly solution_outline_version_id: string;
  readonly solution_outline_id: string;
  readonly project_id: string;
  readonly version_no: number;
  readonly version_state: "DRAFT" | "IN_REVIEW" | "APPROVED" | "RETURNED" | "SUPERSEDED" | "RESTRICTED";
  readonly content_fingerprint: string;
  readonly declared_section_count: number;
  readonly declared_requirement_count: number;
  readonly declared_reference_count: number;
  readonly missing_declaration_count: number;
  readonly conflict_declaration_count: number;
  readonly supersedes_version_ref: string | null;
  readonly review_ref: string | null;
  readonly review_round_ref: string | null;
  readonly created_by: string;
  readonly created_at: string;
}
export interface OutlineVersionDetail extends OutlineVersionSummary {
  readonly section_ids: readonly string[];
  readonly requirement_refs: readonly OutlineRequirementRef[];
  readonly reference_refs: readonly OutlineReferenceRef[];
  readonly missing_declarations: readonly Record<string, unknown>[];
  readonly conflict_declarations: readonly Record<string, unknown>[];
}
export interface OutlineVersionPage {
  readonly items: readonly OutlineVersionSummary[];
  readonly next_cursor: string | null;
  readonly has_more: boolean;
}

const messages = {
  OUTLINE_VERSION_INVALID_INPUT: "项目、方案目录、版本或翻页参数无效。",
  AUTH_SESSION_EXPIRED: "会话已失效，请重新登录。",
  LICENSE_OPERATION_DENIED: "当前许可不允许读取方案版本。",
  RESOURCE_NOT_FOUND: "方案版本不存在或无权查看。",
  OUTLINE_VERSION_UNAVAILABLE: "暂时无法读取方案版本，请稍后重试。",
} as const;
export type OutlineVersionReadErrorCode = keyof typeof messages;
export class OutlineVersionReadError extends Error {
  constructor(readonly code: OutlineVersionReadErrorCode) {
    super(messages[code]); this.name = "OutlineVersionReadError";
  }
}

const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const digest = /^[0-9a-f]{64}$/;
const cursor = /^[A-Za-z0-9_-]{1,4096}\.[A-Za-z0-9_-]{43}$/;
const stamp = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$/;
const states = ["DRAFT", "IN_REVIEW", "APPROVED", "RETURNED", "SUPERSEDED", "RESTRICTED"];
const summaryFields = ["solution_outline_version_id", "solution_outline_id", "project_id",
  "version_no", "version_state", "content_fingerprint", "declared_section_count",
  "declared_requirement_count", "declared_reference_count", "missing_declaration_count",
  "conflict_declaration_count", "supersedes_version_ref", "review_ref", "review_round_ref",
  "created_by", "created_at"] as const;
const detailFields = [...summaryFields, "section_ids", "requirement_refs", "reference_refs",
  "missing_declarations", "conflict_declarations"] as const;
function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
function exact(value: Record<string, unknown>, fields: readonly string[]): boolean {
  return Object.keys(value).length === fields.length && fields.every(field => Object.hasOwn(value, field));
}
function id(value: unknown): value is string {
  return typeof value === "string" && uuid.test(value) && value !== "00000000-0000-0000-0000-000000000000";
}
function optionalId(value: unknown): value is string | null { return value === null || id(value); }
function count(value: unknown, maximum: number): value is number {
  return Number.isSafeInteger(value) && typeof value === "number" && value >= 0 && value <= maximum;
}
function instant(value: unknown): value is string {
  return typeof value === "string" && stamp.test(value) && Number.isFinite(Date.parse(value))
    && new Date(value).toISOString().slice(0, 19) === value.slice(0, 19);
}
function fail(): never { throw new OutlineVersionReadError("OUTLINE_VERSION_UNAVAILABLE"); }

function summary(value: unknown, project: string, outline: string, version?: string): OutlineVersionSummary {
  if (!record(value) || !exact(value, version === undefined ? summaryFields : detailFields)
    || !id(value.solution_outline_version_id)
    || version !== undefined && value.solution_outline_version_id !== version
    || value.project_id !== project || value.solution_outline_id !== outline
    || !count(value.version_no, Number.MAX_SAFE_INTEGER) || value.version_no < 1
    || !states.includes(value.version_state as string)
    || typeof value.content_fingerprint !== "string" || !digest.test(value.content_fingerprint)
    || !count(value.declared_section_count, 100)
    || !count(value.declared_requirement_count, 500)
    || !count(value.declared_reference_count, 500)
    || !count(value.missing_declaration_count, 100)
    || !count(value.conflict_declaration_count, 100)
    || !optionalId(value.supersedes_version_ref) || !optionalId(value.review_ref)
    || !optionalId(value.review_round_ref)
    || (value.review_ref === null) !== (value.review_round_ref === null)
    || !id(value.created_by) || !instant(value.created_at)) fail();
  return Object.freeze(Object.fromEntries(summaryFields.map(field => [field, value[field]]))) as unknown as OutlineVersionSummary;
}

export function parseOutlineVersionPage(value: unknown, project: string, outline: string,
                                        pageSize: number, previousCursor: string | null): OutlineVersionPage {
  if (!record(value) || !exact(value, ["items", "next_cursor", "has_more"])
    || !Array.isArray(value.items) || value.items.length > pageSize
    || typeof value.has_more !== "boolean"
    || value.has_more && (value.items.length === 0 || typeof value.next_cursor !== "string"
      || !cursor.test(value.next_cursor) || value.next_cursor === previousCursor)
    || !value.has_more && value.next_cursor !== null) fail();
  const items = value.items.map(item => summary(item, project, outline));
  if (items.some((item, index) => index > 0 && items[index - 1]!.version_no <= item.version_no)) fail();
  return Object.freeze({ items: Object.freeze(items), next_cursor: value.next_cursor as string | null,
    has_more: value.has_more });
}

export function parseOutlineVersionDetail(value: unknown, project: string, outline: string,
                                          version: string): OutlineVersionDetail {
  const base = summary(value, project, outline, version);
  if (!record(value) || !Array.isArray(value.section_ids)
    || value.section_ids.length !== base.declared_section_count
    || !value.section_ids.every(id) || new Set(value.section_ids).size !== value.section_ids.length
    || !Array.isArray(value.requirement_refs)
    || value.requirement_refs.length !== base.declared_requirement_count
    || !value.requirement_refs.every(item => record(item)
      && exact(item, ["requirement_id", "requirement_version_id"])
      && id(item.requirement_id) && id(item.requirement_version_id))
    || !Array.isArray(value.reference_refs)
    || value.reference_refs.length !== base.declared_reference_count
    || !value.reference_refs.every(item => record(item)
      && exact(item, ["scope", "reference_solution_id", "reference_version_id"])
      && ["PROJECT", "GLOBAL"].includes(item.scope as string)
      && id(item.reference_solution_id) && id(item.reference_version_id))
    || !Array.isArray(value.missing_declarations)
    || value.missing_declarations.length !== base.missing_declaration_count
    || !value.missing_declarations.every(record)
    || !Array.isArray(value.conflict_declarations)
    || value.conflict_declarations.length !== base.conflict_declaration_count
    || !value.conflict_declarations.every(record)) fail();
  return Object.freeze({ ...base,
    section_ids: Object.freeze([...value.section_ids]) as readonly string[],
    requirement_refs: Object.freeze(value.requirement_refs.map(item => Object.freeze({ ...item }))) as readonly OutlineRequirementRef[],
    reference_refs: Object.freeze(value.reference_refs.map(item => Object.freeze({ ...item }))) as readonly OutlineReferenceRef[],
    missing_declarations: Object.freeze(value.missing_declarations.map(item => Object.freeze({ ...item }))) as readonly Record<string, unknown>[],
    conflict_declarations: Object.freeze(value.conflict_declarations.map(item => Object.freeze({ ...item }))) as readonly Record<string, unknown>[],
  });
}

export class OutlineVersionReadClient {
  constructor(private readonly fetcher: typeof fetch = fetch,
              private readonly timeoutMs = 10_000) {}

  async list(project: string, outline: string, pageSize = 50,
             next: string | null = null): Promise<OutlineVersionPage> {
    if (!id(project) || !id(outline) || !Number.isSafeInteger(pageSize)
      || pageSize < 1 || pageSize > 100 || next !== null && !cursor.test(next)) {
      throw new OutlineVersionReadError("OUTLINE_VERSION_INVALID_INPUT");
    }
    const params = new URLSearchParams({ page_size: String(pageSize) });
    if (next !== null) params.set("cursor", next);
    const data = await this.get(`/api/v1/projects/${project}/solution-outlines/${outline}/versions?${params}`);
    return parseOutlineVersionPage(data, project, outline, pageSize, next);
  }

  async detail(project: string, outline: string, version: string): Promise<OutlineVersionDetail> {
    if (!id(project) || !id(outline) || !id(version)) {
      throw new OutlineVersionReadError("OUTLINE_VERSION_INVALID_INPUT");
    }
    const data = await this.get(
      `/api/v1/projects/${project}/solution-outlines/${outline}/versions/${version}`);
    return parseOutlineVersionDetail(data, project, outline, version);
  }

  private async get(path: string): Promise<unknown> {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      const fetcher = this.fetcher;
      const response = await fetcher(path, { method: "GET", credentials: "same-origin",
        cache: "no-store", redirect: "error", headers: { Accept: "application/json" },
        signal: controller.signal });
      if (controller.signal.aborted
        || response.headers.get("content-type")?.split(";")[0].trim().toLowerCase() !== "application/json"
        || response.headers.get("cache-control") !== "no-store") fail();
      const payload: unknown = await response.json();
      if (!record(payload) || !id(payload.trace_id)
        || response.headers.get("x-trace-id") !== payload.trace_id) fail();
      if (response.status !== 200) {
        const code = record(payload.error) ? payload.error.code : null;
        const statuses: Readonly<Record<string, number>> = {
          AUTH_SESSION_EXPIRED: 401, LICENSE_OPERATION_DENIED: 403,
          RESOURCE_NOT_FOUND: 404,
        };
        if (typeof code === "string" && statuses[code] === response.status) {
          throw new OutlineVersionReadError(code as OutlineVersionReadErrorCode);
        }
        fail();
      }
      if (!exact(payload, ["data", "trace_id"]) || response.headers.has("etag")) fail();
      return payload.data;
    } catch (error) {
      if (error instanceof OutlineVersionReadError) throw error;
      return fail();
    } finally { clearTimeout(timer); }
  }
}
