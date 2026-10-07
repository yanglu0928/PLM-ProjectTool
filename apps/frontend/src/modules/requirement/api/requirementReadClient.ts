export type RequirementState = "ACTIVE" | "DEFERRED" | "REJECTED" | "ARCHIVED";
export type RequirementVersionState = "DRAFT" | "IN_REVIEW" | "APPROVED" | "RETURNED" | "SUPERSEDED" | "RESTRICTED";
export type RequirementClassification = "STANDARD_FUNCTION" | "NONSTANDARD_FUNCTION" | "DIFFERENCE" | "PENDING_CONFIRMATION";
export type RequirementSourceType = "APPROVED_SURVEY_CONCLUSION" | "CONFIRMED_HANDOVER" | "HUMAN_DECISION" | "PROJECT_EVIDENCE";
export type RequirementCursor = string & { readonly __family: "requirements" };
export type RequirementVersionCursor = string & { readonly __family: "requirement-versions" };

export interface RequirementView {
  readonly requirement_id: string; readonly project_id: string; readonly requirement_code: string;
  readonly state: RequirementState; readonly current_approved_version_ref: string | null;
  readonly created_by: string; readonly created_at: string; readonly updated_by: string | null;
  readonly updated_at: string; readonly etag: string;
}
export interface RequirementVersionSummary {
  readonly requirement_version_id: string; readonly requirement_id: string; readonly project_id: string;
  readonly version_no: number; readonly state: RequirementVersionState; readonly title: string | null;
  readonly domain_name: string; readonly priority: "LOW" | "MEDIUM" | "HIGH" | "URGENT";
  readonly risk: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL"; readonly classification: RequirementClassification;
  readonly content_fingerprint: string; readonly declared_counts: RequirementDeclaredCounts;
  readonly supersedes_version_ref: string | null; readonly review_ref: string | null;
  readonly review_round_ref: string | null; readonly created_by: string; readonly created_at: string;
}
export interface RequirementDeclaredCounts {
  readonly sources: number; readonly acceptance_criteria: number; readonly capability_assessments: number;
  readonly assumptions: number; readonly exclusions: number; readonly dependencies: number; readonly ai_tasks: number;
}
export interface RequirementSourceView {
  readonly ordinal: number; readonly source_type: RequirementSourceType; readonly source_object_id: string;
  readonly source_version_ref: string | null;
  readonly evidence_refs: readonly { readonly evidence_id: string; readonly ordinal: number }[];
}
export interface RequirementAcceptanceView {
  readonly ordinal: number; readonly observable_result: string; readonly verification_method: string;
  readonly required_data: string; readonly required_environment: string; readonly evidence_requirement: string;
}
export interface RequirementCapabilityAssessmentView {
  readonly ordinal: number; readonly baseline_version_id: string; readonly capability_item_id: string;
  readonly match_type: "DIRECT" | "PARTIAL" | "NONE" | "UNKNOWN"; readonly fit_gap: string;
  readonly constraints_text: string; readonly assessor_kind: "HUMAN"; readonly assessed_by: string | null;
  readonly assessed_at: string; readonly confirmation_state: "CANDIDATE" | "CONFIRMED" | "REJECTED";
  readonly evidence_refs: readonly { readonly evidence_id: string; readonly evidence_role: string; readonly ordinal: number }[];
}
export interface RequirementTextItem { readonly ordinal: number; readonly text: string; }
export interface RequirementVersionView extends RequirementVersionSummary {
  readonly statement: string; readonly rationale: string; readonly sources: readonly RequirementSourceView[];
  readonly acceptance_criteria: readonly RequirementAcceptanceView[];
  readonly capability_assessments: readonly RequirementCapabilityAssessmentView[];
  readonly assumptions: readonly RequirementTextItem[]; readonly exclusions: readonly RequirementTextItem[];
  readonly dependencies: readonly RequirementTextItem[];
  readonly ai_tasks: readonly { readonly ai_task_id: string; readonly ordinal: number }[];
}
export interface RequirementPage<T, C extends string> {
  readonly items: readonly T[]; readonly next_cursor: C | null; readonly has_more: boolean;
}

const messages = {
  REQUIREMENT_READ_INVALID_INPUT: "项目、需求、版本或翻页参数无效。",
  AUTH_SESSION_EXPIRED: "会话已失效，请重新登录。",
  LICENSE_OPERATION_DENIED: "当前许可不允许读取项目需求。",
  RESOURCE_NOT_FOUND: "需求不存在，或当前账户无权查看。",
  PROJECT_ARCHIVED: "项目已归档，当前需求不可读取。",
  REQUIREMENT_READ_UNAVAILABLE: "暂时无法读取项目需求，请稍后重试。",
} as const;
export type RequirementReadErrorCode = keyof typeof messages;
export class RequirementReadError extends Error {
  constructor(readonly code: RequirementReadErrorCode) { super(messages[code]); this.name = "RequirementReadError"; }
}

const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const cursor = /^[A-Za-z0-9_-]{1,1024}\.[A-Za-z0-9_-]{43}$/;
const etag = /^"v(0|[1-9][0-9]*)"$/; const digest = /^[0-9a-f]{64}$/;
const code = /^[A-Za-z][A-Za-z0-9_.-]{0,63}$/;
const states = new Set<RequirementState>(["ACTIVE", "DEFERRED", "REJECTED", "ARCHIVED"]);
const versionStates = new Set<RequirementVersionState>(["DRAFT", "IN_REVIEW", "APPROVED", "RETURNED", "SUPERSEDED", "RESTRICTED"]);
const classes = new Set<RequirementClassification>(["STANDARD_FUNCTION", "NONSTANDARD_FUNCTION", "DIFFERENCE", "PENDING_CONFIRMATION"]);
const sourceTypes = new Set<RequirementSourceType>(["APPROVED_SURVEY_CONCLUSION", "CONFIRMED_HANDOVER", "HUMAN_DECISION", "PROJECT_EVIDENCE"]);
function record(value: unknown): value is Record<string, unknown> { return typeof value === "object" && value !== null && !Array.isArray(value); }
function exact(value: Record<string, unknown>, fields: readonly string[]): boolean {
  return Object.keys(value).length === fields.length && fields.every(field => Object.hasOwn(value, field));
}
function id(value: unknown): value is string { return typeof value === "string" && uuid.test(value) && value !== "00000000-0000-0000-0000-000000000000"; }
function optionalId(value: unknown): value is string | null { return value === null || id(value); }
function integer(value: unknown, minimum = 0, maximum = Number.MAX_SAFE_INTEGER): value is number {
  return typeof value === "number" && Number.isSafeInteger(value) && value >= minimum && value <= maximum;
}
function text(value: unknown, maximum: number): value is string {
  return typeof value === "string" && value.length > 0 && value.length <= maximum && value.trim() === value && !/\p{C}/u.test(value);
}
function instant(value: unknown): value is string {
  return typeof value === "string" && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$/.test(value) && Number.isFinite(Date.parse(value));
}
function frozen<T extends object>(value: T): Readonly<T> { return Object.freeze(value); }

const requirementFields = ["requirement_id", "project_id", "requirement_code", "state", "current_approved_version_ref",
  "created_by", "created_at", "updated_by", "updated_at", "etag"] as const;
export function parseRequirement(value: unknown, projectId: string, requirementId?: string): RequirementView {
  if (!record(value) || !exact(value, requirementFields) || !id(value.requirement_id)
    || requirementId !== undefined && value.requirement_id !== requirementId || value.project_id !== projectId
    || typeof value.requirement_code !== "string" || !code.test(value.requirement_code)
    || !states.has(value.state as RequirementState) || !optionalId(value.current_approved_version_ref)
    || !id(value.created_by) || !instant(value.created_at) || !optionalId(value.updated_by) || !instant(value.updated_at)
    || Date.parse(value.updated_at) < Date.parse(value.created_at) || typeof value.etag !== "string" || !etag.test(value.etag)) {
    throw new RequirementReadError("REQUIREMENT_READ_UNAVAILABLE");
  }
  return frozen({ requirement_id: value.requirement_id, project_id: projectId, requirement_code: value.requirement_code,
    state: value.state as RequirementState, current_approved_version_ref: value.current_approved_version_ref,
    created_by: value.created_by, created_at: value.created_at, updated_by: value.updated_by,
    updated_at: value.updated_at, etag: value.etag });
}

const summaryFields = ["requirement_version_id", "requirement_id", "project_id", "version_no", "state", "title",
  "domain_name", "priority", "risk", "classification", "content_fingerprint", "declared_counts",
  "supersedes_version_ref", "review_ref", "review_round_ref", "created_by", "created_at"] as const;
const countFields = ["sources", "acceptance_criteria", "capability_assessments", "assumptions", "exclusions", "dependencies", "ai_tasks"] as const;
function parseSummary(value: unknown, projectId: string, requirementId: string, versionId?: string): RequirementVersionSummary {
  if (!record(value) || !exact(value, summaryFields) || !id(value.requirement_version_id)
    || versionId !== undefined && value.requirement_version_id !== versionId || value.requirement_id !== requirementId
    || value.project_id !== projectId || !integer(value.version_no, 1)
    || !versionStates.has(value.state as RequirementVersionState) || value.title !== null && !text(value.title, 255)
    || !text(value.domain_name, 255) || !new Set(["LOW", "MEDIUM", "HIGH", "URGENT"]).has(value.priority as string)
    || !new Set(["LOW", "MEDIUM", "HIGH", "CRITICAL"]).has(value.risk as string)
    || !classes.has(value.classification as RequirementClassification) || typeof value.content_fingerprint !== "string"
    || !digest.test(value.content_fingerprint) || !record(value.declared_counts) || !exact(value.declared_counts, countFields)
    || countFields.some(field => !integer((value.declared_counts as Record<string, unknown>)[field], 0, 100_000))
    || !optionalId(value.supersedes_version_ref) || !optionalId(value.review_ref) || !optionalId(value.review_round_ref)
    || (value.review_ref === null) !== (value.review_round_ref === null) || !id(value.created_by) || !instant(value.created_at)) {
    throw new RequirementReadError("REQUIREMENT_READ_UNAVAILABLE");
  }
  return frozen({ requirement_version_id: value.requirement_version_id, requirement_id: requirementId, project_id: projectId,
    version_no: value.version_no, state: value.state as RequirementVersionState, title: value.title,
    domain_name: value.domain_name, priority: value.priority as RequirementVersionSummary["priority"],
    risk: value.risk as RequirementVersionSummary["risk"], classification: value.classification as RequirementClassification,
    content_fingerprint: value.content_fingerprint, declared_counts: frozen({ ...value.declared_counts } as unknown as RequirementDeclaredCounts),
    supersedes_version_ref: value.supersedes_version_ref, review_ref: value.review_ref,
    review_round_ref: value.review_round_ref, created_by: value.created_by, created_at: value.created_at });
}

function ordered<T>(values: unknown, count: number, parse: (value: unknown, ordinal: number) => T): readonly T[] {
  if (!Array.isArray(values) || values.length !== count) throw new RequirementReadError("REQUIREMENT_READ_UNAVAILABLE");
  return Object.freeze(values.map(parse));
}
const sourceFields = ["ordinal", "source_type", "source_object_id", "source_version_ref", "evidence_refs"] as const;
function parseSource(value: unknown, ordinal: number): RequirementSourceView {
  if (!record(value) || !exact(value, sourceFields) || value.ordinal !== ordinal
    || !sourceTypes.has(value.source_type as RequirementSourceType) || !id(value.source_object_id)
    || !optionalId(value.source_version_ref) || (value.source_type === "CONFIRMED_HANDOVER") !== (value.source_version_ref !== null)
    || !Array.isArray(value.evidence_refs)) throw new RequirementReadError("REQUIREMENT_READ_UNAVAILABLE");
  const evidence = value.evidence_refs.map((item, index) => {
    if (!record(item) || !exact(item, ["evidence_id", "ordinal"]) || !id(item.evidence_id) || item.ordinal !== index) {
      throw new RequirementReadError("REQUIREMENT_READ_UNAVAILABLE");
    }
    return frozen({ evidence_id: item.evidence_id, ordinal: index });
  });
  if (new Set(evidence.map(item => item.evidence_id)).size !== evidence.length
    || (["HUMAN_DECISION", "PROJECT_EVIDENCE"].includes(value.source_type as string) && evidence.length === 0)) {
    throw new RequirementReadError("REQUIREMENT_READ_UNAVAILABLE");
  }
  return frozen({ ordinal, source_type: value.source_type as RequirementSourceType,
    source_object_id: value.source_object_id, source_version_ref: value.source_version_ref,
    evidence_refs: Object.freeze(evidence) });
}
function parseAcceptance(value: unknown, ordinal: number): RequirementAcceptanceView {
  const fields = ["ordinal", "observable_result", "verification_method", "required_data", "required_environment", "evidence_requirement"] as const;
  if (!record(value) || !exact(value, fields) || value.ordinal !== ordinal || fields.slice(1).some(field => !text(value[field], 4000))) {
    throw new RequirementReadError("REQUIREMENT_READ_UNAVAILABLE");
  }
  return frozen(value as unknown as RequirementAcceptanceView);
}
function parseAssessment(value: unknown, ordinal: number): RequirementCapabilityAssessmentView {
  const fields = ["ordinal", "baseline_version_id", "capability_item_id", "match_type", "fit_gap", "constraints_text",
    "assessor_kind", "assessed_by", "assessed_at", "confirmation_state", "evidence_refs"] as const;
  if (!record(value) || !exact(value, fields) || value.ordinal !== ordinal || !id(value.baseline_version_id)
    || !id(value.capability_item_id) || !new Set(["DIRECT", "PARTIAL", "NONE", "UNKNOWN"]).has(value.match_type as string)
    || !text(value.fit_gap, 4000) || !text(value.constraints_text, 4000) || value.assessor_kind !== "HUMAN"
    || !optionalId(value.assessed_by) || !instant(value.assessed_at)
    || !new Set(["CANDIDATE", "CONFIRMED", "REJECTED"]).has(value.confirmation_state as string)
    || !Array.isArray(value.evidence_refs)) throw new RequirementReadError("REQUIREMENT_READ_UNAVAILABLE");
  const evidence = value.evidence_refs.map((item, index) => {
    if (!record(item) || !exact(item, ["evidence_id", "evidence_role", "ordinal"]) || !id(item.evidence_id)
      || !text(item.evidence_role, 64) || item.ordinal !== index) throw new RequirementReadError("REQUIREMENT_READ_UNAVAILABLE");
    return frozen({ evidence_id: item.evidence_id, evidence_role: item.evidence_role, ordinal: index });
  });
  return frozen({ ...value, evidence_refs: Object.freeze(evidence) } as unknown as RequirementCapabilityAssessmentView);
}
function parseTextItem(value: unknown, ordinal: number): RequirementTextItem {
  if (!record(value) || !exact(value, ["ordinal", "text"]) || value.ordinal !== ordinal || !text(value.text, 4000)) {
    throw new RequirementReadError("REQUIREMENT_READ_UNAVAILABLE");
  }
  return frozen({ ordinal, text: value.text });
}
export function parseRequirementVersion(value: unknown, projectId: string, requirementId: string,
                                        versionId: string): RequirementVersionView {
  if (!record(value)) throw new RequirementReadError("REQUIREMENT_READ_UNAVAILABLE");
  const detailFields = [...summaryFields, "statement", "rationale", "sources", "acceptance_criteria",
    "capability_assessments", "assumptions", "exclusions", "dependencies", "ai_tasks"] as const;
  if (!exact(value, detailFields) || !text(value.statement, 20_000) || !text(value.rationale, 20_000)) {
    throw new RequirementReadError("REQUIREMENT_READ_UNAVAILABLE");
  }
  const summary = parseSummary(Object.fromEntries(summaryFields.map(field => [field, value[field]])), projectId, requirementId, versionId);
  const counts = summary.declared_counts;
  const sources = ordered(value.sources, counts.sources, parseSource);
  const acceptance = ordered(value.acceptance_criteria, counts.acceptance_criteria, parseAcceptance);
  const assessments = ordered(value.capability_assessments, counts.capability_assessments, parseAssessment);
  const assumptions = ordered(value.assumptions, counts.assumptions, parseTextItem);
  const exclusions = ordered(value.exclusions, counts.exclusions, parseTextItem);
  const dependencies = ordered(value.dependencies, counts.dependencies, parseTextItem);
  const tasks = ordered(value.ai_tasks, counts.ai_tasks, (item, ordinal) => {
    if (!record(item) || !exact(item, ["ai_task_id", "ordinal"]) || !id(item.ai_task_id) || item.ordinal !== ordinal) {
      throw new RequirementReadError("REQUIREMENT_READ_UNAVAILABLE");
    }
    return frozen({ ai_task_id: item.ai_task_id, ordinal });
  });
  return frozen({ ...summary, statement: value.statement, rationale: value.rationale, sources,
    acceptance_criteria: acceptance, capability_assessments: assessments, assumptions, exclusions, dependencies,
    ai_tasks: tasks });
}

export class RequirementReadClient {
  constructor(private readonly fetcher: typeof fetch = fetch, private readonly timeoutMs = 10_000) {
    if (!Number.isInteger(timeoutMs) || timeoutMs < 1 || timeoutMs > 30_000) throw new RequirementReadError("REQUIREMENT_READ_INVALID_INPUT");
  }
  async listRequirements(projectId: string, pageSize = 50, next: RequirementCursor | null = null):
      Promise<RequirementPage<RequirementView, RequirementCursor>> {
    this.#listInput([projectId], pageSize, next);
    return await this.#page(`/api/v1/projects/${projectId}/requirements${this.#query(pageSize, next)}`,
      pageSize, next, value => parseRequirement(value, projectId), "requirement") as RequirementPage<RequirementView, RequirementCursor>;
  }
  async getRequirement(projectId: string, requirementId: string): Promise<RequirementView> {
    this.#ids(projectId, requirementId);
    const result = await this.#get(`/api/v1/projects/${projectId}/requirements/${requirementId}`, true);
    const value = parseRequirement(result.data, projectId, requirementId);
    if (result.etag !== value.etag) throw new RequirementReadError("REQUIREMENT_READ_UNAVAILABLE");
    return value;
  }
  async listVersions(projectId: string, requirementId: string, pageSize = 50,
                     next: RequirementVersionCursor | null = null): Promise<RequirementPage<RequirementVersionSummary, RequirementVersionCursor>> {
    this.#listInput([projectId, requirementId], pageSize, next);
    return await this.#page(`/api/v1/projects/${projectId}/requirements/${requirementId}/versions${this.#query(pageSize, next)}`,
      pageSize, next, value => parseSummary(value, projectId, requirementId), "version") as RequirementPage<RequirementVersionSummary, RequirementVersionCursor>;
  }
  async getVersion(projectId: string, requirementId: string, versionId: string): Promise<RequirementVersionView> {
    this.#ids(projectId, requirementId, versionId);
    const data = await this.#get(`/api/v1/projects/${projectId}/requirements/${requirementId}/versions/${versionId}`);
    return parseRequirementVersion(data, projectId, requirementId, versionId);
  }
  #ids(...values: string[]): void {
    if (values.some(value => !id(value))) throw new RequirementReadError("REQUIREMENT_READ_INVALID_INPUT");
  }
  #listInput(values: string[], pageSize: number, next: string | null): void {
    this.#ids(...values);
    if (!integer(pageSize, 1, 200) || next !== null && (typeof next !== "string" || !cursor.test(next))) {
      throw new RequirementReadError("REQUIREMENT_READ_INVALID_INPUT");
    }
  }
  #query(pageSize: number, next: string | null): string {
    const query = new URLSearchParams({ page_size: String(pageSize) }); if (next !== null) query.set("cursor", next); return `?${query}`;
  }
  async #page<T>(path: string, size: number, previous: string | null, parse: (value: unknown) => T,
                 order: "requirement" | "version"): Promise<RequirementPage<T, string>> {
    const data = await this.#get(path);
    if (!record(data) || !exact(data, ["items", "next_cursor", "has_more"]) || !Array.isArray(data.items)
      || data.items.length > size || typeof data.has_more !== "boolean"
      || data.has_more && (data.items.length === 0 || typeof data.next_cursor !== "string" || !cursor.test(data.next_cursor)
        || data.next_cursor === previous) || !data.has_more && data.next_cursor !== null) {
      throw new RequirementReadError("REQUIREMENT_READ_UNAVAILABLE");
    }
    const items = data.items.map(parse) as (T & Record<string, unknown>)[];
    const key = order === "requirement" ? "requirement_id" : "requirement_version_id";
    if (new Set(items.map(item => item[key])).size !== items.length || items.some((item, index) => index > 0 && (
      order === "requirement" ? String(items[index - 1]!.updated_at) < String(item.updated_at)
        || items[index - 1]!.updated_at === item.updated_at && String(items[index - 1]![key]) <= String(item[key])
        : Number(items[index - 1]!.version_no) <= Number(item.version_no)))) {
      throw new RequirementReadError("REQUIREMENT_READ_UNAVAILABLE");
    }
    return frozen({ items: Object.freeze(items) as readonly T[], next_cursor: data.next_cursor as string | null, has_more: data.has_more });
  }
  async #get(path: string, includeEtag?: false): Promise<unknown>;
  async #get(path: string, includeEtag: true): Promise<{ data: unknown; etag: string | null }>;
  async #get(path: string, includeEtag = false): Promise<unknown> {
    const controller = new AbortController(); const timer = window.setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      const response = await this.fetcher(path, { method: "GET", credentials: "same-origin", cache: "no-store",
        redirect: "error", headers: { Accept: "application/json" }, signal: controller.signal });
      if (controller.signal.aborted || response.headers.get("content-type")?.split(";")[0].trim().toLowerCase() !== "application/json") {
        throw new RequirementReadError("REQUIREMENT_READ_UNAVAILABLE");
      }
      const payload: unknown = await response.json();
      if (!record(payload) || !id(payload.trace_id)) throw new RequirementReadError("REQUIREMENT_READ_UNAVAILABLE");
      if (response.status !== 200) {
        const error = record(payload.error) ? payload.error.code : null;
        const expected: Readonly<Record<string, number>> = { AUTH_SESSION_EXPIRED: 401, LICENSE_OPERATION_DENIED: 403,
          RESOURCE_NOT_FOUND: 404, PROJECT_ARCHIVED: 409 };
        if (typeof error === "string" && expected[error] === response.status) throw new RequirementReadError(error as RequirementReadErrorCode);
        throw new RequirementReadError("REQUIREMENT_READ_UNAVAILABLE");
      }
      return includeEtag ? { data: payload.data, etag: response.headers.get("etag") } : payload.data;
    } catch (failure) {
      if (failure instanceof RequirementReadError) throw failure;
      throw new RequirementReadError("REQUIREMENT_READ_UNAVAILABLE");
    } finally { window.clearTimeout(timer); }
  }
}
