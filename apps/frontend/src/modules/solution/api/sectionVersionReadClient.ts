/** Immutable SectionVersion history; fixed refs are not current source proof. */

export interface SectionRequirementRef {
  readonly requirement_id: string;
  readonly requirement_version_id: string;
}
export interface SectionStructuredSpecRef {
  readonly spec_series_id: string;
  readonly structured_solution_spec_id: string;
  readonly fit_rationale?: string;
}
export interface SectionVersionSummary {
  readonly solution_section_version_id: string;
  readonly solution_section_id: string;
  readonly project_id: string;
  readonly version_no: number;
  readonly version_state: "DRAFT" | "IN_REVIEW" | "APPROVED" | "RETURNED" | "SUPERSEDED" | "RESTRICTED";
  readonly title: string;
  readonly content_fingerprint: string;
  readonly declared_requirement_count: number;
  readonly declared_evidence_count: number;
  readonly spec_binding_state: "UNDECLARED" | "NONE_REQUIRED" | "FIXED_REFS";
  readonly declared_spec_count: number;
  readonly assumption_count: number;
  readonly exclusion_count: number;
  readonly supersedes_version_ref: string | null;
  readonly review_ref: string | null;
  readonly review_round_ref: string | null;
  readonly created_by: string;
  readonly created_at: string;
}
export interface SectionVersionDetail extends SectionVersionSummary {
  readonly content_document_version_ref: string | null;
  readonly content_artifact_ref: string | null;
  readonly requirement_refs: readonly SectionRequirementRef[];
  readonly evidence_ids: readonly string[];
  readonly spec_not_required_reason: string | null;
  readonly structured_spec_refs: readonly SectionStructuredSpecRef[];
  readonly assumptions: readonly Record<string, unknown>[];
  readonly exclusions: readonly Record<string, unknown>[];
}
export interface SectionVersionPage {
  readonly items: readonly SectionVersionSummary[];
  readonly next_cursor: string | null;
  readonly has_more: boolean;
}

const messages = {
  SECTION_VERSION_INVALID_INPUT: "项目、章节、版本或翻页参数无效。",
  AUTH_SESSION_EXPIRED: "会话已失效，请重新登录。",
  LICENSE_OPERATION_DENIED: "当前许可不允许读取章节版本。",
  RESOURCE_NOT_FOUND: "章节版本不存在或无权查看。",
  SECTION_VERSION_UNAVAILABLE: "暂时无法读取章节版本，请稍后重试。",
} as const;
export type SectionVersionReadErrorCode = keyof typeof messages;
export class SectionVersionReadError extends Error {
  constructor(readonly code: SectionVersionReadErrorCode) {
    super(messages[code]); this.name = "SectionVersionReadError";
  }
}

const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const digest = /^[0-9a-f]{64}$/;
const cursor = /^[A-Za-z0-9_-]{1,4096}\.[A-Za-z0-9_-]{43}$/;
const stamp = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$/;
const states = ["DRAFT", "IN_REVIEW", "APPROVED", "RETURNED", "SUPERSEDED", "RESTRICTED"];
const specStates = ["UNDECLARED", "NONE_REQUIRED", "FIXED_REFS"];
const summaryFields = ["solution_section_version_id", "solution_section_id", "project_id",
  "version_no", "version_state", "title", "content_fingerprint", "declared_requirement_count",
  "declared_evidence_count", "spec_binding_state", "declared_spec_count", "assumption_count",
  "exclusion_count", "supersedes_version_ref",
  "review_ref", "review_round_ref", "created_by", "created_at"] as const;
const detailFields = [...summaryFields, "content_document_version_ref", "content_artifact_ref",
  "requirement_refs", "evidence_ids", "assumptions", "exclusions",
  "spec_not_required_reason", "structured_spec_refs"] as const;
function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
function exact(value: Record<string, unknown>, fields: readonly string[]): boolean {
  return Object.keys(value).length === fields.length && fields.every(field => Object.hasOwn(value, field));
}
function id(value: unknown): value is string {
  return typeof value === "string" && uuid.test(value)
    && value !== "00000000-0000-0000-0000-000000000000";
}
function optionalId(value: unknown): value is string | null { return value === null || id(value); }
function count(value: unknown, maximum: number): value is number {
  return typeof value === "number" && Number.isSafeInteger(value) && value >= 0 && value <= maximum;
}
function instant(value: unknown): value is string {
  return typeof value === "string" && stamp.test(value) && Number.isFinite(Date.parse(value))
    && new Date(value).toISOString().slice(0, 19) === value.slice(0, 19);
}
function basis(value: unknown): value is string {
  return typeof value === "string" && value.length >= 1 && value.length <= 1000
    && value === value.trim() && value === value.normalize("NFC")
    && !/[\p{Cc}\p{Cs}]/u.test(value);
}
function fail(): never { throw new SectionVersionReadError("SECTION_VERSION_UNAVAILABLE"); }

function summary(value: unknown, project: string, section: string,
                 version?: string): SectionVersionSummary {
  if (!record(value) || !exact(value, version === undefined ? summaryFields : detailFields)
    || !id(value.solution_section_version_id)
    || version !== undefined && value.solution_section_version_id !== version
    || value.project_id !== project || value.solution_section_id !== section
    || !count(value.version_no, Number.MAX_SAFE_INTEGER) || value.version_no < 1
    || !states.includes(value.version_state as string)
    || typeof value.title !== "string" || value.title.length < 1 || value.title.length > 500
    || typeof value.content_fingerprint !== "string" || !digest.test(value.content_fingerprint)
    || !count(value.declared_requirement_count, 500)
    || !count(value.declared_evidence_count, 500)
    || !specStates.includes(value.spec_binding_state as string)
    || !count(value.declared_spec_count, 500)
    || value.spec_binding_state === "FIXED_REFS" && value.declared_spec_count === 0
    || value.spec_binding_state !== "FIXED_REFS" && value.declared_spec_count !== 0
    || !count(value.assumption_count, 100) || !count(value.exclusion_count, 100)
    || !optionalId(value.supersedes_version_ref) || !optionalId(value.review_ref)
    || !optionalId(value.review_round_ref)
    || (value.review_ref === null) !== (value.review_round_ref === null)
    || !id(value.created_by) || !instant(value.created_at)) fail();
  return Object.freeze(Object.fromEntries(summaryFields.map(field => [field, value[field]]))) as unknown as SectionVersionSummary;
}

export function parseSectionVersionPage(value: unknown, project: string, section: string,
                                        pageSize: number, previousCursor: string | null): SectionVersionPage {
  if (!record(value) || !exact(value, ["items", "next_cursor", "has_more"])
    || !Array.isArray(value.items) || value.items.length > pageSize
    || typeof value.has_more !== "boolean"
    || value.has_more && (value.items.length === 0 || typeof value.next_cursor !== "string"
      || !cursor.test(value.next_cursor) || value.next_cursor === previousCursor)
    || !value.has_more && value.next_cursor !== null) fail();
  const items = value.items.map(item => summary(item, project, section));
  if (items.some((item, index) => index > 0 && items[index - 1]!.version_no <= item.version_no)) fail();
  return Object.freeze({ items: Object.freeze(items), next_cursor: value.next_cursor as string | null,
    has_more: value.has_more });
}

export function parseSectionVersionDetail(value: unknown, project: string, section: string,
                                          version: string): SectionVersionDetail {
  const base = summary(value, project, section, version);
  if (!record(value) || !optionalId(value.content_document_version_ref)
    || !optionalId(value.content_artifact_ref)
    || (value.content_document_version_ref === null) === (value.content_artifact_ref === null)
    || !Array.isArray(value.requirement_refs)
    || value.requirement_refs.length !== base.declared_requirement_count
    || !value.requirement_refs.every(item => record(item)
      && exact(item, ["requirement_id", "requirement_version_id"])
      && id(item.requirement_id) && id(item.requirement_version_id))
    || new Set(value.requirement_refs.map(item => item.requirement_id)).size
      !== value.requirement_refs.length
    || !Array.isArray(value.evidence_ids)
    || value.evidence_ids.length !== base.declared_evidence_count
    || !value.evidence_ids.every(id) || new Set(value.evidence_ids).size !== value.evidence_ids.length
    || !Array.isArray(value.assumptions) || value.assumptions.length !== base.assumption_count
    || !value.assumptions.every(record)
    || !Array.isArray(value.exclusions) || value.exclusions.length !== base.exclusion_count
    || !value.exclusions.every(record)
    || !Array.isArray(value.structured_spec_refs)
    || value.structured_spec_refs.length !== base.declared_spec_count
    || !value.structured_spec_refs.every(item => record(item)
      && (exact(item, ["spec_series_id", "structured_solution_spec_id"])
        || exact(item, ["spec_series_id", "structured_solution_spec_id", "fit_rationale"]))
      && id(item.spec_series_id) && id(item.structured_solution_spec_id)
      && (!Object.hasOwn(item, "fit_rationale") || basis(item.fit_rationale)))
    || new Set(value.structured_spec_refs.map(item => item.spec_series_id)).size
      !== value.structured_spec_refs.length
    || new Set(value.structured_spec_refs.map(item => item.structured_solution_spec_id)).size
      !== value.structured_spec_refs.length
    || base.spec_binding_state === "NONE_REQUIRED" && !basis(value.spec_not_required_reason)
    || base.spec_binding_state !== "NONE_REQUIRED" && value.spec_not_required_reason !== null) fail();
  return Object.freeze({ ...base,
    content_document_version_ref: value.content_document_version_ref as string | null,
    content_artifact_ref: value.content_artifact_ref as string | null,
    requirement_refs: Object.freeze(value.requirement_refs.map(item => Object.freeze({ ...item }))) as readonly SectionRequirementRef[],
    evidence_ids: Object.freeze([...value.evidence_ids]) as readonly string[],
    spec_not_required_reason: value.spec_not_required_reason as string | null,
    structured_spec_refs: Object.freeze(value.structured_spec_refs.map(item => Object.freeze({ ...item }))) as readonly SectionStructuredSpecRef[],
    assumptions: Object.freeze(value.assumptions.map(item => Object.freeze({ ...item }))) as readonly Record<string, unknown>[],
    exclusions: Object.freeze(value.exclusions.map(item => Object.freeze({ ...item }))) as readonly Record<string, unknown>[],
  });
}

export class SectionVersionReadClient {
  constructor(private readonly fetcher: typeof fetch = fetch,
              private readonly timeoutMs = 10_000) {}

  async list(project: string, section: string, pageSize = 50,
             next: string | null = null): Promise<SectionVersionPage> {
    if (!id(project) || !id(section) || !Number.isSafeInteger(pageSize)
      || pageSize < 1 || pageSize > 100 || next !== null && !cursor.test(next)) {
      throw new SectionVersionReadError("SECTION_VERSION_INVALID_INPUT");
    }
    const params = new URLSearchParams({ page_size: String(pageSize) });
    if (next !== null) params.set("cursor", next);
    const data = await this.get(`/api/v1/projects/${project}/solution-sections/${section}/versions?${params}`);
    return parseSectionVersionPage(data, project, section, pageSize, next);
  }

  async detail(project: string, section: string, version: string): Promise<SectionVersionDetail> {
    if (!id(project) || !id(section) || !id(version)) {
      throw new SectionVersionReadError("SECTION_VERSION_INVALID_INPUT");
    }
    const data = await this.get(
      `/api/v1/projects/${project}/solution-sections/${section}/versions/${version}`);
    return parseSectionVersionDetail(data, project, section, version);
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
          AUTH_SESSION_EXPIRED: 401, LICENSE_OPERATION_DENIED: 403, RESOURCE_NOT_FOUND: 404,
        };
        if (typeof code === "string" && statuses[code] === response.status) {
          throw new SectionVersionReadError(code as SectionVersionReadErrorCode);
        }
        fail();
      }
      if (!exact(payload, ["data", "trace_id"]) || response.headers.has("etag")) fail();
      return payload.data;
    } catch (error) {
      if (error instanceof SectionVersionReadError) throw error;
      return fail();
    } finally { clearTimeout(timer); }
  }
}
