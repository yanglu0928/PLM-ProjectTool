export type HandoverAnalysisState = "ACTIVE" | "ARCHIVED" | "RESTRICTED";
export type HandoverVersionState = "DRAFT" | "IN_REVIEW" | "APPROVED" | "RETURNED" | "SUPERSEDED" | "RESTRICTED";
export type HandoverItemType = "GAP" | "MISSING" | "CONFLICT" | "RISK" | "SCOPE" | "NEED_CONFIRM";
export type HandoverItemState = "CANDIDATE" | "CONFIRMED" | "RESOLVED" | "ACCEPTED_RISK" | "REJECTED" | "SUPERSEDED";
export type HandoverSeverity = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
export type HandoverPriority = "LOW" | "MEDIUM" | "HIGH" | "URGENT";
export type HandoverAnalysisCursor = string & { readonly __family: "handover-analyses" };
export type HandoverVersionCursor = string & { readonly __family: "handover-versions" };
export type HandoverItemCursor = string & { readonly __family: "handover-items" };

export interface HandoverAnalysisView {
  readonly handover_analysis_id: string; readonly project_id: string;
  readonly analysis_purpose: string; readonly source_set_ref: string;
  readonly state: HandoverAnalysisState; readonly current_approved_version_ref: string | null;
  readonly created_by: string; readonly created_at: string; readonly updated_at: string; readonly etag: string;
}
export interface HandoverSourceDocument {
  readonly document_id: string; readonly document_version_id: string; readonly ordinal: number;
}
export interface HandoverAITaskRef { readonly ai_task_id: string; readonly ordinal: number; }
export interface HandoverAnalysisVersionView {
  readonly handover_analysis_version_id: string; readonly handover_analysis_id: string; readonly project_id: string;
  readonly version_no: number; readonly state: HandoverVersionState; readonly source_set_ref: string;
  readonly capability_baseline_id: string; readonly capability_baseline_version_ref: string;
  readonly content_fingerprint: string; readonly declared_source_count: number; readonly declared_item_count: number;
  readonly declared_evidence_count: number; readonly declared_capability_ref_count: number;
  readonly declared_ai_task_count: number; readonly supersedes_version_ref: string | null;
  readonly review_ref: string | null; readonly review_round_ref: string | null;
  readonly created_by: string; readonly created_at: string;
  readonly source_documents: readonly HandoverSourceDocument[]; readonly ai_tasks: readonly HandoverAITaskRef[];
}
export interface HandoverInputField {
  readonly name: string; readonly format: string; readonly example: string; readonly required: boolean;
}
export interface HandoverItemOption {
  readonly option_code: string; readonly label: string; readonly description: string | null; readonly ordinal: number;
}
export interface HandoverCapabilityRef {
  readonly baseline_version_id: string; readonly capability_item_id: string; readonly ordinal: number;
}
export interface HandoverAnalysisItemView {
  readonly analysis_item_id: string; readonly handover_analysis_version_id: string;
  readonly handover_analysis_id: string; readonly project_id: string; readonly ordinal: number;
  readonly item_type: HandoverItemType; readonly title: string; readonly statement: string; readonly impact: string;
  readonly severity: HandoverSeverity; readonly priority: HandoverPriority;
  readonly recommendation: string | null; readonly confirmation_question: string | null;
  readonly required_input_spec: Readonly<{ fields: readonly HandoverInputField[] }> | Readonly<Record<string, never>>;
  readonly source_missing: boolean; readonly state: HandoverItemState; readonly evidence_refs: readonly string[];
  readonly capability_refs: readonly HandoverCapabilityRef[]; readonly options: readonly HandoverItemOption[];
}
export interface HandoverPage<T, C extends string> {
  readonly items: readonly T[]; readonly next_cursor: C | null; readonly has_more: boolean;
}

const messages = {
  HANDOVER_READ_INVALID_INPUT: "项目、交接分析、版本或翻页参数无效。",
  AUTH_SESSION_EXPIRED: "会话已失效，请重新登录。",
  LICENSE_OPERATION_DENIED: "当前许可不允许读取项目交接分析。",
  RESOURCE_NOT_FOUND: "交接分析不存在，或当前账户无权查看。",
  PROJECT_ARCHIVED: "项目已归档，当前交接分析不可读取。",
  HANDOVER_READ_UNAVAILABLE: "暂时无法读取项目交接分析，请稍后重试。",
} as const;
export type HandoverReadErrorCode = keyof typeof messages;
export class HandoverReadError extends Error {
  constructor(readonly code: HandoverReadErrorCode) {
    super(messages[code]); this.name = "HandoverReadError";
  }
}

const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const cursor = /^[A-Za-z0-9_-]{1,1024}\.[A-Za-z0-9_-]{43}$/;
const etag = /^"v(0|[1-9][0-9]*)"$/;
const sourceRef = /^sha256:[0-9a-f]{64}$/; const digest = /^[0-9a-f]{64}$/;
const analysisStates = new Set<HandoverAnalysisState>(["ACTIVE", "ARCHIVED", "RESTRICTED"]);
const versionStates = new Set<HandoverVersionState>(["DRAFT", "IN_REVIEW", "APPROVED", "RETURNED", "SUPERSEDED", "RESTRICTED"]);
const itemTypes = new Set<HandoverItemType>(["GAP", "MISSING", "CONFLICT", "RISK", "SCOPE", "NEED_CONFIRM"]);
const itemStates = new Set<HandoverItemState>(["CANDIDATE", "CONFIRMED", "RESOLVED", "ACCEPTED_RISK", "REJECTED", "SUPERSEDED"]);
const severities = new Set<HandoverSeverity>(["LOW", "MEDIUM", "HIGH", "CRITICAL"]);
const priorities = new Set<HandoverPriority>(["LOW", "MEDIUM", "HIGH", "URGENT"]);
function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
function exact(value: Record<string, unknown>, fields: readonly string[]): boolean {
  return Object.keys(value).length === fields.length && fields.every(field => Object.hasOwn(value, field));
}
function id(value: unknown): value is string {
  return typeof value === "string" && uuid.test(value) && value !== "00000000-0000-0000-0000-000000000000";
}
function text(value: unknown, maximum: number): value is string {
  return typeof value === "string" && value.length > 0 && value.length <= maximum
    && value.trim() === value && !/\p{C}/u.test(value);
}
function instant(value: unknown): value is string {
  return typeof value === "string" && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$/.test(value)
    && Number.isFinite(Date.parse(value));
}
function integer(value: unknown, minimum = 0, maximum = Number.MAX_SAFE_INTEGER): value is number {
  return typeof value === "number" && Number.isSafeInteger(value) && value >= minimum && value <= maximum;
}
function optionalId(value: unknown): value is string | null { return value === null || id(value); }
function frozen<T extends object>(value: T): Readonly<T> { return Object.freeze(value); }

const analysisFields = ["handover_analysis_id", "project_id", "analysis_purpose", "source_set_ref", "state",
  "current_approved_version_ref", "created_by", "created_at", "updated_at", "etag"] as const;
export function parseHandoverAnalysis(value: unknown, projectId: string, analysisId?: string): HandoverAnalysisView {
  if (!record(value) || !exact(value, analysisFields) || !id(value.handover_analysis_id)
    || value.project_id !== projectId || analysisId !== undefined && value.handover_analysis_id !== analysisId
    || !text(value.analysis_purpose, 2000) || typeof value.source_set_ref !== "string" || !sourceRef.test(value.source_set_ref)
    || !analysisStates.has(value.state as HandoverAnalysisState) || !optionalId(value.current_approved_version_ref)
    || !id(value.created_by) || !instant(value.created_at) || !instant(value.updated_at)
    || Date.parse(value.updated_at) < Date.parse(value.created_at) || typeof value.etag !== "string" || !etag.test(value.etag)) {
    throw new HandoverReadError("HANDOVER_READ_UNAVAILABLE");
  }
  return frozen({ handover_analysis_id: value.handover_analysis_id, project_id: projectId,
    analysis_purpose: value.analysis_purpose, source_set_ref: value.source_set_ref,
    state: value.state as HandoverAnalysisState, current_approved_version_ref: value.current_approved_version_ref,
    created_by: value.created_by, created_at: value.created_at, updated_at: value.updated_at, etag: value.etag });
}

const versionFields = ["handover_analysis_version_id", "handover_analysis_id", "project_id", "version_no", "state",
  "source_set_ref", "capability_baseline_id", "capability_baseline_version_ref", "content_fingerprint",
  "declared_source_count", "declared_item_count", "declared_evidence_count", "declared_capability_ref_count",
  "declared_ai_task_count", "supersedes_version_ref", "review_ref", "review_round_ref", "created_by", "created_at",
  "source_documents", "ai_tasks"] as const;
export function parseHandoverVersion(value: unknown, projectId: string, analysisId: string,
                                     versionId?: string): HandoverAnalysisVersionView {
  if (!record(value) || !exact(value, versionFields) || !id(value.handover_analysis_version_id)
    || versionId !== undefined && value.handover_analysis_version_id !== versionId
    || value.handover_analysis_id !== analysisId || value.project_id !== projectId || !integer(value.version_no, 1)
    || !versionStates.has(value.state as HandoverVersionState) || typeof value.source_set_ref !== "string"
    || !sourceRef.test(value.source_set_ref) || !id(value.capability_baseline_id)
    || !id(value.capability_baseline_version_ref) || typeof value.content_fingerprint !== "string"
    || !digest.test(value.content_fingerprint) || !integer(value.declared_source_count, 1, 500)
    || !integer(value.declared_item_count, 1, 500) || !integer(value.declared_evidence_count, 0, 100_000)
    || !integer(value.declared_capability_ref_count, 0, 100_000) || !integer(value.declared_ai_task_count, 0, 100)
    || !optionalId(value.supersedes_version_ref) || !optionalId(value.review_ref) || !optionalId(value.review_round_ref)
    || (value.review_ref === null) !== (value.review_round_ref === null) || !id(value.created_by) || !instant(value.created_at)
    || !Array.isArray(value.source_documents) || !Array.isArray(value.ai_tasks)
    || (versionId === undefined && (value.source_documents.length !== 0 || value.ai_tasks.length !== 0))
    || (versionId !== undefined && (value.source_documents.length !== value.declared_source_count
      || value.ai_tasks.length !== value.declared_ai_task_count))) {
    throw new HandoverReadError("HANDOVER_READ_UNAVAILABLE");
  }
  const sources = value.source_documents.map((item, ordinal): HandoverSourceDocument => {
    if (!record(item) || !exact(item, ["document_id", "document_version_id", "ordinal"])
      || !id(item.document_id) || !id(item.document_version_id) || item.ordinal !== ordinal) {
      throw new HandoverReadError("HANDOVER_READ_UNAVAILABLE");
    }
    return frozen({ document_id: item.document_id, document_version_id: item.document_version_id, ordinal });
  });
  const tasks = value.ai_tasks.map((item, ordinal): HandoverAITaskRef => {
    if (!record(item) || !exact(item, ["ai_task_id", "ordinal"]) || !id(item.ai_task_id) || item.ordinal !== ordinal) {
      throw new HandoverReadError("HANDOVER_READ_UNAVAILABLE");
    }
    return frozen({ ai_task_id: item.ai_task_id, ordinal });
  });
  if (new Set(sources.map(item => item.document_id)).size !== sources.length
    || new Set(sources.map(item => item.document_version_id)).size !== sources.length
    || new Set(tasks.map(item => item.ai_task_id)).size !== tasks.length) throw new HandoverReadError("HANDOVER_READ_UNAVAILABLE");
  return frozen({ handover_analysis_version_id: value.handover_analysis_version_id, handover_analysis_id: analysisId,
    project_id: projectId, version_no: value.version_no, state: value.state as HandoverVersionState,
    source_set_ref: value.source_set_ref, capability_baseline_id: value.capability_baseline_id,
    capability_baseline_version_ref: value.capability_baseline_version_ref, content_fingerprint: value.content_fingerprint,
    declared_source_count: value.declared_source_count, declared_item_count: value.declared_item_count,
    declared_evidence_count: value.declared_evidence_count, declared_capability_ref_count: value.declared_capability_ref_count,
    declared_ai_task_count: value.declared_ai_task_count, supersedes_version_ref: value.supersedes_version_ref,
    review_ref: value.review_ref, review_round_ref: value.review_round_ref, created_by: value.created_by,
    created_at: value.created_at, source_documents: Object.freeze(sources), ai_tasks: Object.freeze(tasks) });
}

const itemFields = ["analysis_item_id", "handover_analysis_version_id", "handover_analysis_id", "project_id", "ordinal",
  "item_type", "title", "statement", "impact", "severity", "priority", "recommendation", "confirmation_question",
  "required_input_spec", "source_missing", "state", "evidence_refs", "capability_refs", "options"] as const;
export function parseHandoverItem(value: unknown, projectId: string, analysisId: string,
                                  versionId: string): HandoverAnalysisItemView {
  if (!record(value) || !exact(value, itemFields) || !id(value.analysis_item_id)
    || value.handover_analysis_version_id !== versionId || value.handover_analysis_id !== analysisId
    || value.project_id !== projectId || !integer(value.ordinal, 0, 499)
    || !itemTypes.has(value.item_type as HandoverItemType) || !text(value.title, 255) || !text(value.statement, 4000)
    || !text(value.impact, 2000) || !severities.has(value.severity as HandoverSeverity)
    || !priorities.has(value.priority as HandoverPriority)
    || (value.recommendation !== null && !text(value.recommendation, 2000))
    || (value.confirmation_question !== null && !text(value.confirmation_question, 2000))
    || typeof value.source_missing !== "boolean" || !itemStates.has(value.state as HandoverItemState)
    || !Array.isArray(value.evidence_refs) || value.evidence_refs.length > 200 || value.evidence_refs.some(ref => !id(ref))
    || new Set(value.evidence_refs).size !== value.evidence_refs.length || !value.source_missing && value.evidence_refs.length === 0
    || !Array.isArray(value.capability_refs) || value.capability_refs.length > 200
    || !Array.isArray(value.options) || value.options.length > 20 || !record(value.required_input_spec)) {
    throw new HandoverReadError("HANDOVER_READ_UNAVAILABLE");
  }
  const capabilities = value.capability_refs.map((item, ordinal): HandoverCapabilityRef => {
    if (!record(item) || !exact(item, ["baseline_version_id", "capability_item_id", "ordinal"])
      || !id(item.baseline_version_id) || !id(item.capability_item_id) || item.ordinal !== ordinal) {
      throw new HandoverReadError("HANDOVER_READ_UNAVAILABLE");
    }
    return frozen({ baseline_version_id: item.baseline_version_id, capability_item_id: item.capability_item_id, ordinal });
  });
  const options = value.options.map((item, ordinal): HandoverItemOption => {
    if (!record(item) || !exact(item, ["option_code", "label", "description", "ordinal"])
      || typeof item.option_code !== "string" || !/^[A-Z][A-Z0-9_-]{0,31}$/.test(item.option_code)
      || !text(item.label, 255) || item.description !== null && !text(item.description, 2000) || item.ordinal !== ordinal) {
      throw new HandoverReadError("HANDOVER_READ_UNAVAILABLE");
    }
    return frozen({ option_code: item.option_code, label: item.label, description: item.description, ordinal });
  });
  let inputSpec: HandoverAnalysisItemView["required_input_spec"];
  if (value.item_type === "NEED_CONFIRM") {
    if (value.confirmation_question === null || value.recommendation === null || options.length < 2
      || !exact(value.required_input_spec, ["fields"]) || !Array.isArray(value.required_input_spec.fields)
      || value.required_input_spec.fields.length < 1 || value.required_input_spec.fields.length > 32) {
      throw new HandoverReadError("HANDOVER_READ_UNAVAILABLE");
    }
    const fields = value.required_input_spec.fields.map((field): HandoverInputField => {
      if (!record(field) || !exact(field, ["name", "format", "example", "required"])
        || !text(field.name, 128) || !text(field.format, 128) || !text(field.example, 500)
        || typeof field.required !== "boolean") throw new HandoverReadError("HANDOVER_READ_UNAVAILABLE");
      return frozen({ name: field.name, format: field.format, example: field.example, required: field.required });
    });
    inputSpec = frozen({ fields: Object.freeze(fields) });
  } else {
    if (value.confirmation_question !== null || options.length !== 0 || Object.keys(value.required_input_spec).length !== 0) {
      throw new HandoverReadError("HANDOVER_READ_UNAVAILABLE");
    }
    inputSpec = frozen({});
  }
  if (new Set(capabilities.map(item => item.capability_item_id)).size !== capabilities.length
    || new Set(options.map(item => item.option_code)).size !== options.length) throw new HandoverReadError("HANDOVER_READ_UNAVAILABLE");
  return frozen({ analysis_item_id: value.analysis_item_id, handover_analysis_version_id: versionId,
    handover_analysis_id: analysisId, project_id: projectId, ordinal: value.ordinal,
    item_type: value.item_type as HandoverItemType, title: value.title, statement: value.statement, impact: value.impact,
    severity: value.severity as HandoverSeverity, priority: value.priority as HandoverPriority,
    recommendation: value.recommendation, confirmation_question: value.confirmation_question,
    required_input_spec: inputSpec, source_missing: value.source_missing, state: value.state as HandoverItemState,
    evidence_refs: Object.freeze([...value.evidence_refs]) as readonly string[], capability_refs: Object.freeze(capabilities),
    options: Object.freeze(options) });
}

export class HandoverReadClient {
  constructor(private readonly fetcher: typeof fetch = fetch, private readonly timeoutMs = 10_000) {
    if (!Number.isInteger(timeoutMs) || timeoutMs < 1 || timeoutMs > 30_000) {
      throw new HandoverReadError("HANDOVER_READ_INVALID_INPUT");
    }
  }
  async listAnalyses(projectId: string, pageSize = 50, next: HandoverAnalysisCursor | null = null):
      Promise<HandoverPage<HandoverAnalysisView, HandoverAnalysisCursor>> {
    this.#listInput([projectId], pageSize, next);
    return await this.#page(`/api/v1/projects/${projectId}/handover-analyses${this.#query(pageSize, next)}`,
      pageSize, next, value => parseHandoverAnalysis(value, projectId), "analysis") as HandoverPage<HandoverAnalysisView, HandoverAnalysisCursor>;
  }
  async getAnalysis(projectId: string, analysisId: string): Promise<HandoverAnalysisView> {
    this.#ids(projectId, analysisId); const result = await this.#get(`/api/v1/projects/${projectId}/handover-analyses/${analysisId}`, true);
    const value = parseHandoverAnalysis(result.data, projectId, analysisId);
    if (result.etag !== value.etag) throw new HandoverReadError("HANDOVER_READ_UNAVAILABLE");
    return value;
  }
  async listVersions(projectId: string, analysisId: string, pageSize = 50, next: HandoverVersionCursor | null = null):
      Promise<HandoverPage<HandoverAnalysisVersionView, HandoverVersionCursor>> {
    this.#listInput([projectId, analysisId], pageSize, next);
    return await this.#page(`/api/v1/projects/${projectId}/handover-analyses/${analysisId}/versions${this.#query(pageSize, next)}`,
      pageSize, next, value => parseHandoverVersion(value, projectId, analysisId), "version") as HandoverPage<HandoverAnalysisVersionView, HandoverVersionCursor>;
  }
  async getVersion(projectId: string, analysisId: string, versionId: string): Promise<HandoverAnalysisVersionView> {
    this.#ids(projectId, analysisId, versionId);
    const data = await this.#get(`/api/v1/projects/${projectId}/handover-analyses/${analysisId}/versions/${versionId}`);
    return parseHandoverVersion(data, projectId, analysisId, versionId);
  }
  async listItems(projectId: string, analysisId: string, versionId: string, pageSize = 50,
                  next: HandoverItemCursor | null = null): Promise<HandoverPage<HandoverAnalysisItemView, HandoverItemCursor>> {
    this.#listInput([projectId, analysisId, versionId], pageSize, next);
    return await this.#page(`/api/v1/projects/${projectId}/handover-analyses/${analysisId}/versions/${versionId}/items${this.#query(pageSize, next)}`,
      pageSize, next, value => parseHandoverItem(value, projectId, analysisId, versionId), "item") as HandoverPage<HandoverAnalysisItemView, HandoverItemCursor>;
  }
  #ids(...values: string[]): void {
    if (values.some(value => !id(value))) throw new HandoverReadError("HANDOVER_READ_INVALID_INPUT");
  }
  #listInput(values: string[], pageSize: number, next: string | null): void {
    this.#ids(...values);
    if (!integer(pageSize, 1, 200) || next !== null && (typeof next !== "string" || !cursor.test(next))) {
      throw new HandoverReadError("HANDOVER_READ_INVALID_INPUT");
    }
  }
  #query(pageSize: number, next: string | null): string {
    const query = new URLSearchParams({ page_size: String(pageSize) }); if (next !== null) query.set("cursor", next); return `?${query}`;
  }
  async #page<T>(path: string, size: number, previous: string | null, parse: (value: unknown) => T,
                 order: "analysis" | "version" | "item"): Promise<HandoverPage<T, string>> {
    const data = await this.#get(path);
    if (!record(data) || !exact(data, ["items", "next_cursor", "has_more"]) || !Array.isArray(data.items)
      || data.items.length > size || typeof data.has_more !== "boolean"
      || data.has_more && (data.items.length === 0 || typeof data.next_cursor !== "string" || !cursor.test(data.next_cursor)
        || data.next_cursor === previous) || !data.has_more && data.next_cursor !== null) {
      throw new HandoverReadError("HANDOVER_READ_UNAVAILABLE");
    }
    const items = data.items.map(parse) as (T & Record<string, unknown>)[];
    const key = order === "analysis" ? "handover_analysis_id" : order === "version" ? "handover_analysis_version_id" : "analysis_item_id";
    if (new Set(items.map(item => item[key])).size !== items.length || items.some((item, index) => index > 0 && (
      order === "analysis" ? String(items[index - 1]!.updated_at) < String(item.updated_at)
        || items[index - 1]!.updated_at === item.updated_at && String(items[index - 1]![key]) <= String(item[key])
        : order === "version" ? Number(items[index - 1]!.version_no) <= Number(item.version_no)
          : Number(items[index - 1]!.ordinal) >= Number(item.ordinal)))) {
      throw new HandoverReadError("HANDOVER_READ_UNAVAILABLE");
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
        throw new HandoverReadError("HANDOVER_READ_UNAVAILABLE");
      }
      const payload: unknown = await response.json();
      if (!record(payload) || !id(payload.trace_id)) throw new HandoverReadError("HANDOVER_READ_UNAVAILABLE");
      if (response.status !== 200) {
        const code = record(payload.error) ? payload.error.code : null;
        const expected: Readonly<Record<string, number>> = { AUTH_SESSION_EXPIRED: 401, LICENSE_OPERATION_DENIED: 403,
          RESOURCE_NOT_FOUND: 404, PROJECT_ARCHIVED: 409 };
        if (typeof code === "string" && expected[code] === response.status) throw new HandoverReadError(code as HandoverReadErrorCode);
        throw new HandoverReadError("HANDOVER_READ_UNAVAILABLE");
      }
      return includeEtag ? { data: payload.data, etag: response.headers.get("etag") } : payload.data;
    } catch (failure) {
      if (failure instanceof HandoverReadError) throw failure;
      throw new HandoverReadError("HANDOVER_READ_UNAVAILABLE");
    } finally { window.clearTimeout(timer); }
  }
}
