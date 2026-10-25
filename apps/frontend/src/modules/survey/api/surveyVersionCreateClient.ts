/** Frozen Survey DRAFT version command. Source candidates and questions still need human review. */
import { SessionClient, SessionClientError } from "@/modules/auth/api/sessionClient";
import type { SurveyAnswerType, SurveySourceKind } from "./surveyReadClient";

export interface SurveyVersionSourceDraft {
  readonly source_kind: SurveySourceKind;
  readonly handover_item_row_id: string | null;
  readonly handover_analysis_version_id: string | null;
  readonly handover_analysis_id: string | null;
  readonly capability_item_row_id: string | null;
  readonly capability_baseline_version_id: string | null;
  readonly capability_baseline_id: string | null;
  readonly template_document_version_id: string | null;
  readonly template_document_id: string | null;
  readonly manual_source_note: string | null;
}
export interface SurveyVersionQuestionDraft {
  readonly question_id: string; readonly topic: string; readonly question_text: string;
  readonly objective: string; readonly answer_type: SurveyAnswerType;
  readonly validation_rule: Readonly<Record<string, unknown>>; readonly required: boolean;
  readonly condition_rule: Readonly<Record<string, unknown>> | null;
  readonly expected_output: string; readonly evidence_required: boolean;
  readonly options: readonly Readonly<{ option_code: string; label: string;
    description: string | null }>[];
  readonly sources: readonly SurveyVersionSourceDraft[];
}
export interface SurveyVersionCreateInput {
  readonly questions: readonly SurveyVersionQuestionDraft[];
  readonly target_department_ids: readonly string[];
}
export interface SurveyVersionCreateReceipt {
  readonly survey_version_id: string; readonly survey_id: string; readonly project_id: string;
  readonly version_no: number; readonly state: "DRAFT"; readonly content_fingerprint: string;
  readonly supersedes_version_ref: string | null; readonly created_at: string;
  readonly survey_etag: string;
}
const messages = {
  INVALID_INPUT: "请核对问题、人工访谈依据、固定来源和目标部门。",
  UNCERTAIN: "提交结果无法确认；请保留原问题、版本标记和操作号，核对版本列表。",
  AUTH_RELOGIN_REQUIRED: "请重新登录后提交。",
  AUTH_CLIENT_BUSY: "会话正在处理其他操作。",
  AUTH_SESSION_EXPIRED: "会话已失效。",
  AUTH_CSRF_INVALID: "登录状态已变化。",
  LICENSE_OPERATION_DENIED: "当前许可不允许创建调研版本。",
  RESOURCE_NOT_FOUND: "调研定义不存在或当前账户无权创建版本。",
  VALIDATION_FAILED: "固定来源、目标部门或问题内容不合格，请重新读取。",
  CONFLICT_VERSION: "调研定义版本已变化，请刷新后重新确认。",
  CONFLICT_STATE: "调研定义当前状态不允许新增版本。",
  CONFLICT_IDEMPOTENCY: "原操作号与当前内容冲突，请核对历史。",
  PROJECT_ARCHIVED: "项目已归档，不能新增调研版本。",
  SYSTEM_UNAVAILABLE: "服务暂不可用，请保留原操作号并核对版本列表。",
} as const;
export type SurveyVersionCreateErrorCode = keyof typeof messages;
export class SurveyVersionCreateError extends Error {
  readonly uncertain: boolean;
  constructor(readonly code: SurveyVersionCreateErrorCode) {
    super(messages[code]); this.name = "SurveyVersionCreateError";
    this.uncertain = code === "UNCERTAIN";
  }
}

const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const etag = /^"v(0|[1-9][0-9]*)"$/;
const keyPattern = /^[\x20-\x7e]{16,128}$/;
const digest = /^[0-9a-f]{64}$/;
const stamp = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$/;
const sourceFields = ["source_kind", "handover_item_row_id", "handover_analysis_version_id",
  "handover_analysis_id", "capability_item_row_id", "capability_baseline_version_id",
  "capability_baseline_id", "template_document_version_id", "template_document_id",
  "manual_source_note"] as const;
function id(value: unknown): value is string {
  return typeof value === "string" && uuid.test(value)
    && value !== "00000000-0000-0000-0000-000000000000";
}
function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
function exact(value: Record<string, unknown>, fields: readonly string[]): boolean {
  return Object.keys(value).length === fields.length && fields.every(field => Object.hasOwn(value, field));
}
function text(value: unknown, max: number): value is string {
  return typeof value === "string" && value.length >= 1 && value.length <= max
    && value === value.trim() && !/\p{C}/u.test(value);
}
function invalid(): never { throw new SurveyVersionCreateError("INVALID_INPUT"); }
function uncertain(): never { throw new SurveyVersionCreateError("UNCERTAIN"); }

function source(value: unknown): value is SurveyVersionSourceDraft {
  if (!record(value) || !exact(value, sourceFields)) return false;
  const groups = [[value.handover_item_row_id, value.handover_analysis_version_id,
    value.handover_analysis_id], [value.capability_item_row_id,
    value.capability_baseline_version_id, value.capability_baseline_id],
  [value.template_document_version_id, value.template_document_id]];
  const expected = { HANDOVER_ITEM: 0, CAPABILITY_ITEM: 1,
    TEMPLATE_DOCUMENT_VERSION: 2, MANUAL: -1 }[String(value.source_kind)];
  if (expected === undefined || !groups.every((group, index) =>
    group.every(part => index === expected ? id(part) : part === null))) return false;
  return expected === -1 ? text(value.manual_source_note, 2000) : value.manual_source_note === null;
}
function question(value: unknown): value is SurveyVersionQuestionDraft {
  if (!record(value) || !exact(value, ["question_id", "topic", "question_text", "objective",
    "answer_type", "validation_rule", "required", "condition_rule", "expected_output",
    "evidence_required", "options", "sources"])
    || !id(value.question_id) || !text(value.topic, 255)
    || !text(value.question_text, 4000) || !text(value.objective, 2000)
    || !["TEXT", "SINGLE_CHOICE", "MULTIPLE_CHOICE", "DATE", "NUMBER", "ATTACHMENT"].includes(String(value.answer_type))
    || !record(value.validation_rule) || value.condition_rule !== null && !record(value.condition_rule)
    || typeof value.required !== "boolean" || !text(value.expected_output, 2000)
    || typeof value.evidence_required !== "boolean" || !Array.isArray(value.options)
    || !Array.isArray(value.sources) || value.sources.length < 1 || value.sources.length > 20
    || !value.sources.every(source)) return false;
  const choices = value.answer_type === "SINGLE_CHOICE" || value.answer_type === "MULTIPLE_CHOICE";
  if (choices ? value.options.length < 2 : value.options.length !== 0) return false;
  const codes = new Set<string>();
  return value.options.every((option: unknown) => {
    if (!record(option) || !exact(option, ["option_code", "label", "description"])
      || typeof option.option_code !== "string"
      || !/^[A-Z][A-Z0-9_-]{0,31}$/.test(option.option_code)
      || codes.has(option.option_code) || !text(option.label, 255)
      || option.description !== null && !text(option.description, 1000)) return false;
    codes.add(option.option_code);
    return true;
  });
}
export function handoverItemSource(candidate: {
  readonly handover_item_row_id: string; readonly handover_analysis_version_id: string;
  readonly handover_analysis_id: string;
}): SurveyVersionSourceDraft {
  if (!id(candidate?.handover_item_row_id) || !id(candidate.handover_analysis_version_id)
    || !id(candidate.handover_analysis_id)) invalid();
  return Object.freeze({ source_kind: "HANDOVER_ITEM", handover_item_row_id: candidate.handover_item_row_id,
    handover_analysis_version_id: candidate.handover_analysis_version_id,
    handover_analysis_id: candidate.handover_analysis_id, capability_item_row_id: null,
    capability_baseline_version_id: null, capability_baseline_id: null,
    template_document_version_id: null, template_document_id: null,
    manual_source_note: null });
}
export function manualSurveySource(note: string): SurveyVersionSourceDraft {
  if (!text(note, 2000)) invalid();
  return Object.freeze({ source_kind: "MANUAL", handover_item_row_id: null,
    handover_analysis_version_id: null, handover_analysis_id: null,
    capability_item_row_id: null, capability_baseline_version_id: null,
    capability_baseline_id: null, template_document_version_id: null,
    template_document_id: null, manual_source_note: note });
}

export function validateSurveyVersionCreateInput(value: unknown): SurveyVersionCreateInput {
  if (!record(value) || !exact(value, ["questions", "target_department_ids"])
    || !Array.isArray(value.questions) || value.questions.length < 1 || value.questions.length > 500
    || !value.questions.every(question)
    || new Set(value.questions.map(item => item.question_id)).size !== value.questions.length
    || !Array.isArray(value.target_department_ids) || value.target_department_ids.length < 1
    || value.target_department_ids.length > 200 || !value.target_department_ids.every(id)
    || new Set(value.target_department_ids).size !== value.target_department_ids.length) invalid();
  return value as unknown as SurveyVersionCreateInput;
}

export class SurveyVersionCreateClient {
  constructor(private readonly session: SessionClient) {
    if (!(session instanceof SessionClient)) invalid();
  }
  async create(projectId: string, surveyId: string, surveyEtag: string,
    input: SurveyVersionCreateInput, key: string): Promise<SurveyVersionCreateReceipt> {
    const lock = typeof surveyEtag === "string" && etag.test(surveyEtag)
      ? Number(surveyEtag.slice(2, -1)) : null;
    if (!id(projectId) || !id(surveyId) || lock === null || !Number.isSafeInteger(lock)
      || lock >= Number.MAX_SAFE_INTEGER || typeof key !== "string" || !keyPattern.test(key)) invalid();
    validateSurveyVersionCreateInput(input);
    const identity = this.session.view;
    if (!identity || identity.password_change_required || !this.session.canSubmit
      || !identity.authorized_projects.some(item => item.project_id === projectId
        && (item.role === "PROJECT_MANAGER" || item.role === "IMPLEMENTATION_MEMBER"))) {
      throw new SurveyVersionCreateError("RESOURCE_NOT_FOUND");
    }
    let body: string;
    try { body = JSON.stringify({ questions: input.questions,
      target_department_ids: input.target_department_ids }); }
    catch { return invalid(); }
    let response: Response;
    try {
      response = await this.session.postProjectSurveyVersionCreate(
        projectId, surveyId, body, surveyEtag, key);
    } catch (failure) {
      if (failure instanceof SessionClientError && (failure.code === "AUTH_RELOGIN_REQUIRED"
        || failure.code === "AUTH_CLIENT_BUSY")) {
        throw new SurveyVersionCreateError(failure.code);
      }
      return uncertain();
    }
    try {
      if (response.headers.get("content-type")?.split(";")[0].trim().toLowerCase() !== "application/json"
        || response.headers.get("cache-control") !== "no-store") uncertain();
      const payload: unknown = await response.json();
      if (!record(payload) || !id(payload.trace_id)
        || response.headers.get("x-trace-id") !== payload.trace_id) uncertain();
      if (response.status !== 201) {
        const code = record(payload.error) ? payload.error.code : null;
        const statuses: Readonly<Record<string, number>> = {
          AUTH_SESSION_EXPIRED: 401, AUTH_CSRF_INVALID: 403,
          LICENSE_OPERATION_DENIED: 403, RESOURCE_NOT_FOUND: 404,
          VALIDATION_FAILED: 422, CONFLICT_VERSION: 409, CONFLICT_STATE: 409,
          CONFLICT_IDEMPOTENCY: 409, PROJECT_ARCHIVED: 409, SYSTEM_UNAVAILABLE: 503,
        };
        if (typeof code === "string" && statuses[code] === response.status) {
          throw new SurveyVersionCreateError(code as SurveyVersionCreateErrorCode);
        }
        uncertain();
      }
      if (!exact(payload, ["data", "trace_id"]) || !record(payload.data)) uncertain();
      const value = payload.data;
      if (!exact(value, ["survey_version_id", "survey_id", "project_id", "version_no",
        "state", "content_fingerprint", "supersedes_version_ref", "created_at", "survey_etag"])
        || !id(value.survey_version_id) || value.survey_id !== surveyId
        || value.project_id !== projectId || !Number.isSafeInteger(value.version_no)
        || Number(value.version_no) < 1 || value.state !== "DRAFT"
        || typeof value.content_fingerprint !== "string" || !digest.test(value.content_fingerprint)
        || value.supersedes_version_ref !== null && !id(value.supersedes_version_ref)
        || typeof value.created_at !== "string" || !stamp.test(value.created_at)
        || !Number.isFinite(Date.parse(value.created_at))
        || value.survey_etag !== `"v${lock + 1}"`
        || response.headers.get("etag") !== value.survey_etag
        || response.headers.get("location") !== `/api/v1/projects/${projectId}/surveys/${surveyId}/versions/${value.survey_version_id}`) uncertain();
      return Object.freeze({ ...value }) as unknown as SurveyVersionCreateReceipt;
    } catch (failure) {
      if (failure instanceof SurveyVersionCreateError) throw failure;
      return uncertain();
    }
  }
}
