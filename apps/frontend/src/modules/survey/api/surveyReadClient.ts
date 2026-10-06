export type SurveyState = "ACTIVE" | "ARCHIVED" | "RESTRICTED";
export type SurveyVersionState = "DRAFT" | "IN_REVIEW" | "APPROVED" | "RETURNED" | "SUPERSEDED" | "RESTRICTED";
export type SurveyAnswerType = "TEXT" | "SINGLE_CHOICE" | "MULTIPLE_CHOICE" | "DATE" | "NUMBER" | "ATTACHMENT";
export type SurveySourceKind = "HANDOVER_ITEM" | "CAPABILITY_ITEM" | "TEMPLATE_DOCUMENT_VERSION" | "MANUAL";
export type SurveyCursor = string & { readonly __family: "surveys" };
export type SurveyVersionCursor = string & { readonly __family: "survey-versions" };

export interface SurveyView {
  readonly survey_id: string; readonly project_id: string; readonly name: string; readonly state: SurveyState;
  readonly current_approved_version_ref: string | null; readonly created_by: string; readonly created_at: string;
  readonly updated_by: string | null; readonly updated_at: string; readonly etag: string;
}
export interface SurveyOptionView {
  readonly option_code: string; readonly label: string; readonly description: string | null; readonly ordinal: number;
}
export interface SurveySourceView {
  readonly source_kind: SurveySourceKind;
  readonly handover_item_row_id: string | null; readonly handover_analysis_version_id: string | null;
  readonly handover_analysis_id: string | null; readonly capability_item_row_id: string | null;
  readonly capability_baseline_version_id: string | null; readonly capability_baseline_id: string | null;
  readonly template_document_version_id: string | null; readonly template_document_id: string | null;
  readonly manual_source_note: string | null; readonly ordinal: number;
}
export type SurveyConditionRule = Readonly<Record<string, unknown>>;
export interface SurveyQuestionView {
  readonly question_id: string; readonly sequence_no: number; readonly topic: string; readonly question_text: string;
  readonly objective: string; readonly answer_type: SurveyAnswerType;
  readonly validation_rule: Readonly<Record<string, unknown>>; readonly required: boolean;
  readonly condition_rule: SurveyConditionRule | null; readonly expected_output: string;
  readonly evidence_required: boolean; readonly options: readonly SurveyOptionView[];
  readonly sources: readonly SurveySourceView[];
}
export interface SurveyTargetDepartmentView { readonly department_id: string; readonly ordinal: number; }
export interface SurveyVersionView {
  readonly survey_version_id: string; readonly survey_id: string; readonly project_id: string;
  readonly version_no: number; readonly state: SurveyVersionState; readonly content_fingerprint: string;
  readonly declared_question_count: number; readonly declared_option_count: number;
  readonly declared_source_count: number; readonly declared_target_department_count: number;
  readonly supersedes_version_ref: string | null; readonly review_ref: string | null;
  readonly review_round_ref: string | null; readonly created_by: string; readonly created_at: string;
  readonly questions: readonly SurveyQuestionView[]; readonly target_departments: readonly SurveyTargetDepartmentView[];
}
export interface SurveyPage<T, C extends string> {
  readonly items: readonly T[]; readonly next_cursor: C | null; readonly has_more: boolean;
}

const messages = {
  SURVEY_READ_INVALID_INPUT: "项目、调研定义、版本或翻页参数无效。",
  AUTH_SESSION_EXPIRED: "会话已失效，请重新登录。",
  LICENSE_OPERATION_DENIED: "当前许可不允许读取项目调研定义。",
  RESOURCE_NOT_FOUND: "调研定义不存在，或当前账户无权查看。",
  PROJECT_ARCHIVED: "项目已归档，当前调研定义不可读取。",
  SURVEY_READ_UNAVAILABLE: "暂时无法读取项目调研定义，请稍后重试。",
} as const;
export type SurveyReadErrorCode = keyof typeof messages;
export class SurveyReadError extends Error {
  constructor(readonly code: SurveyReadErrorCode) { super(messages[code]); this.name = "SurveyReadError"; }
}

const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const cursor = /^[A-Za-z0-9_-]{1,1024}\.[A-Za-z0-9_-]{43}$/;
const etag = /^"v(0|[1-9][0-9]*)"$/; const digest = /^[0-9a-f]{64}$/;
const optionCode = /^[A-Z][A-Z0-9_-]{0,31}$/; const extension = /^\.[a-z0-9]{1,16}$/;
const surveyStates = new Set<SurveyState>(["ACTIVE", "ARCHIVED", "RESTRICTED"]);
const versionStates = new Set<SurveyVersionState>(["DRAFT", "IN_REVIEW", "APPROVED", "RETURNED", "SUPERSEDED", "RESTRICTED"]);
const answerTypes = new Set<SurveyAnswerType>(["TEXT", "SINGLE_CHOICE", "MULTIPLE_CHOICE", "DATE", "NUMBER", "ATTACHMENT"]);
const sourceKinds = new Set<SurveySourceKind>(["HANDOVER_ITEM", "CAPABILITY_ITEM", "TEMPLATE_DOCUMENT_VERSION", "MANUAL"]);
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
function integer(value: unknown, minimum = 0, maximum = Number.MAX_SAFE_INTEGER): value is number {
  return typeof value === "number" && Number.isSafeInteger(value) && value >= minimum && value <= maximum;
}
function text(value: unknown, maximum: number): value is string {
  return typeof value === "string" && value.length > 0 && value.length <= maximum
    && value.trim() === value && !/\p{C}/u.test(value);
}
function instant(value: unknown): value is string {
  return typeof value === "string" && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$/.test(value)
    && Number.isFinite(Date.parse(value));
}
function frozen<T extends object>(value: T): Readonly<T> { return Object.freeze(value); }
function finite(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}
function frozenJson(value: unknown): unknown {
  if (Array.isArray(value)) return Object.freeze(value.map(frozenJson));
  if (record(value)) return Object.freeze(Object.fromEntries(Object.entries(value).map(
    ([key, item]) => [key, frozenJson(item)])));
  return value;
}

const surveyFields = ["survey_id", "project_id", "name", "state", "current_approved_version_ref", "created_by",
  "created_at", "updated_by", "updated_at", "etag"] as const;
export function parseSurvey(value: unknown, projectId: string, surveyId?: string): SurveyView {
  if (!record(value) || !exact(value, surveyFields) || !id(value.survey_id)
    || surveyId !== undefined && value.survey_id !== surveyId || value.project_id !== projectId
    || !text(value.name, 255) || !surveyStates.has(value.state as SurveyState)
    || !optionalId(value.current_approved_version_ref) || !id(value.created_by) || !instant(value.created_at)
    || !optionalId(value.updated_by) || !instant(value.updated_at)
    || Date.parse(value.updated_at) < Date.parse(value.created_at) || typeof value.etag !== "string" || !etag.test(value.etag)) {
    throw new SurveyReadError("SURVEY_READ_UNAVAILABLE");
  }
  return frozen({ survey_id: value.survey_id, project_id: projectId, name: value.name,
    state: value.state as SurveyState, current_approved_version_ref: value.current_approved_version_ref,
    created_by: value.created_by, created_at: value.created_at, updated_by: value.updated_by,
    updated_at: value.updated_at, etag: value.etag });
}

function validationRule(value: unknown, answerType: SurveyAnswerType, optionCount: number): Readonly<Record<string, unknown>> {
  if (!record(value)) throw new SurveyReadError("SURVEY_READ_UNAVAILABLE");
  const keys = new Set(Object.keys(value));
  const only = (...allowed: string[]) => [...keys].every(key => allowed.includes(key));
  let valid = false;
  if (answerType === "TEXT" && only("min_length", "max_length")) {
    const minimum = value.min_length ?? 0; const maximum = value.max_length ?? 4000;
    valid = integer(minimum, 0, 4000) && integer(maximum, 0, 4000) && minimum <= maximum;
  } else if (answerType === "NUMBER" && only("minimum", "maximum", "integer")) {
    const minimum = value.minimum ?? null; const maximum = value.maximum ?? null; const whole = value.integer ?? false;
    valid = (minimum === null || finite(minimum)) && (maximum === null || finite(maximum)) && typeof whole === "boolean"
      && (minimum === null || maximum === null || minimum <= maximum);
  } else if (answerType === "DATE" && only("minimum", "maximum")) {
    const minimum = value.minimum ?? null; const maximum = value.maximum ?? null;
    const date = (item: unknown) => {
      if (item === null) return true;
      if (typeof item !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(item)) return false;
      const parsed = Date.parse(`${item}T00:00:00Z`);
      return Number.isFinite(parsed) && new Date(parsed).toISOString().slice(0, 10) === item;
    };
    valid = date(minimum) && date(maximum) && (minimum === null || maximum === null || minimum <= maximum);
  } else if (answerType === "MULTIPLE_CHOICE" && only("min_selections", "max_selections")) {
    const minimum = value.min_selections ?? 0; const maximum = value.max_selections ?? optionCount;
    valid = integer(minimum, 0, optionCount) && integer(maximum, 0, optionCount) && minimum <= maximum;
  } else if (answerType === "ATTACHMENT" && only("min_files", "max_files", "allowed_extensions")) {
    const minimum = value.min_files ?? 0; const maximum = value.max_files ?? 20;
    const extensions = value.allowed_extensions ?? [];
    valid = integer(minimum, 0, 20) && integer(maximum, 0, 20) && minimum <= maximum
      && Array.isArray(extensions) && extensions.length <= 50
      && extensions.every(item => typeof item === "string" && extension.test(item))
      && new Set(extensions).size === extensions.length;
  } else if (answerType === "SINGLE_CHOICE" && keys.size === 0) valid = true;
  if (!valid) throw new SurveyReadError("SURVEY_READ_UNAVAILABLE");
  return frozenJson(value) as Readonly<Record<string, unknown>>;
}

function conditionRule(value: unknown): SurveyConditionRule {
  let leaves = 0;
  const visit = (node: unknown, depth: number): SurveyConditionRule => {
    if (depth > 8 || !record(node) || Object.keys(node).length === 0) throw new SurveyReadError("SURVEY_READ_UNAVAILABLE");
    const groups = ["all", "any"].filter(key => Object.hasOwn(node, key));
    if (groups.length > 0) {
      if (groups.length !== 1 || Object.keys(node).length !== 1) throw new SurveyReadError("SURVEY_READ_UNAVAILABLE");
      const children = node[groups[0]!];
      if (!Array.isArray(children) || children.length < 1 || children.length > 20) throw new SurveyReadError("SURVEY_READ_UNAVAILABLE");
      return frozen({ [groups[0]!]: Object.freeze(children.map(child => visit(child, depth + 1))) });
    }
    if (!["question_ref", "operator", "value"].every((key, index) => index < 2 ? Object.hasOwn(node, key) : true)
      || Object.keys(node).some(key => !["question_ref", "operator", "value"].includes(key)) || !id(node.question_ref)
      || typeof node.operator !== "string" || ++leaves > 100) throw new SurveyReadError("SURVEY_READ_UNAVAILABLE");
    const unary = node.operator === "ANSWERED" || node.operator === "NOT_ANSWERED";
    const valued = ["EQUALS", "NOT_EQUALS", "IN", "NOT_IN"].includes(node.operator);
    if (!unary && !valued || unary && Object.hasOwn(node, "value") || valued && !Object.hasOwn(node, "value")) {
      throw new SurveyReadError("SURVEY_READ_UNAVAILABLE");
    }
    const scalar = (item: unknown) => item === null || typeof item === "boolean" || typeof item === "string" && item.length <= 2000
      || integer(item, -(2 ** 53), 2 ** 53) || finite(item);
    if (valued) {
      const item = node.value;
      if ((node.operator === "IN" || node.operator === "NOT_IN")
        ? !Array.isArray(item) || item.length < 1 || item.length > 100 || !item.every(scalar)
          || new Set(item.map(entry => `${typeof entry}:${JSON.stringify(entry)}`)).size !== item.length
        : !scalar(item)) throw new SurveyReadError("SURVEY_READ_UNAVAILABLE");
    }
    return frozen(Object.hasOwn(node, "value")
      ? { question_ref: node.question_ref, operator: node.operator, value: frozenJson(node.value) }
      : { question_ref: node.question_ref, operator: node.operator });
  };
  return visit(value, 1);
}

const optionFields = ["option_code", "label", "description", "ordinal"] as const;
function parseOption(value: unknown, ordinal: number): SurveyOptionView {
  if (!record(value) || !exact(value, optionFields) || typeof value.option_code !== "string" || !optionCode.test(value.option_code)
    || !text(value.label, 255) || value.description !== null && !text(value.description, 1000) || value.ordinal !== ordinal) {
    throw new SurveyReadError("SURVEY_READ_UNAVAILABLE");
  }
  return frozen({ option_code: value.option_code, label: value.label, description: value.description, ordinal });
}

const sourceFields = ["source_kind", "handover_item_row_id", "handover_analysis_version_id", "handover_analysis_id",
  "capability_item_row_id", "capability_baseline_version_id", "capability_baseline_id", "template_document_version_id",
  "template_document_id", "manual_source_note", "ordinal"] as const;
function parseSource(value: unknown, ordinal: number): SurveySourceView {
  if (!record(value) || !exact(value, sourceFields) || !sourceKinds.has(value.source_kind as SurveySourceKind)
    || value.ordinal !== ordinal) throw new SurveyReadError("SURVEY_READ_UNAVAILABLE");
  const groups = [["handover_item_row_id", "handover_analysis_version_id", "handover_analysis_id"],
    ["capability_item_row_id", "capability_baseline_version_id", "capability_baseline_id"],
    ["template_document_version_id", "template_document_id"]] as const;
  const expected = value.source_kind === "HANDOVER_ITEM" ? 0 : value.source_kind === "CAPABILITY_ITEM" ? 1
    : value.source_kind === "TEMPLATE_DOCUMENT_VERSION" ? 2 : -1;
  for (const [index, fields] of groups.entries()) {
    if (fields.some(field => !optionalId(value[field])) || fields.some(field => value[field] !== null) !== (index === expected)
      || index === expected && fields.some(field => !id(value[field]))) throw new SurveyReadError("SURVEY_READ_UNAVAILABLE");
  }
  if (value.source_kind === "MANUAL" ? !text(value.manual_source_note, 2000) : value.manual_source_note !== null) {
    throw new SurveyReadError("SURVEY_READ_UNAVAILABLE");
  }
  return frozen({ source_kind: value.source_kind as SurveySourceKind,
    handover_item_row_id: value.handover_item_row_id as string | null,
    handover_analysis_version_id: value.handover_analysis_version_id as string | null,
    handover_analysis_id: value.handover_analysis_id as string | null,
    capability_item_row_id: value.capability_item_row_id as string | null,
    capability_baseline_version_id: value.capability_baseline_version_id as string | null,
    capability_baseline_id: value.capability_baseline_id as string | null,
    template_document_version_id: value.template_document_version_id as string | null,
    template_document_id: value.template_document_id as string | null,
    manual_source_note: value.manual_source_note as string | null, ordinal });
}

const questionFields = ["question_id", "sequence_no", "topic", "question_text", "objective", "answer_type",
  "validation_rule", "required", "condition_rule", "expected_output", "evidence_required", "options", "sources"] as const;
function parseQuestion(value: unknown, sequence: number): SurveyQuestionView {
  if (!record(value) || !exact(value, questionFields) || !id(value.question_id) || value.sequence_no !== sequence
    || !text(value.topic, 255) || !text(value.question_text, 4000) || !text(value.objective, 2000)
    || !answerTypes.has(value.answer_type as SurveyAnswerType) || typeof value.required !== "boolean"
    || !text(value.expected_output, 2000) || typeof value.evidence_required !== "boolean"
    || !Array.isArray(value.options) || !Array.isArray(value.sources) || value.sources.length < 1 || value.sources.length > 20) {
    throw new SurveyReadError("SURVEY_READ_UNAVAILABLE");
  }
  const answer = value.answer_type as SurveyAnswerType;
  const options = value.options.map((item, ordinal) => parseOption(item, ordinal));
  if ((answer === "SINGLE_CHOICE" || answer === "MULTIPLE_CHOICE") ? options.length < 2 : options.length !== 0) {
    throw new SurveyReadError("SURVEY_READ_UNAVAILABLE");
  }
  if (new Set(options.map(item => item.option_code)).size !== options.length) throw new SurveyReadError("SURVEY_READ_UNAVAILABLE");
  const sources = value.sources.map((item, ordinal) => parseSource(item, ordinal));
  return frozen({ question_id: value.question_id, sequence_no: sequence, topic: value.topic,
    question_text: value.question_text, objective: value.objective, answer_type: answer,
    validation_rule: validationRule(value.validation_rule, answer, options.length), required: value.required,
    condition_rule: value.condition_rule === null ? null : conditionRule(value.condition_rule),
    expected_output: value.expected_output, evidence_required: value.evidence_required,
    options: Object.freeze(options), sources: Object.freeze(sources) });
}

const versionFields = ["survey_version_id", "survey_id", "project_id", "version_no", "state", "content_fingerprint",
  "declared_question_count", "declared_option_count", "declared_source_count", "declared_target_department_count",
  "supersedes_version_ref", "review_ref", "review_round_ref", "created_by", "created_at", "questions",
  "target_departments"] as const;
export function parseSurveyVersion(value: unknown, projectId: string, surveyId: string,
                                   versionId?: string): SurveyVersionView {
  if (!record(value) || !exact(value, versionFields) || !id(value.survey_version_id)
    || versionId !== undefined && value.survey_version_id !== versionId || value.survey_id !== surveyId
    || value.project_id !== projectId || !integer(value.version_no, 1)
    || !versionStates.has(value.state as SurveyVersionState) || typeof value.content_fingerprint !== "string"
    || !digest.test(value.content_fingerprint) || !integer(value.declared_question_count, 1, 500)
    || !integer(value.declared_option_count, 0, 100_000) || !integer(value.declared_source_count, 1, 10_000)
    || !integer(value.declared_target_department_count, 1, 200) || !optionalId(value.supersedes_version_ref)
    || !optionalId(value.review_ref) || !optionalId(value.review_round_ref)
    || (value.review_ref === null) !== (value.review_round_ref === null) || !id(value.created_by) || !instant(value.created_at)
    || !Array.isArray(value.questions) || !Array.isArray(value.target_departments)
    || value.questions.length !== value.declared_question_count
    || value.target_departments.length !== value.declared_target_department_count) {
    throw new SurveyReadError("SURVEY_READ_UNAVAILABLE");
  }
  const questions = value.questions.map((item, sequence) => parseQuestion(item, sequence));
  if (new Set(questions.map(item => item.question_id)).size !== questions.length
    || questions.reduce((count, item) => count + item.options.length, 0) !== value.declared_option_count
    || questions.reduce((count, item) => count + item.sources.length, 0) !== value.declared_source_count) {
    throw new SurveyReadError("SURVEY_READ_UNAVAILABLE");
  }
  const targets = value.target_departments.map((item, ordinal): SurveyTargetDepartmentView => {
    if (!record(item) || !exact(item, ["department_id", "ordinal"]) || !id(item.department_id) || item.ordinal !== ordinal) {
      throw new SurveyReadError("SURVEY_READ_UNAVAILABLE");
    }
    return frozen({ department_id: item.department_id, ordinal });
  });
  if (new Set(targets.map(item => item.department_id)).size !== targets.length) throw new SurveyReadError("SURVEY_READ_UNAVAILABLE");
  return frozen({ survey_version_id: value.survey_version_id, survey_id: surveyId, project_id: projectId,
    version_no: value.version_no, state: value.state as SurveyVersionState, content_fingerprint: value.content_fingerprint,
    declared_question_count: value.declared_question_count, declared_option_count: value.declared_option_count,
    declared_source_count: value.declared_source_count, declared_target_department_count: value.declared_target_department_count,
    supersedes_version_ref: value.supersedes_version_ref, review_ref: value.review_ref,
    review_round_ref: value.review_round_ref, created_by: value.created_by, created_at: value.created_at,
    questions: Object.freeze(questions), target_departments: Object.freeze(targets) });
}

export class SurveyReadClient {
  constructor(private readonly fetcher: typeof fetch = fetch, private readonly timeoutMs = 10_000) {
    if (!integer(timeoutMs, 1, 30_000)) throw new SurveyReadError("SURVEY_READ_INVALID_INPUT");
  }
  async listSurveys(projectId: string, pageSize = 50, next: SurveyCursor | null = null):
      Promise<SurveyPage<SurveyView, SurveyCursor>> {
    this.#listInput([projectId], pageSize, next);
    return await this.#page(`/api/v1/projects/${projectId}/surveys${this.#query(pageSize, next)}`, pageSize, next,
      item => parseSurvey(item, projectId), "survey") as SurveyPage<SurveyView, SurveyCursor>;
  }
  async getSurvey(projectId: string, surveyId: string): Promise<SurveyView> {
    this.#ids(projectId, surveyId);
    const response = await this.#get(`/api/v1/projects/${projectId}/surveys/${surveyId}`, true);
    const value = parseSurvey(response.data, projectId, surveyId);
    if (response.etag !== value.etag) throw new SurveyReadError("SURVEY_READ_UNAVAILABLE");
    return value;
  }
  async listVersions(projectId: string, surveyId: string, pageSize = 50, next: SurveyVersionCursor | null = null):
      Promise<SurveyPage<SurveyVersionView, SurveyVersionCursor>> {
    this.#listInput([projectId, surveyId], pageSize, next);
    return await this.#page(`/api/v1/projects/${projectId}/surveys/${surveyId}/versions${this.#query(pageSize, next)}`,
      pageSize, next, item => parseSurveyVersion(item, projectId, surveyId), "version") as SurveyPage<SurveyVersionView, SurveyVersionCursor>;
  }
  async getVersion(projectId: string, surveyId: string, versionId: string): Promise<SurveyVersionView> {
    this.#ids(projectId, surveyId, versionId);
    const data = await this.#get(`/api/v1/projects/${projectId}/surveys/${surveyId}/versions/${versionId}`);
    return parseSurveyVersion(data, projectId, surveyId, versionId);
  }
  #ids(...values: string[]): void {
    if (values.some(value => !id(value))) throw new SurveyReadError("SURVEY_READ_INVALID_INPUT");
  }
  #listInput(values: string[], pageSize: number, next: string | null): void {
    this.#ids(...values);
    if (!integer(pageSize, 1, 200) || next !== null && (typeof next !== "string" || !cursor.test(next))) {
      throw new SurveyReadError("SURVEY_READ_INVALID_INPUT");
    }
  }
  #query(pageSize: number, next: string | null): string {
    const query = new URLSearchParams({ page_size: String(pageSize) });
    if (next !== null) query.set("cursor", next); return `?${query}`;
  }
  async #page<T>(path: string, size: number, previous: string | null, parse: (item: unknown) => T,
                 order: "survey" | "version"): Promise<SurveyPage<T, string>> {
    const data = await this.#get(path);
    if (!record(data) || !exact(data, ["items", "next_cursor", "has_more"]) || !Array.isArray(data.items)
      || data.items.length > size || typeof data.has_more !== "boolean"
      || data.has_more && (data.items.length === 0 || typeof data.next_cursor !== "string" || !cursor.test(data.next_cursor)
        || data.next_cursor === previous) || !data.has_more && data.next_cursor !== null) {
      throw new SurveyReadError("SURVEY_READ_UNAVAILABLE");
    }
    const items = data.items.map(parse) as (T & Record<string, unknown>)[];
    const key = order === "survey" ? "survey_id" : "survey_version_id";
    if (new Set(items.map(item => item[key])).size !== items.length || items.some((item, index) => index > 0 && (
      order === "survey" ? String(items[index - 1]!.updated_at) < String(item.updated_at)
        || items[index - 1]!.updated_at === item.updated_at && String(items[index - 1]![key]) <= String(item[key])
        : Number(items[index - 1]!.version_no) <= Number(item.version_no)))) {
      throw new SurveyReadError("SURVEY_READ_UNAVAILABLE");
    }
    return frozen({ items: Object.freeze(items) as readonly T[], next_cursor: data.next_cursor as string | null,
      has_more: data.has_more });
  }
  async #get(path: string, includeEtag?: false): Promise<unknown>;
  async #get(path: string, includeEtag: true): Promise<{ data: unknown; etag: string | null }>;
  async #get(path: string, includeEtag = false): Promise<unknown> {
    const controller = new AbortController(); const timer = window.setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      const fetcher = this.fetcher;
      const response = await fetcher(path, { method: "GET", credentials: "same-origin", cache: "no-store",
        redirect: "error", headers: { Accept: "application/json" }, signal: controller.signal });
      if (controller.signal.aborted || response.headers.get("content-type")?.split(";")[0].trim().toLowerCase() !== "application/json") {
        throw new SurveyReadError("SURVEY_READ_UNAVAILABLE");
      }
      const payload: unknown = await response.json();
      if (!record(payload) || !id(payload.trace_id)) throw new SurveyReadError("SURVEY_READ_UNAVAILABLE");
      if (response.status !== 200) {
        const code = record(payload.error) ? payload.error.code : null;
        const expected: Readonly<Record<string, number>> = { AUTH_SESSION_EXPIRED: 401, LICENSE_OPERATION_DENIED: 403,
          RESOURCE_NOT_FOUND: 404, PROJECT_ARCHIVED: 409 };
        if (typeof code === "string" && expected[code] === response.status) throw new SurveyReadError(code as SurveyReadErrorCode);
        throw new SurveyReadError("SURVEY_READ_UNAVAILABLE");
      }
      if (!exact(payload, ["data", "trace_id"])) throw new SurveyReadError("SURVEY_READ_UNAVAILABLE");
      return includeEtag ? { data: payload.data, etag: response.headers.get("etag") } : payload.data;
    } catch (failure) {
      if (failure instanceof SurveyReadError) throw failure;
      throw new SurveyReadError("SURVEY_READ_UNAVAILABLE");
    } finally { window.clearTimeout(timer); }
  }
}
