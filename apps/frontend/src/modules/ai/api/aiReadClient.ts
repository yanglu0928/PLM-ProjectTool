/** Strict, read-only transport for frozen AI Task, Invocation and Suggestion APIs. */

export interface AIResourceVersion {
  readonly resource_type: string;
  readonly resource_id: string;
  readonly version_id: string;
}

export interface AITaskView {
  readonly ai_task_id: string;
  readonly project_id: string;
  readonly task_type: string;
  readonly requested_by: string;
  readonly input_refs: readonly AIResourceVersion[];
  readonly prompt_policy_ref: string;
  readonly prompt_policy_version: number | null;
  readonly prompt_version_ref: Readonly<{ prompt_template_id: string; version_no: number }> | null;
  readonly output_schema_ref: string;
  readonly context_policy_ref: string;
  readonly egress_authorization_ref: string | null;
  readonly job_id: string | null;
  readonly current_invocation_id: string | null;
  readonly task_state: "QUEUED" | "RUNNING" | "SUCCEEDED" | "FAILED" | "CANCEL_REQUESTED" | "CANCELLED";
  readonly suggestion_state: "NONE" | "AVAILABLE" | "ACCEPTED_TO_DRAFT" | "REJECTED" | "SUPERSEDED";
  readonly trace_id: string;
  readonly error_code: string | null;
  readonly retryable: boolean | null;
  readonly requested_at: string;
  readonly started_at: string | null;
  readonly completed_at: string | null;
  readonly etag: string;
}

export interface AITaskPage {
  readonly items: readonly AITaskView[];
  readonly next_cursor: string | null;
  readonly has_more: boolean;
}

export interface AIExecutionContext {
  readonly content_plan_id: string;
  readonly content_plan_version: 1;
  readonly context_policy_ref: string;
  readonly mode: "NONE" | "RAG_CONTEXT";
  readonly retrieval_run_id: string | null;
  readonly context_bundle_id: string | null;
}

export interface AIInvocationView {
  readonly ai_invocation_id: string;
  readonly ai_task_id: string;
  readonly attempt_no: number;
  readonly provider: Readonly<{ ai_provider_id: string; provider_config_version_id: string }>;
  readonly model: Readonly<{ ai_model_id: string; revision: string }>;
  readonly prompt_version_ref: Readonly<{ prompt_template_id: string; version_no: number }>;
  readonly output_schema: Readonly<{ ref: string; version: number }>;
  readonly context: AIExecutionContext | null;
  readonly invocation_state: "PENDING" | "RUNNING" | "SUCCEEDED" | "FAILED" | "CANCELLED";
  readonly schema_validation_state: "NOT_APPLICABLE" | "PENDING" | "VALID" | "INVALID";
  readonly usage: Readonly<{ input_tokens: number | null; output_tokens: number | null }>;
  readonly latency_ms: number | null;
  readonly error_code: string | null;
  readonly retryable: boolean | null;
  readonly created_at: string;
  readonly started_at: string | null;
  readonly completed_at: string | null;
}

export interface AIInvocationPage {
  readonly items: readonly AIInvocationView[];
  readonly next_cursor: string | null;
  readonly has_more: boolean;
}

export type AIRequiredFieldKey = "ACTUAL_STATE" | "DECISION" | "OWNER" | "TARGET_DATE"
  | "SCOPE" | "CONSTRAINT" | "EXCEPTION" | "NOTES";
export interface AIRequiredField {
  readonly key: AIRequiredFieldKey;
  readonly label: string;
  readonly prompt: string;
  readonly reason: string;
  readonly required: boolean;
}
export interface AIConfirmation {
  readonly required: boolean;
  readonly question: string | null;
  readonly required_fields: readonly AIRequiredField[];
}
export interface AIGapItemV1 {
  readonly category: AIGapCategory;
  readonly title: string;
  readonly summary: string;
  readonly rationale: string;
  readonly recommendation: string;
  readonly source_ordinals: readonly number[];
}
export interface AIGapItemV2 {
  readonly category: AIGapCategory;
  readonly title: string;
  readonly summary: string;
  readonly rationale: string;
  readonly recommendation: string;
  readonly source_citations: readonly Readonly<{ source_ordinal: number; node_ids: readonly string[] }>[];
  readonly confirmation: AIConfirmation;
}
export type AIGapCategory = "STANDARD_FUNCTION" | "NONSTANDARD_FUNCTION" | "DIFFERENCE" | "PENDING_CONFIRMATION";
export type AIGapPayload = Readonly<{ schema_ref: string; schema_version: 1; items: readonly AIGapItemV1[] }>
  | Readonly<{ schema_ref: string; schema_version: 2; items: readonly AIGapItemV2[] }>;

export interface AISourceLocation {
  readonly source_ordinal: number;
  readonly document_id: string;
  readonly document_version_id: string;
  readonly precision: "DOCUMENT" | "PARSED_NODE";
  readonly content_url: string;
  readonly locations: readonly Readonly<Record<string, unknown>>[];
}

export interface AISuggestionView {
  readonly ai_task_id: string;
  readonly ai_invocation_id: string;
  readonly suggestion_payload_id: string;
  readonly project_id: string;
  readonly suggestion_state: "AVAILABLE" | "ACCEPTED_TO_DRAFT" | "REJECTED" | "SUPERSEDED";
  readonly fact_status: "NOT_FORMAL_FACT";
  readonly quality_flags: readonly string[];
  readonly input_versions: readonly AIResourceVersion[];
  readonly provider: AIInvocationView["provider"];
  readonly model: AIInvocationView["model"];
  readonly prompt_version_ref: AIInvocationView["prompt_version_ref"];
  readonly output_schema: AIInvocationView["output_schema"];
  readonly context: AIExecutionContext;
  readonly payload: AIGapPayload;
  readonly source_locations: readonly AISourceLocation[];
  readonly created_at: string;
  readonly etag: string;
}

const messages = {
  AI_READ_INVALID_INPUT: "AI读取参数无效。",
  AUTH_SESSION_EXPIRED: "会话已失效，请重新登录。",
  LICENSE_OPERATION_DENIED: "当前许可不允许查看AI任务。",
  RESOURCE_NOT_FOUND: "AI任务、建议或原文不存在，或您无权查看。",
  AI_READ_UNAVAILABLE: "暂时无法读取AI任务，请稍后重试。",
} as const;
export type AIReadErrorCode = keyof typeof messages;
export class AIReadError extends Error {
  constructor(readonly code: AIReadErrorCode) { super(messages[code]); this.name = "AIReadError"; }
}

const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const refPattern = /^[A-Za-z][A-Za-z0-9._:/-]{0,127}$/;
const namePattern = /^[A-Z][A-Z0-9_]{0,63}$/;
const modelPattern = /^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$/;
const etagPattern = /^"v(0|[1-9][0-9]*)"$/;
const taskCursor = /^ait1\.[A-Za-z0-9_-]{1,1536}$/;
const invocationCursor = /^aii1\.[A-Za-z0-9_-]{1,1536}$/;
const taskStates = new Set(["QUEUED", "RUNNING", "SUCCEEDED", "FAILED", "CANCEL_REQUESTED", "CANCELLED"]);
const suggestionStates = new Set(["NONE", "AVAILABLE", "ACCEPTED_TO_DRAFT", "REJECTED", "SUPERSEDED"]);
const invocationStates = new Set(["PENDING", "RUNNING", "SUCCEEDED", "FAILED", "CANCELLED"]);
const validationStates = new Set(["NOT_APPLICABLE", "PENDING", "VALID", "INVALID"]);
const categories = new Set(["STANDARD_FUNCTION", "NONSTANDARD_FUNCTION", "DIFFERENCE", "PENDING_CONFIRMATION"]);
const fieldKeys = new Set(["ACTUAL_STATE", "DECISION", "OWNER", "TARGET_DATE", "SCOPE", "CONSTRAINT", "EXCEPTION", "NOTES"]);
const nodeKinds = new Set(["TEXT_LINE", "PDF_TEXT_LINE", "OCR_LINE", "CSV_CELL", "DOCX_PARAGRAPH",
  "DOCX_SECTION", "DOCX_TABLE_CELL", "PPTX_SHAPE", "PPTX_TABLE_CELL", "XLSX_CELL"]);

function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
function id(value: unknown): value is string {
  return typeof value === "string" && uuid.test(value) && value !== "00000000-0000-0000-0000-000000000000";
}
function positive(value: unknown): value is number {
  return typeof value === "number" && Number.isSafeInteger(value) && value > 0;
}
function nonnegative(value: unknown): value is number {
  return typeof value === "number" && Number.isSafeInteger(value) && value >= 0;
}
function instant(value: unknown): value is string {
  if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$/.test(value)) return false;
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) && new Date(parsed).toISOString().slice(0, 19) === value.slice(0, 19);
}
function boundedText(value: unknown, maxBytes: number): value is string {
  return typeof value === "string" && value.length > 0 && value.trim() === value && !/[\p{Cc}\p{Cs}]/u.test(value)
    && new TextEncoder().encode(value).length <= maxBytes;
}
function exact(value: Record<string, unknown>, fields: readonly string[]): boolean {
  const keys = Object.keys(value);
  return keys.length === fields.length && keys.every(key => fields.includes(key));
}
function optionalId(value: unknown): value is string | null { return value === null || id(value); }
function optionalCount(value: unknown): value is number | null { return value === null || nonnegative(value); }
function safeError(value: unknown): value is string | null {
  return value === null || typeof value === "string" && namePattern.test(value);
}
function freezeRecord<T extends Record<string, unknown>>(value: T): Readonly<T> { return Object.freeze(value); }

function resource(value: unknown): AIResourceVersion {
  if (!record(value) || typeof value.resource_type !== "string" || !/^[A-Z][A-Z0-9_-]{0,63}$/.test(value.resource_type)
      || !id(value.resource_id) || !id(value.version_id)) throw new AIReadError("AI_READ_UNAVAILABLE");
  return freezeRecord({ resource_type: value.resource_type, resource_id: value.resource_id, version_id: value.version_id });
}

function context(value: unknown): AIExecutionContext {
  if (!record(value) || !id(value.content_plan_id) || value.content_plan_version !== 1
      || typeof value.context_policy_ref !== "string" || !refPattern.test(value.context_policy_ref)
      || (value.mode !== "NONE" && value.mode !== "RAG_CONTEXT")
      || !optionalId(value.retrieval_run_id) || !optionalId(value.context_bundle_id)
      || (value.mode === "NONE" && (value.retrieval_run_id !== null || value.context_bundle_id !== null))
      || (value.mode === "RAG_CONTEXT" && (!id(value.retrieval_run_id) || !id(value.context_bundle_id)))) {
    throw new AIReadError("AI_READ_UNAVAILABLE");
  }
  return freezeRecord({ content_plan_id: value.content_plan_id, content_plan_version: 1 as const,
    context_policy_ref: value.context_policy_ref, mode: value.mode as AIExecutionContext["mode"],
    retrieval_run_id: value.retrieval_run_id, context_bundle_id: value.context_bundle_id });
}

function provider(value: unknown): AIInvocationView["provider"] {
  if (!record(value) || !id(value.ai_provider_id) || !id(value.provider_config_version_id)) {
    throw new AIReadError("AI_READ_UNAVAILABLE");
  }
  return freezeRecord({ ai_provider_id: value.ai_provider_id, provider_config_version_id: value.provider_config_version_id });
}
function model(value: unknown): AIInvocationView["model"] {
  if (!record(value) || !id(value.ai_model_id) || typeof value.revision !== "string" || !modelPattern.test(value.revision)) {
    throw new AIReadError("AI_READ_UNAVAILABLE");
  }
  return freezeRecord({ ai_model_id: value.ai_model_id, revision: value.revision });
}
function prompt(value: unknown): AIInvocationView["prompt_version_ref"] {
  if (!record(value) || !id(value.prompt_template_id) || !positive(value.version_no)) {
    throw new AIReadError("AI_READ_UNAVAILABLE");
  }
  return freezeRecord({ prompt_template_id: value.prompt_template_id, version_no: value.version_no });
}
function outputSchema(value: unknown): AIInvocationView["output_schema"] {
  if (!record(value) || typeof value.ref !== "string" || !refPattern.test(value.ref) || !positive(value.version)) {
    throw new AIReadError("AI_READ_UNAVAILABLE");
  }
  return freezeRecord({ ref: value.ref, version: value.version });
}

export function parseAITask(value: unknown, projectId: string, taskId: string | null = null): AITaskView {
  if (!record(value) || !id(projectId) || (taskId !== null && !id(taskId)) || !id(value.ai_task_id)
      || (taskId !== null && value.ai_task_id !== taskId) || value.project_id !== projectId
      || typeof value.task_type !== "string" || !namePattern.test(value.task_type) || !id(value.requested_by)
      || !Array.isArray(value.input_refs) || value.input_refs.length < 1 || value.input_refs.length > 1000
      || typeof value.prompt_policy_ref !== "string" || !refPattern.test(value.prompt_policy_ref)
      || typeof value.output_schema_ref !== "string" || !refPattern.test(value.output_schema_ref)
      || typeof value.context_policy_ref !== "string" || !refPattern.test(value.context_policy_ref)
      || !optionalId(value.egress_authorization_ref) || !optionalId(value.job_id) || !optionalId(value.current_invocation_id)
      || typeof value.task_state !== "string" || !taskStates.has(value.task_state)
      || typeof value.suggestion_state !== "string" || !suggestionStates.has(value.suggestion_state)
      || !id(value.trace_id) || !safeError(value.error_code)
      || (value.retryable !== null && typeof value.retryable !== "boolean") || !instant(value.requested_at)
      || (value.started_at !== null && !instant(value.started_at)) || (value.completed_at !== null && !instant(value.completed_at))
      || typeof value.etag !== "string" || !etagPattern.test(value.etag)) throw new AIReadError("AI_READ_UNAVAILABLE");
  let promptRef: AITaskView["prompt_version_ref"] = null;
  if (value.prompt_version_ref === null) {
    if (value.prompt_policy_version !== null) throw new AIReadError("AI_READ_UNAVAILABLE");
  } else {
    promptRef = prompt(value.prompt_version_ref);
    if (!positive(value.prompt_policy_version)) throw new AIReadError("AI_READ_UNAVAILABLE");
  }
  const refs = Object.freeze(value.input_refs.map(resource));
  if (new Set(refs.map(item => `${item.resource_type}:${item.resource_id}:${item.version_id}`)).size !== refs.length
      || (value.started_at !== null && value.started_at < value.requested_at)
      || (value.completed_at !== null && (value.started_at === null || value.completed_at < value.started_at))) {
    throw new AIReadError("AI_READ_UNAVAILABLE");
  }
  return freezeRecord({ ai_task_id: value.ai_task_id, project_id: value.project_id, task_type: value.task_type,
    requested_by: value.requested_by, input_refs: refs, prompt_policy_ref: value.prompt_policy_ref,
    prompt_policy_version: value.prompt_policy_version as number | null, prompt_version_ref: promptRef,
    output_schema_ref: value.output_schema_ref, context_policy_ref: value.context_policy_ref,
    egress_authorization_ref: value.egress_authorization_ref as string | null, job_id: value.job_id as string | null,
    current_invocation_id: value.current_invocation_id as string | null, task_state: value.task_state as AITaskView["task_state"],
    suggestion_state: value.suggestion_state as AITaskView["suggestion_state"], trace_id: value.trace_id,
    error_code: value.error_code as string | null, retryable: value.retryable as boolean | null,
    requested_at: value.requested_at, started_at: value.started_at as string | null,
    completed_at: value.completed_at as string | null, etag: value.etag });
}

export function parseAIInvocation(value: unknown, taskId: string): AIInvocationView {
  if (!record(value) || !id(taskId) || !id(value.ai_invocation_id) || value.ai_task_id !== taskId
      || !positive(value.attempt_no) || typeof value.invocation_state !== "string" || !invocationStates.has(value.invocation_state)
      || typeof value.schema_validation_state !== "string" || !validationStates.has(value.schema_validation_state)
      || !record(value.usage) || !optionalCount(value.usage.input_tokens) || !optionalCount(value.usage.output_tokens)
      || !optionalCount(value.latency_ms) || !safeError(value.error_code)
      || (value.retryable !== null && typeof value.retryable !== "boolean") || !instant(value.created_at)
      || (value.started_at !== null && !instant(value.started_at)) || (value.completed_at !== null && !instant(value.completed_at))) {
    throw new AIReadError("AI_READ_UNAVAILABLE");
  }
  const terminal = ["SUCCEEDED", "FAILED", "CANCELLED"].includes(value.invocation_state);
  if ((terminal && (value.started_at === null || value.completed_at === null)) || (!terminal && value.completed_at !== null)
      || (value.started_at !== null && value.started_at < value.created_at)
      || (value.completed_at !== null && (value.started_at === null || value.completed_at < value.started_at))
      || (value.invocation_state === "FAILED" && (value.error_code === null || typeof value.retryable !== "boolean"))) {
    throw new AIReadError("AI_READ_UNAVAILABLE");
  }
  const parsedContext = value.context === null ? null : context(value.context);
  return freezeRecord({ ai_invocation_id: value.ai_invocation_id, ai_task_id: value.ai_task_id,
    attempt_no: value.attempt_no, provider: provider(value.provider), model: model(value.model),
    prompt_version_ref: prompt(value.prompt_version_ref), output_schema: outputSchema(value.output_schema),
    context: parsedContext, invocation_state: value.invocation_state as AIInvocationView["invocation_state"],
    schema_validation_state: value.schema_validation_state as AIInvocationView["schema_validation_state"],
    usage: freezeRecord({ input_tokens: value.usage.input_tokens as number | null,
      output_tokens: value.usage.output_tokens as number | null }), latency_ms: value.latency_ms as number | null,
    error_code: value.error_code as string | null, retryable: value.retryable as boolean | null,
    created_at: value.created_at, started_at: value.started_at as string | null,
    completed_at: value.completed_at as string | null });
}

function sortedUniqueNumbers(value: unknown): value is number[] {
  return Array.isArray(value) && value.length >= 1 && value.length <= 32
    && value.every(item => positive(item) && item <= 1000)
    && value.every((item, index) => index === 0 || value[index - 1] < item);
}
function sortedUniqueTexts(value: unknown): value is string[] {
  return Array.isArray(value) && value.length >= 1 && value.length <= 32
    && value.every(item => boundedText(item, 512))
    && value.every((item, index) => index === 0 || value[index - 1] < item);
}
type CommonGapItem = Record<string, unknown> & {
  category: AIGapCategory; title: string; summary: string; rationale: string; recommendation: string;
};
function commonItem(value: Record<string, unknown>): value is CommonGapItem {
  return typeof value.category === "string" && categories.has(value.category)
    && boundedText(value.title, 512) && boundedText(value.summary, 8192)
    && boundedText(value.rationale, 8192) && boundedText(value.recommendation, 8192);
}

function payload(value: unknown, schema: AIInvocationView["output_schema"]): { value: AIGapPayload; ordinals: Map<number, Set<string>> } {
  if (!record(value) || value.schema_ref !== schema.ref || value.schema_version !== schema.version
      || !Array.isArray(value.items) || value.items.length < 1 || value.items.length > 100) {
    throw new AIReadError("AI_READ_UNAVAILABLE");
  }
  const sources = new Map<number, Set<string>>();
  if (schema.version === 1 && (schema.ref === "gap-output.v1" || schema.ref === "gap-analysis-output.v1")) {
    const items = value.items.map(item => {
      if (!record(item) || !exact(item, ["category", "title", "summary", "rationale", "recommendation", "source_ordinals"])
          || !commonItem(item) || !sortedUniqueNumbers(item.source_ordinals)) throw new AIReadError("AI_READ_UNAVAILABLE");
      for (const ordinal of item.source_ordinals) sources.set(ordinal, new Set());
      return freezeRecord({ category: item.category, title: item.title, summary: item.summary,
        rationale: item.rationale, recommendation: item.recommendation,
        source_ordinals: Object.freeze([...item.source_ordinals]) });
    });
    return { value: freezeRecord({ schema_ref: schema.ref, schema_version: 1, items: Object.freeze(items) }), ordinals: sources };
  }
  if (schema.version === 2 && (schema.ref === "gap-output.v2" || schema.ref === "gap-analysis-output.v2")) {
    const items = value.items.map(item => {
      if (!record(item) || !exact(item, ["category", "title", "summary", "rationale", "recommendation", "source_citations", "confirmation"])
          || !commonItem(item) || !Array.isArray(item.source_citations) || item.source_citations.length < 1
          || item.source_citations.length > 32 || !record(item.confirmation)
          || !exact(item.confirmation, ["required", "question", "required_fields"])) throw new AIReadError("AI_READ_UNAVAILABLE");
      const citationOrdinals: number[] = [];
      const citations = item.source_citations.map(citation => {
        if (!record(citation) || !exact(citation, ["source_ordinal", "node_ids"]) || !positive(citation.source_ordinal)
            || citation.source_ordinal > 1000 || !sortedUniqueTexts(citation.node_ids)) throw new AIReadError("AI_READ_UNAVAILABLE");
        citationOrdinals.push(citation.source_ordinal);
        const nodes = sources.get(citation.source_ordinal) ?? new Set<string>();
        for (const node of citation.node_ids) nodes.add(node);
        sources.set(citation.source_ordinal, nodes);
        return freezeRecord({ source_ordinal: citation.source_ordinal, node_ids: Object.freeze([...citation.node_ids]) });
      });
      if (citationOrdinals.some((ordinal, index) => index > 0 && citationOrdinals[index - 1] >= ordinal)) {
        throw new AIReadError("AI_READ_UNAVAILABLE");
      }
      const required = item.category === "PENDING_CONFIRMATION";
      if (item.confirmation.required !== required || !Array.isArray(item.confirmation.required_fields)
          || (required && (!boundedText(item.confirmation.question, 2048) || item.confirmation.required_fields.length < 1))
          || (!required && (item.confirmation.question !== null || item.confirmation.required_fields.length !== 0))
          || item.confirmation.required_fields.length > 8) throw new AIReadError("AI_READ_UNAVAILABLE");
      const fields = item.confirmation.required_fields.map(field => {
        if (!record(field) || !exact(field, ["key", "label", "prompt", "reason", "required"])
            || typeof field.key !== "string" || !fieldKeys.has(field.key) || !boundedText(field.label, 256)
            || !boundedText(field.prompt, 2048) || !boundedText(field.reason, 2048) || typeof field.required !== "boolean") {
          throw new AIReadError("AI_READ_UNAVAILABLE");
        }
        return freezeRecord({ key: field.key as AIRequiredFieldKey, label: field.label,
          prompt: field.prompt, reason: field.reason, required: field.required });
      });
      if (new Set(fields.map(field => field.key)).size !== fields.length || (required && !fields.some(field => field.required))) {
        throw new AIReadError("AI_READ_UNAVAILABLE");
      }
      return freezeRecord({ category: item.category, title: item.title, summary: item.summary,
        rationale: item.rationale, recommendation: item.recommendation, source_citations: Object.freeze(citations),
        confirmation: freezeRecord({ required, question: item.confirmation.question as string | null,
          required_fields: Object.freeze(fields) }) });
    });
    return { value: freezeRecord({ schema_ref: schema.ref, schema_version: 2, items: Object.freeze(items) }), ordinals: sources };
  }
  throw new AIReadError("AI_READ_UNAVAILABLE");
}

function bounds(value: unknown): boolean {
  return Array.isArray(value) && value.length === 4 && value.every(item => typeof item === "number" && Number.isFinite(item) && item >= 0 && item <= 1)
    && value[0] < value[2] && value[1] < value[3];
}
function cell(value: unknown): [number, number] | null {
  if (typeof value !== "string") return null;
  const match = /^([A-Z]{1,3})([1-9][0-9]{0,6})$/.exec(value);
  if (!match) return null;
  let column = 0;
  for (const char of match[1]!) column = column * 26 + char.charCodeAt(0) - 64;
  const row = Number(match[2]);
  return column <= 16_384 && row <= 1_048_576 ? [column, row] : null;
}
function locator(value: unknown, nested = false): value is Record<string, unknown> {
  if (!record(value)) return false;
  switch (value.locator_type) {
    case "DOCUMENT": return exact(value, ["locator_type"]);
    case "PAGE": return Object.keys(value).every(key => ["locator_type", "page_no", "bbox"].includes(key))
      && positive(value.page_no) && (!Object.hasOwn(value, "bbox") || bounds(value.bbox));
    case "TEXT_RANGE": return Object.keys(value).every(key => ["locator_type", "page_no", "section_path", "start_offset", "end_offset", "normalized_fingerprint"].includes(key))
      && Object.hasOwn(value, "start_offset") && Object.hasOwn(value, "end_offset") && Object.hasOwn(value, "normalized_fingerprint")
      && (Object.hasOwn(value, "page_no") !== Object.hasOwn(value, "section_path"))
      && (!Object.hasOwn(value, "page_no") || positive(value.page_no))
      && (!Object.hasOwn(value, "section_path") || boundedText(value.section_path, 1024))
      && nonnegative(value.start_offset) && positive(value.end_offset) && value.end_offset > value.start_offset
      && typeof value.normalized_fingerprint === "string" && /^[0-9a-f]{64}$/.test(value.normalized_fingerprint);
    case "SECTION": return exact(value, ["locator_type", "section_path"]) && boundedText(value.section_path, 1024);
    case "PARAGRAPH": return Object.keys(value).every(key => ["locator_type", "page_no", "paragraph_index", "stable_anchor"].includes(key))
      && (Object.hasOwn(value, "paragraph_index") !== Object.hasOwn(value, "stable_anchor"))
      && (!Object.hasOwn(value, "page_no") || positive(value.page_no))
      && (!Object.hasOwn(value, "paragraph_index") || positive(value.paragraph_index))
      && (!Object.hasOwn(value, "stable_anchor") || boundedText(value.stable_anchor, 256));
    case "TABLE_CELL": return exact(value, ["locator_type", "table_anchor", "row_no", "column_no"])
      && boundedText(value.table_anchor, 256) && positive(value.row_no) && positive(value.column_no);
    case "SHEET_RANGE": {
      if (!exact(value, ["locator_type", "sheet_name", "start_cell", "end_cell"]) || !boundedText(value.sheet_name, 128)) return false;
      const start = cell(value.start_cell); const end = cell(value.end_cell);
      return start !== null && end !== null && end[0] >= start[0] && end[1] >= start[1];
    }
    case "SLIDE_SHAPE": return Object.keys(value).every(key => ["locator_type", "slide_no", "shape_id", "bounds"].includes(key))
      && Object.hasOwn(value, "slide_no") && Object.hasOwn(value, "shape_id") && positive(value.slide_no)
      && boundedText(value.shape_id, 256) && (!Object.hasOwn(value, "bounds") || bounds(value.bounds));
    case "STRUCTURED_NODE": return !nested && exact(value, ["locator_type", "parse_record_id", "node_id", "source_locator"])
      && id(value.parse_record_id) && boundedText(value.node_id, 512) && locator(value.source_locator, true);
    default: return false;
  }
}

function sourceLocation(value: unknown, projectId: string, declared: Map<number, Set<string>>, inputKeys: Set<string>): AISourceLocation {
  if (!record(value) || !positive(value.source_ordinal) || value.source_ordinal > 1000 || !declared.has(value.source_ordinal)
      || !id(value.document_id) || !id(value.document_version_id)
      || !inputKeys.has(`DOC-02:${value.document_id}:${value.document_version_id}`)
      || (value.precision !== "DOCUMENT" && value.precision !== "PARSED_NODE") || !Array.isArray(value.locations)
      || value.locations.length < 1 || value.locations.length > 32) throw new AIReadError("AI_READ_UNAVAILABLE");
  const expectedUrl = `/api/v1/projects/${projectId}/documents/${value.document_id}/versions/${value.document_version_id}/content`;
  if (value.content_url !== expectedUrl) throw new AIReadError("AI_READ_UNAVAILABLE");
  const expectedNodes = declared.get(value.source_ordinal)!;
  const rawLocations = value.locations as unknown[];
  const foundNodes = new Set<string>();
  const locations: Readonly<Record<string, unknown>>[] = rawLocations.map(item => {
    if (!record(item) || !boundedText(item.display_label, 255) || item.precision !== value.precision || !locator(item.locator)) {
      throw new AIReadError("AI_READ_UNAVAILABLE");
    }
    if (value.precision === "DOCUMENT") {
      if (rawLocations.length !== 1 || !exact(item, ["locator", "precision", "display_label"])
          || item.locator.locator_type !== "DOCUMENT" || expectedNodes.size !== 0) throw new AIReadError("AI_READ_UNAVAILABLE");
      return freezeRecord({ locator: freezeRecord({ ...item.locator }), precision: "DOCUMENT", display_label: item.display_label });
    }
    if (!exact(item, ["node_id", "kind", "locator", "precision", "display_label"]) || !boundedText(item.node_id, 512)
        || typeof item.kind !== "string" || !nodeKinds.has(item.kind) || item.locator.locator_type !== "STRUCTURED_NODE"
        || item.locator.node_id !== item.node_id || !expectedNodes.has(item.node_id)) throw new AIReadError("AI_READ_UNAVAILABLE");
    foundNodes.add(item.node_id);
    return freezeRecord({ node_id: item.node_id, kind: item.kind, locator: freezeRecord({ ...item.locator }),
      precision: "PARSED_NODE", display_label: item.display_label });
  });
  if (value.precision === "PARSED_NODE" && (expectedNodes.size !== locations.length
      || foundNodes.size !== expectedNodes.size)) throw new AIReadError("AI_READ_UNAVAILABLE");
  return freezeRecord({ source_ordinal: value.source_ordinal, document_id: value.document_id,
    document_version_id: value.document_version_id, precision: value.precision as AISourceLocation["precision"],
    content_url: expectedUrl, locations: Object.freeze(locations) });
}

export function parseAISuggestion(value: unknown, projectId: string, taskId: string): AISuggestionView {
  if (!record(value) || !id(projectId) || !id(taskId) || value.ai_task_id !== taskId || value.project_id !== projectId
      || !id(value.ai_invocation_id) || !id(value.suggestion_payload_id)
      || typeof value.suggestion_state !== "string" || !suggestionStates.has(value.suggestion_state) || value.suggestion_state === "NONE"
      || value.fact_status !== "NOT_FORMAL_FACT" || !Array.isArray(value.quality_flags) || value.quality_flags.length > 64
      || !Array.isArray(value.input_versions) || value.input_versions.length < 1 || value.input_versions.length > 1000
      || !Array.isArray(value.source_locations) || value.source_locations.length < 1 || value.source_locations.length > 1000
      || !instant(value.created_at) || typeof value.etag !== "string" || !etagPattern.test(value.etag)) {
    throw new AIReadError("AI_READ_UNAVAILABLE");
  }
  const inputs = Object.freeze(value.input_versions.map(resource));
  const qualityFlags = value.quality_flags as unknown[];
  if (!qualityFlags.every(flag => typeof flag === "string" && namePattern.test(flag))
      || qualityFlags.some((flag, index) => index > 0 && String(qualityFlags[index - 1]) >= String(flag))) {
    throw new AIReadError("AI_READ_UNAVAILABLE");
  }
  const inputKeys = new Set(inputs.map(item => `${item.resource_type}:${item.resource_id}:${item.version_id}`));
  if (inputKeys.size !== inputs.length) throw new AIReadError("AI_READ_UNAVAILABLE");
  const schema = outputSchema(value.output_schema);
  const parsedPayload = payload(value.payload, schema);
  const locations = Object.freeze(value.source_locations.map(item => sourceLocation(item, projectId, parsedPayload.ordinals, inputKeys)));
  if (locations.some((item, index) => index > 0 && locations[index - 1]!.source_ordinal >= item.source_ordinal)
      || locations.length !== parsedPayload.ordinals.size) throw new AIReadError("AI_READ_UNAVAILABLE");
  return freezeRecord({ ai_task_id: taskId, ai_invocation_id: value.ai_invocation_id,
    suggestion_payload_id: value.suggestion_payload_id, project_id: projectId,
    suggestion_state: value.suggestion_state as AISuggestionView["suggestion_state"], fact_status: "NOT_FORMAL_FACT" as const,
    quality_flags: Object.freeze([...qualityFlags] as string[]), input_versions: inputs,
    provider: provider(value.provider), model: model(value.model), prompt_version_ref: prompt(value.prompt_version_ref),
    output_schema: schema, context: context(value.context), payload: parsedPayload.value,
    source_locations: locations, created_at: value.created_at, etag: value.etag });
}

export class AIReadClient {
  constructor(private readonly fetcher: typeof fetch = fetch, private readonly timeoutMs = 10_000) {
    if (!Number.isInteger(timeoutMs) || timeoutMs < 1 || timeoutMs > 30_000) throw new AIReadError("AI_READ_INVALID_INPUT");
  }

  async listTasks(projectId: string, pageSize = 50, cursor: string | null = null): Promise<AITaskPage> {
    this.#listInput(projectId, pageSize, cursor, taskCursor);
    const data = await this.#get(`/api/v1/projects/${projectId}/ai-tasks${this.#query(pageSize, cursor)}`);
    if (!record(data) || !Array.isArray(data.items) || data.items.length > pageSize) throw new AIReadError("AI_READ_UNAVAILABLE");
    const items = Object.freeze(data.items.map(item => parseAITask(item, projectId)));
    this.#page(data, items, taskCursor, item => item.ai_task_id);
    if (items.some((item, index) => index > 0 && (items[index - 1]!.requested_at < item.requested_at
        || items[index - 1]!.requested_at === item.requested_at && items[index - 1]!.ai_task_id <= item.ai_task_id))) {
      throw new AIReadError("AI_READ_UNAVAILABLE");
    }
    return freezeRecord({ items, next_cursor: data.next_cursor as string | null, has_more: data.has_more as boolean });
  }

  async getTask(projectId: string, taskId: string): Promise<AITaskView> {
    this.#ids(projectId, taskId);
    const result = await this.#get(`/api/v1/projects/${projectId}/ai-tasks/${taskId}`, true);
    const item = parseAITask(result.data, projectId, taskId);
    if (result.etag !== item.etag) throw new AIReadError("AI_READ_UNAVAILABLE");
    return item;
  }

  async listInvocations(projectId: string, taskId: string, pageSize = 50,
                        cursor: string | null = null): Promise<AIInvocationPage> {
    this.#ids(projectId, taskId); this.#listInput(projectId, pageSize, cursor, invocationCursor);
    const data = await this.#get(`/api/v1/projects/${projectId}/ai-tasks/${taskId}/invocations${this.#query(pageSize, cursor)}`);
    if (!record(data) || !Array.isArray(data.items) || data.items.length > pageSize) throw new AIReadError("AI_READ_UNAVAILABLE");
    const items = Object.freeze(data.items.map(item => parseAIInvocation(item, taskId)));
    this.#page(data, items, invocationCursor, item => item.ai_invocation_id);
    if (items.some((item, index) => index > 0 && items[index - 1]!.attempt_no <= item.attempt_no)) {
      throw new AIReadError("AI_READ_UNAVAILABLE");
    }
    return freezeRecord({ items, next_cursor: data.next_cursor as string | null, has_more: data.has_more as boolean });
  }

  async getSuggestion(projectId: string, taskId: string): Promise<AISuggestionView> {
    this.#ids(projectId, taskId);
    const result = await this.#get(`/api/v1/projects/${projectId}/ai-tasks/${taskId}/suggestion`, true);
    const item = parseAISuggestion(result.data, projectId, taskId);
    if (result.etag !== item.etag) throw new AIReadError("AI_READ_UNAVAILABLE");
    return item;
  }

  #ids(projectId: string, taskId: string): void {
    if (!id(projectId) || !id(taskId)) throw new AIReadError("AI_READ_INVALID_INPUT");
  }
  #listInput(projectId: string, pageSize: number, cursor: string | null, pattern: RegExp): void {
    if (!id(projectId) || !Number.isInteger(pageSize) || pageSize < 1 || pageSize > 100
        || (cursor !== null && !pattern.test(cursor))) throw new AIReadError("AI_READ_INVALID_INPUT");
  }
  #query(pageSize: number, cursor: string | null): string {
    const params = new URLSearchParams({ page_size: String(pageSize) });
    if (cursor !== null) params.set("cursor", cursor);
    return `?${params}`;
  }
  #page<T>(data: Record<string, unknown>, items: readonly T[], pattern: RegExp, key: (item: T) => string): void {
    if (typeof data.has_more !== "boolean"
        || (data.has_more && (typeof data.next_cursor !== "string" || !pattern.test(data.next_cursor) || items.length === 0))
        || (!data.has_more && data.next_cursor !== null) || new Set(items.map(key)).size !== items.length) {
      throw new AIReadError("AI_READ_UNAVAILABLE");
    }
  }

  async #get(path: string, includeEtag?: false): Promise<unknown>;
  async #get(path: string, includeEtag: true): Promise<{ data: unknown; etag: string | null }>;
  async #get(path: string, includeEtag = false): Promise<unknown> {
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      const fetcher = this.fetcher;
      const response = await fetcher(path, { method: "GET", credentials: "same-origin", cache: "no-store",
        redirect: "error", headers: { Accept: "application/json" }, signal: controller.signal });
      if (controller.signal.aborted || response.headers.get("content-type")?.split(";")[0].trim().toLowerCase() !== "application/json") {
        throw new AIReadError("AI_READ_UNAVAILABLE");
      }
      const body: unknown = await response.json();
      if (!record(body) || !id(body.trace_id)) throw new AIReadError("AI_READ_UNAVAILABLE");
      if (response.status !== 200) {
        const code = record(body.error) ? body.error.code : null;
        const expected: Record<string, number> = { AUTH_SESSION_EXPIRED: 401, LICENSE_OPERATION_DENIED: 403, RESOURCE_NOT_FOUND: 404 };
        if (typeof code === "string" && Object.hasOwn(expected, code) && response.status === expected[code]) {
          throw new AIReadError(code as AIReadErrorCode);
        }
        throw new AIReadError("AI_READ_UNAVAILABLE");
      }
      return includeEtag ? { data: body.data, etag: response.headers.get("etag") } : body.data;
    } catch (failure) {
      if (failure instanceof AIReadError) throw failure;
      throw new AIReadError("AI_READ_UNAVAILABLE");
    } finally { window.clearTimeout(timer); }
  }
}
