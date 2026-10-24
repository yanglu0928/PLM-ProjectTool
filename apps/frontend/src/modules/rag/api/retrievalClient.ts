import { SessionClient, SessionClientError } from "@/modules/auth/api/sessionClient";

export type RAGRetrievalState = "RUNNING" | "SUCCEEDED" | "FAILED" | "CANCELLED";
export type RAGSourceType = "CONTRACTUAL" | "PROJECT_RECORD" | "STANDARD_CAPABILITY"
  | "REFERENCE_MATERIAL" | "TEMPLATE" | "GENERATED_ARTIFACT" | "OTHER";

export interface RAGMetadataFilter {
  readonly document_category?: readonly string[];
  readonly source_type?: readonly RAGSourceType[];
  readonly document_version_ref?: string;
}
export interface RAGRetrievalCreateInput {
  readonly query: string;
  readonly metadata_filter: RAGMetadataFilter;
  readonly project_index_ref: string;
  readonly top_k: number;
}
export interface RAGCreatedRetrieval { readonly retrieval_run_id: string; readonly job_id: string; }
export interface RAGRetrievalRun {
  readonly retrieval_run_id: string; readonly project_id: string; readonly requested_by: string;
  readonly project_index_ref: string; readonly retrieval_policy_ref: "fts.project.v1";
  readonly rerank_policy_ref: "none.v1"; readonly top_k: number;
  readonly rerank_state: "NOT_APPLICABLE"; readonly egress_state: "NOT_APPLICABLE";
  readonly retrieval_state: RAGRetrievalState; readonly quality_flags: readonly string[];
  readonly degraded: false; readonly error_code: string | null; readonly job_id: string;
  readonly created_at: string; readonly completed_at: string | null; readonly etag: string;
}
export interface RAGScorePart {
  readonly score_kind: "FTS" | "VECTOR" | "METADATA" | "SOURCE_WEIGHT" | "RERANK" | "FINAL";
  readonly score_ordinal: number; readonly raw_score_micros: number;
  readonly normalized_score_micros: number; readonly weight_micros: number;
  readonly weighted_score_micros: number; readonly score_policy_ref: string;
}
export interface RAGCandidate {
  readonly candidate_id: string; readonly rank: number; readonly chunk_id: string;
  readonly document_version_ref: string; readonly parse_result_ref: string;
  readonly source_type: RAGSourceType; readonly source_locator: Readonly<Record<string, string | number | boolean | null>>;
  readonly retrieval_channel: "FTS" | "VECTOR" | "HYBRID" | "EXACT";
  readonly final_score_micros: number; readonly score_parts: readonly RAGScorePart[]; readonly snippet: string;
}
export interface RAGRetrievalResult {
  readonly retrieval_run_id: string; readonly project_id: string; readonly candidates: readonly RAGCandidate[];
  readonly quality_flags: readonly string[]; readonly degraded: boolean; readonly completed_at: string;
}
export interface RAGContextItem {
  readonly ordinal: number; readonly chunk_id: string; readonly document_version_ref: string;
  readonly source_locator: Readonly<Record<string, string | number | boolean | null>>;
  readonly snippet_start: number; readonly snippet_end: number; readonly token_count: number; readonly snippet: string;
}
export interface RAGContextView {
  readonly context_bundle_id: string; readonly retrieval_run_id: string; readonly project_id: string;
  readonly context_policy_ref: string; readonly token_budget: number; readonly token_count: number;
  readonly created_at: string; readonly items: readonly RAGContextItem[];
}
export interface RAGCancelFirstReceipt {
  readonly first_result: Readonly<{ retrieval_run_id: string; job_id: string;
    state: RAGRetrievalState | "CANCEL_REQUESTED"; changed: boolean; etag: string; status_url: string }>;
  readonly is_current_state_proof: false;
}

const messages = {
  RAG_RETRIEVAL_INVALID_INPUT: "检索条件、索引或版本无效，请重新核对。",
  AUTH_RELOGIN_REQUIRED: "提交检索前请重新登录。",
  AUTH_CLIENT_BUSY: "正在处理另一项会话操作，请稍候。",
  AUTH_SESSION_EXPIRED: "会话已失效，请重新登录。",
  AUTH_CSRF_INVALID: "登录状态已变化，请重新登录。",
  LICENSE_OPERATION_DENIED: "当前许可不允许使用项目检索。",
  RESOURCE_NOT_FOUND: "检索、索引或项目不存在，或当前账户无权访问。",
  PROJECT_ARCHIVED: "项目已归档，不能创建新检索。",
  CONFLICT_STATE: "检索尚未形成可读取结果，请稍后刷新当前状态。",
  CONFLICT_VERSION: "检索状态已变化，请重新读取后再决定。",
  CONFLICT_IDEMPOTENCY: "原操作号对应不同输入，已停止。",
  RAG_RETRIEVAL_UNCERTAIN: "检索操作结果无法确认；请保留原操作号并核对当前事实，切勿换号重试。",
} as const;
export type RAGRetrievalErrorCode = keyof typeof messages;
export class RAGRetrievalError extends Error {
  readonly uncertain: boolean;
  constructor(readonly code: RAGRetrievalErrorCode) {
    super(messages[code]); this.name = "RAGRetrievalError";
    this.uncertain = code === "RAG_RETRIEVAL_UNCERTAIN";
  }
}

const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const etag = /^"v(0|[1-9][0-9]*)"$/; const code = /^[A-Z][A-Z0-9_]{0,63}$/;
const reference = /^[A-Za-z][A-Za-z0-9._:/-]{0,127}$/; const digest = /^[0-9a-f]{64}$/;
const sourceTypes = new Set<RAGSourceType>(["CONTRACTUAL", "PROJECT_RECORD", "STANDARD_CAPABILITY",
  "REFERENCE_MATERIAL", "TEMPLATE", "GENERATED_ARTIFACT", "OTHER"]);
function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
function id(value: unknown): value is string {
  return typeof value === "string" && uuid.test(value) && value !== "00000000-0000-0000-0000-000000000000";
}
function integer(value: unknown, minimum: number, maximum: number): value is number {
  return typeof value === "number" && Number.isSafeInteger(value) && value >= minimum && value <= maximum;
}
function instant(value: unknown): value is string {
  return typeof value === "string" && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$/.test(value)
    && Number.isFinite(Date.parse(value));
}
function codes(value: unknown): readonly string[] {
  if (!Array.isArray(value) || value.length > 32 || value.some(item => typeof item !== "string" || !code.test(item))
    || new Set(value).size !== value.length) throw new RAGRetrievalError("RAG_RETRIEVAL_UNCERTAIN");
  return Object.freeze([...value]) as readonly string[];
}
function locator(value: unknown): Readonly<Record<string, string | number | boolean | null>> {
  if (!record(value) || typeof value.locator_type !== "string" || !value.locator_type
    || Object.keys(value).length > 16 || Object.entries(value).some(([key, item]) => !/^[a-z][a-z0-9_]{0,63}$/.test(key)
      || !(item === null || typeof item === "string" || typeof item === "boolean"
        || (typeof item === "number" && Number.isSafeInteger(item))))) {
    throw new RAGRetrievalError("RAG_RETRIEVAL_UNCERTAIN");
  }
  return Object.freeze(Object.fromEntries(Object.entries(value)) as Record<string, string | number | boolean | null>);
}
function envelope(payload: unknown): { data: unknown; error: string | null } {
  if (!record(payload) || !id(payload.trace_id)) throw new RAGRetrievalError("RAG_RETRIEVAL_UNCERTAIN");
  return { data: payload.data, error: record(payload.error) && typeof payload.error.code === "string" ? payload.error.code : null };
}
function mapped(status: number, server: string | null): RAGRetrievalError {
  const expected: Readonly<Record<string, number>> = {
    AUTH_SESSION_EXPIRED: 401, AUTH_CSRF_INVALID: 403, LICENSE_OPERATION_DENIED: 403,
    RESOURCE_NOT_FOUND: 404, PROJECT_ARCHIVED: 409, CONFLICT_STATE: 409,
    CONFLICT_VERSION: 409, CONFLICT_IDEMPOTENCY: 409,
  };
  if (server && expected[server] === status) return new RAGRetrievalError(server as RAGRetrievalErrorCode);
  if (["REQUEST_MALFORMED", "VALIDATION_FAILED", "CONFLICT_VERSION_REQUIRED"].includes(server ?? "")) {
    return new RAGRetrievalError("RAG_RETRIEVAL_INVALID_INPUT");
  }
  return new RAGRetrievalError("RAG_RETRIEVAL_UNCERTAIN");
}
function normalizedCreate(input: RAGRetrievalCreateInput): Record<string, unknown> {
  if (!record(input) || !id(input.project_index_ref) || !integer(input.top_k, 1, 100)
    || typeof input.query !== "string" || !record(input.metadata_filter)) {
    throw new RAGRetrievalError("RAG_RETRIEVAL_INVALID_INPUT");
  }
  const query = input.query.normalize("NFKC").split(/\s+/u).filter(Boolean).join(" ");
  const queryLength = Array.from(query).length;
  if (queryLength < 1 || queryLength > 4096 || new TextEncoder().encode(query).length > 16_384 || /\p{C}/u.test(query)) {
    throw new RAGRetrievalError("RAG_RETRIEVAL_INVALID_INPUT");
  }
  const allowed = new Set(["document_category", "source_type", "document_version_ref"]);
  if (Object.keys(input.metadata_filter).some(key => !allowed.has(key))) throw new RAGRetrievalError("RAG_RETRIEVAL_INVALID_INPUT");
  const filter: Record<string, unknown> = {};
  if (input.metadata_filter.document_category !== undefined) {
    const values = input.metadata_filter.document_category;
    if (!Array.isArray(values) || values.length < 1 || values.length > 32
      || values.some(item => typeof item !== "string" || item !== item.trim() || item.length < 1 || item.length > 64 || /\p{C}/u.test(item))
      || new Set(values).size !== values.length) throw new RAGRetrievalError("RAG_RETRIEVAL_INVALID_INPUT");
    filter.document_category = [...values].sort();
  }
  if (input.metadata_filter.source_type !== undefined) {
    const values = input.metadata_filter.source_type;
    if (!Array.isArray(values) || values.length < 1 || values.length > 7
      || values.some(item => !sourceTypes.has(item)) || new Set(values).size !== values.length) {
      throw new RAGRetrievalError("RAG_RETRIEVAL_INVALID_INPUT");
    }
    filter.source_type = [...values].sort();
  }
  if (input.metadata_filter.document_version_ref !== undefined) {
    if (!id(input.metadata_filter.document_version_ref)) throw new RAGRetrievalError("RAG_RETRIEVAL_INVALID_INPUT");
    filter.document_version_ref = input.metadata_filter.document_version_ref;
  }
  return { query, metadata_filter: filter, project_index_ref: input.project_index_ref, global_index_ref: null,
    retrieval_policy_ref: "fts.project.v1", rerank_policy_ref: "none.v1", top_k: input.top_k };
}

function parseRun(value: unknown, projectId: string, runId: string, response: Response): RAGRetrievalRun {
  if (!record(value) || value.retrieval_run_id !== runId || value.project_id !== projectId || !id(value.requested_by)
    || value.global_index_ref !== null || !id(value.project_index_ref) || value.retrieval_policy_ref !== "fts.project.v1"
    || value.rerank_policy_ref !== "none.v1" || !integer(value.top_k, 1, 100)
    || value.rerank_state !== "NOT_APPLICABLE" || value.egress_state !== "NOT_APPLICABLE"
    || !["RUNNING", "SUCCEEDED", "FAILED", "CANCELLED"].includes(String(value.retrieval_state))
    || typeof value.degraded !== "boolean" || value.degraded !== false
    || (value.error_code !== null && (typeof value.error_code !== "string" || !code.test(value.error_code)))
    || !id(value.job_id) || !id(value.trace_id) || !instant(value.created_at)
    || (value.completed_at !== null && !instant(value.completed_at)) || !etag.test(String(value.etag))
    || response.headers.get("etag") !== value.etag) throw new RAGRetrievalError("RAG_RETRIEVAL_UNCERTAIN");
  const flags = codes(value.quality_flags);
  return Object.freeze({ retrieval_run_id: runId, project_id: projectId, requested_by: value.requested_by,
    project_index_ref: value.project_index_ref, retrieval_policy_ref: "fts.project.v1" as const,
    rerank_policy_ref: "none.v1" as const, top_k: value.top_k, rerank_state: "NOT_APPLICABLE" as const,
    egress_state: "NOT_APPLICABLE" as const, retrieval_state: value.retrieval_state as RAGRetrievalState,
    quality_flags: flags, degraded: false as const, error_code: value.error_code as string | null,
    job_id: value.job_id, created_at: value.created_at, completed_at: value.completed_at as string | null,
    etag: value.etag as string });
}
function parseScore(value: unknown): RAGScorePart {
  if (!record(value) || !["FTS", "VECTOR", "METADATA", "SOURCE_WEIGHT", "RERANK", "FINAL"].includes(String(value.score_kind))
    || !integer(value.score_ordinal, 0, 31) || !integer(value.raw_score_micros, -1_000_000_000, 1_000_000_000)
    || !integer(value.normalized_score_micros, 0, 1_000_000) || !integer(value.weight_micros, 0, 1_000_000)
    || !integer(value.weighted_score_micros, -1_000_000_000, 1_000_000_000)
    || typeof value.score_policy_ref !== "string" || !reference.test(value.score_policy_ref)) {
    throw new RAGRetrievalError("RAG_RETRIEVAL_UNCERTAIN");
  }
  return Object.freeze({ score_kind: value.score_kind as RAGScorePart["score_kind"], score_ordinal: value.score_ordinal,
    raw_score_micros: value.raw_score_micros, normalized_score_micros: value.normalized_score_micros,
    weight_micros: value.weight_micros, weighted_score_micros: value.weighted_score_micros,
    score_policy_ref: value.score_policy_ref });
}
function parseResult(value: unknown, projectId: string, runId: string): RAGRetrievalResult {
  if (!record(value) || value.retrieval_run_id !== runId || value.project_id !== projectId
    || !Array.isArray(value.candidates) || value.candidates.length < 1 || value.candidates.length > 100
    || typeof value.degraded !== "boolean" || !instant(value.completed_at)) {
    throw new RAGRetrievalError("RAG_RETRIEVAL_UNCERTAIN");
  }
  const candidates = value.candidates.map((item, rank): RAGCandidate => {
    if (!record(item) || !id(item.candidate_id) || item.rank !== rank || !id(item.chunk_id)
      || !id(item.document_version_ref) || !id(item.parse_result_ref) || !sourceTypes.has(item.source_type as RAGSourceType)
      || !["FTS", "VECTOR", "HYBRID", "EXACT"].includes(String(item.retrieval_channel))
      || !integer(item.final_score_micros, -1_000_000_000, 1_000_000_000)
      || !Array.isArray(item.score_parts) || item.score_parts.length < 1 || item.score_parts.length > 32
      || typeof item.snippet !== "string" || Array.from(item.snippet).length < 1 || Array.from(item.snippet).length > 8192) {
      throw new RAGRetrievalError("RAG_RETRIEVAL_UNCERTAIN");
    }
    const parts = Object.freeze(item.score_parts.map(parseScore));
    if (new Set(parts.map(part => `${part.score_kind}:${part.score_ordinal}`)).size !== parts.length) {
      throw new RAGRetrievalError("RAG_RETRIEVAL_UNCERTAIN");
    }
    return Object.freeze({ candidate_id: item.candidate_id, rank, chunk_id: item.chunk_id,
      document_version_ref: item.document_version_ref, parse_result_ref: item.parse_result_ref,
      source_type: item.source_type as RAGSourceType, source_locator: locator(item.source_locator),
      retrieval_channel: item.retrieval_channel as RAGCandidate["retrieval_channel"],
      final_score_micros: item.final_score_micros, score_parts: parts, snippet: item.snippet });
  });
  if (new Set(candidates.map(item => item.candidate_id)).size !== candidates.length) throw new RAGRetrievalError("RAG_RETRIEVAL_UNCERTAIN");
  return Object.freeze({ retrieval_run_id: runId, project_id: projectId, candidates: Object.freeze(candidates),
    quality_flags: codes(value.quality_flags), degraded: value.degraded, completed_at: value.completed_at });
}
function parseContext(value: unknown, projectId: string, runId: string): RAGContextView {
  if (!record(value) || !id(value.context_bundle_id) || value.retrieval_run_id !== runId || value.project_id !== projectId
    || typeof value.context_policy_ref !== "string" || !reference.test(value.context_policy_ref)
    || typeof value.bundle_fingerprint !== "string" || !digest.test(value.bundle_fingerprint)
    || !integer(value.token_budget, 1, Number.MAX_SAFE_INTEGER) || !integer(value.token_count, 1, value.token_budget as number)
    || !instant(value.created_at) || !Array.isArray(value.items) || value.items.length < 1 || value.items.length > 100) {
    throw new RAGRetrievalError("RAG_RETRIEVAL_UNCERTAIN");
  }
  const items = value.items.map((item, ordinal): RAGContextItem => {
    if (!record(item) || item.ordinal !== ordinal || !id(item.chunk_id) || !id(item.document_version_ref)
      || !integer(item.snippet_start, 0, Number.MAX_SAFE_INTEGER) || !integer(item.snippet_end, 1, Number.MAX_SAFE_INTEGER)
      || (item.snippet_end as number) <= (item.snippet_start as number)
      || !integer(item.token_count, 1, 16_384) || typeof item.snippet !== "string" || Array.from(item.snippet).length < 1
      || Array.from(item.snippet).length !== (item.snippet_end as number) - (item.snippet_start as number)) {
      throw new RAGRetrievalError("RAG_RETRIEVAL_UNCERTAIN");
    }
    return Object.freeze({ ordinal, chunk_id: item.chunk_id, document_version_ref: item.document_version_ref,
      source_locator: locator(item.source_locator), snippet_start: item.snippet_start, snippet_end: item.snippet_end,
      token_count: item.token_count, snippet: item.snippet });
  });
  if (items.reduce((total, item) => total + item.token_count, 0) !== value.token_count) {
    throw new RAGRetrievalError("RAG_RETRIEVAL_UNCERTAIN");
  }
  return Object.freeze({ context_bundle_id: value.context_bundle_id, retrieval_run_id: runId, project_id: projectId,
    context_policy_ref: value.context_policy_ref, token_budget: value.token_budget, token_count: value.token_count,
    created_at: value.created_at, items: Object.freeze(items) });
}

export class RAGRetrievalClient {
  constructor(private readonly session: SessionClient, private readonly fetcher: typeof fetch = fetch,
    private readonly timeoutMs = 10_000) {
    if (!(session instanceof SessionClient) || !Number.isInteger(timeoutMs) || timeoutMs < 1 || timeoutMs > 30_000) {
      throw new RAGRetrievalError("RAG_RETRIEVAL_INVALID_INPUT");
    }
  }
  async create(projectId: string, input: RAGRetrievalCreateInput, idempotencyKey: string): Promise<RAGCreatedRetrieval> {
    if (!id(projectId) || !/^[\x20-\x7e]{16,128}$/.test(idempotencyKey)) throw new RAGRetrievalError("RAG_RETRIEVAL_INVALID_INPUT");
    const body = JSON.stringify(normalizedCreate(input));
    return this.#write(() => this.session.postProjectRAGRetrievalCreate(projectId, body, idempotencyKey), 202, (data, response) => {
      if (!record(data) || !id(data.retrieval_run_id) || !id(data.job_id)
        || response.headers.get("location") !== `/api/v1/projects/${projectId}/retrieval-runs/${data.retrieval_run_id}`) {
        throw new RAGRetrievalError("RAG_RETRIEVAL_UNCERTAIN");
      }
      return Object.freeze({ retrieval_run_id: data.retrieval_run_id, job_id: data.job_id });
    });
  }
  getRun(projectId: string, runId: string): Promise<RAGRetrievalRun> {
    return this.#get(projectId, runId, "", (data, response) => parseRun(data, projectId, runId, response));
  }
  getResult(projectId: string, runId: string): Promise<RAGRetrievalResult> {
    return this.#get(projectId, runId, "/result", data => parseResult(data, projectId, runId));
  }
  getContext(projectId: string, runId: string): Promise<RAGContextView> {
    return this.#get(projectId, runId, "/context", data => parseContext(data, projectId, runId));
  }
  async cancel(projectId: string, run: RAGRetrievalRun, idempotencyKey: string, reason: string): Promise<RAGCancelFirstReceipt> {
    const summary = typeof reason === "string" ? reason.trim() : "";
    if (!id(projectId) || !record(run) || run.project_id !== projectId || !id(run.retrieval_run_id)
      || !etag.test(run.etag) || !/^[\x20-\x7e]{16,128}$/.test(idempotencyKey)
      || summary.length < 1 || summary.length > 1024 || /\p{C}/u.test(summary)) {
      throw new RAGRetrievalError("RAG_RETRIEVAL_INVALID_INPUT");
    }
    return this.#write(() => this.session.postProjectRAGRetrievalCancel(projectId, run.retrieval_run_id,
      run.etag, idempotencyKey, summary), 200, (data, response) => {
      const base = `/api/v1/projects/${projectId}/retrieval-runs/${run.retrieval_run_id}`;
      if (!record(data) || data.retrieval_run_id !== run.retrieval_run_id || !id(data.job_id)
        || !["RUNNING", "SUCCEEDED", "FAILED", "CANCELLED", "CANCEL_REQUESTED"].includes(String(data.state))
        || typeof data.changed !== "boolean" || !etag.test(String(data.etag)) || response.headers.get("etag") !== data.etag
        || data.status_url !== base) throw new RAGRetrievalError("RAG_RETRIEVAL_UNCERTAIN");
      return Object.freeze({ first_result: Object.freeze({ retrieval_run_id: run.retrieval_run_id,
        job_id: data.job_id, state: data.state as RAGCancelFirstReceipt["first_result"]["state"],
        changed: data.changed, etag: data.etag as string, status_url: base }), is_current_state_proof: false as const });
    });
  }
  async #get<T>(projectId: string, runId: string, suffix: "" | "/result" | "/context",
    parse: (data: unknown, response: Response) => T): Promise<T> {
    if (!id(projectId) || !id(runId)) throw new RAGRetrievalError("RAG_RETRIEVAL_INVALID_INPUT");
    const controller = new AbortController(); const timer = window.setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      const fetcher = this.fetcher;
      const response = await fetcher(`/api/v1/projects/${projectId}/retrieval-runs/${runId}${suffix}`, {
        method: "GET", credentials: "same-origin", cache: "no-store", redirect: "error",
        headers: { Accept: "application/json" }, signal: controller.signal,
      });
      if (controller.signal.aborted || response.headers.get("content-type")?.split(";")[0].trim().toLowerCase() !== "application/json") {
        throw new RAGRetrievalError("RAG_RETRIEVAL_UNCERTAIN");
      }
      const result = envelope(await response.json());
      if (response.status !== 200) throw mapped(response.status, result.error);
      return parse(result.data, response);
    } catch (failure) {
      if (failure instanceof RAGRetrievalError) throw failure;
      throw new RAGRetrievalError("RAG_RETRIEVAL_UNCERTAIN");
    } finally { window.clearTimeout(timer); }
  }
  async #write<T>(send: () => Promise<Response>, expected: number,
    parse: (data: unknown, response: Response) => T): Promise<T> {
    let response: Response;
    try { response = await send(); }
    catch (failure) {
      if (failure instanceof SessionClientError && ["AUTH_RELOGIN_REQUIRED", "AUTH_CLIENT_BUSY"].includes(failure.code)) {
        throw new RAGRetrievalError(failure.code as "AUTH_RELOGIN_REQUIRED" | "AUTH_CLIENT_BUSY");
      }
      throw new RAGRetrievalError("RAG_RETRIEVAL_UNCERTAIN");
    }
    try {
      if (response.headers.get("content-type")?.split(";")[0].trim().toLowerCase() !== "application/json") {
        throw new RAGRetrievalError("RAG_RETRIEVAL_UNCERTAIN");
      }
      const result = envelope(await response.json());
      if (response.status !== expected) throw mapped(response.status, result.error);
      return parse(result.data, response);
    } catch (failure) {
      if (failure instanceof RAGRetrievalError) throw failure;
      throw new RAGRetrievalError("RAG_RETRIEVAL_UNCERTAIN");
    }
  }
}
