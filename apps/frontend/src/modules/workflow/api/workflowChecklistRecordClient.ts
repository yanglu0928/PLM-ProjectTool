import { SessionClient, SessionClientError } from "@/modules/auth/api/sessionClient";
import { parseWorkflow, type WorkflowView } from "./workflowReadClient";

export type HandoverChecklistItemKey = "HANDOVER_BASELINE" | "HANDOVER_ISSUES";
export type SurveyChecklistItemKey = "SURVEY_ACTUAL_SOURCES" | "SURVEY_CONCLUSION";
export type SupportedChecklistItemKey = HandoverChecklistItemKey | SurveyChecklistItemKey;
export type SupportedChecklistStage = "HANDOVER" | "SURVEY";
export type SupportedChecklistResult = "PASS" | "FAIL";

const itemStages = Object.freeze({
  HANDOVER_BASELINE: "HANDOVER",
  HANDOVER_ISSUES: "HANDOVER",
  SURVEY_ACTUAL_SOURCES: "SURVEY",
  SURVEY_CONCLUSION: "SURVEY",
} as const satisfies Record<SupportedChecklistItemKey, SupportedChecklistStage>);

export function checklistStageForItem(itemKey: string): SupportedChecklistStage | null {
  return Object.hasOwn(itemStages, itemKey)
    ? itemStages[itemKey as SupportedChecklistItemKey] : null;
}

export interface WorkflowChecklistRecordView {
  readonly record_id: string;
  readonly workflow_id: string;
  readonly project_id: string;
  readonly definition_version: 1;
  readonly stage_key: SupportedChecklistStage;
  readonly item_key: SupportedChecklistItemKey;
  readonly result: SupportedChecklistResult;
  readonly item_version: number;
  readonly recorded_workflow_version: number;
  readonly current_workflow_version: number;
  readonly supersedes_record_id: string | null;
  readonly evidence_refs: readonly string[];
  readonly review_round_refs: readonly string[];
  readonly exception_refs: readonly string[];
  readonly reason: string | null;
  readonly impact: string | null;
  readonly occurred_at: string;
  readonly etag: string;
}

export interface WorkflowChecklistFirstReceipt {
  readonly first_record: WorkflowChecklistRecordView;
  /** A replay is the immutable first result, never proof of the current Checklist state. */
  readonly is_current_state_proof: false;
}

export interface WorkflowChecklistRecordInput {
  readonly before: WorkflowView;
  readonly item_key: SupportedChecklistItemKey;
  readonly result: SupportedChecklistResult;
  readonly evidence_refs: readonly string[];
  readonly reason?: string | null;
  readonly impact?: string | null;
  readonly idempotency_key: string;
}

const messages = {
  WORKFLOW_CHECKLIST_INVALID_INPUT: "请重新读取流程、资格依据与版本后再记录。",
  AUTH_RELOGIN_REQUIRED: "记录检查项前请重新登录。",
  AUTH_CLIENT_BUSY: "正在处理会话操作，请稍候。",
  AUTH_SESSION_EXPIRED: "会话已失效，请重新登录。",
  AUTH_CSRF_INVALID: "登录状态已变化，请重新登录。",
  LICENSE_OPERATION_DENIED: "当前许可不允许记录流程检查项。",
  RESOURCE_NOT_FOUND: "项目流程不存在或无权记录。",
  PROJECT_ARCHIVED: "项目已归档，请重新读取。",
  CONFLICT_VERSION: "流程版本已变化，请重新读取。",
  CONFLICT_STATE: "流程状态已变化，请重新读取。",
  CONFLICT_IDEMPOTENCY: "原操作记录与请求不一致，已停止重试。",
  WORKFLOW_GATE_NOT_SATISFIED: "服务端复验未通过；请重新读取资格依据。",
  WORKFLOW_CHECKLIST_UNCERTAIN: "记录结果无法确认；保留原请求、操作记录和版本，先重新读取流程与审计。",
} as const;
export type WorkflowChecklistRecordErrorCode = keyof typeof messages;

export class WorkflowChecklistRecordError extends Error {
  readonly uncertain: boolean;
  constructor(readonly code: WorkflowChecklistRecordErrorCode) {
    super(messages[code]);
    this.name = "WorkflowChecklistRecordError";
    this.uncertain = code === "WORKFLOW_CHECKLIST_UNCERTAIN";
  }
}

const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const strongEtag = /^"v([1-9][0-9]{0,18})"$/;
const responseFields = new Set([
  "record_id", "workflow_id", "project_id", "definition_version", "stage_key", "item_key",
  "result", "item_version", "recorded_workflow_version", "current_workflow_version",
  "supersedes_record_id", "evidence_refs", "review_round_refs", "exception_refs", "reason",
  "impact", "occurred_at", "etag",
]);

function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
function identifier(value: unknown): value is string {
  return typeof value === "string" && uuid.test(value)
    && value !== "00000000-0000-0000-0000-000000000000";
}
function exactFields(value: Record<string, unknown>): boolean {
  return Object.keys(value).length === responseFields.size
    && Object.keys(value).every((key) => responseFields.has(key));
}
function versionFromEtag(value: unknown): number | null {
  if (typeof value !== "string") return null;
  const match = strongEtag.exec(value);
  if (match === null) return null;
  const version = Number(match[1]);
  return Number.isSafeInteger(version) && version < Number.MAX_SAFE_INTEGER ? version : null;
}
function positiveVersion(value: unknown): value is number {
  return typeof value === "number" && Number.isSafeInteger(value) && value >= 1
    && value < Number.MAX_SAFE_INTEGER;
}
function identifiers(value: unknown, required: boolean): readonly string[] | null {
  if (!Array.isArray(value) || required && value.length === 0 || value.length > 500
    || value.some((item) => !identifier(item))) return null;
  const result = value as string[];
  if (new Set(result).size !== result.length) return null;
  return Object.freeze([...result]);
}
function sameSet(left: readonly string[], right: readonly string[]): boolean {
  return left.length === right.length && left.every((value) => right.includes(value));
}
function optionalText(value: unknown): string | null | undefined {
  if (value === null || value === undefined) return null;
  if (typeof value !== "string") return undefined;
  const normalized = value.trim();
  if (normalized.length === 0 || normalized.length > 2000 || normalized.includes("\u0000")) return undefined;
  return normalized;
}
function utcInstant(value: unknown): value is string {
  if (typeof value !== "string"
    || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$/.test(value)) return false;
  const parsed = Date.parse(value);
  const calendar = Date.parse(value.slice(0, 19) + "Z");
  return Number.isFinite(parsed) && Number.isFinite(calendar)
    && new Date(calendar).toISOString().slice(0, 19) === value.slice(0, 19);
}

function parseResponse(value: unknown): WorkflowChecklistRecordView {
  if (!record(value) || !exactFields(value) || !identifier(value.record_id)
    || !identifier(value.workflow_id) || !identifier(value.project_id)
    || value.definition_version !== 1
    || typeof value.item_key !== "string"
    || checklistStageForItem(value.item_key) !== value.stage_key
    || !["PASS", "FAIL"].includes(value.result as string)
    || !positiveVersion(value.item_version) || !positiveVersion(value.recorded_workflow_version)
    || !positiveVersion(value.current_workflow_version)
    || value.current_workflow_version < value.recorded_workflow_version
    || value.supersedes_record_id !== null && !identifier(value.supersedes_record_id)
    || value.item_version === 1 !== (value.supersedes_record_id === null)
    || value.reason !== null && (typeof value.reason !== "string" || optionalText(value.reason) !== value.reason)
    || value.impact !== null && (typeof value.impact !== "string" || optionalText(value.impact) !== value.impact)
    || !utcInstant(value.occurred_at) || versionFromEtag(value.etag) !== value.current_workflow_version) {
    throw new WorkflowChecklistRecordError("WORKFLOW_CHECKLIST_UNCERTAIN");
  }
  const result = value.result as SupportedChecklistResult;
  const evidence = identifiers(value.evidence_refs, result === "PASS");
  const reviews = identifiers(value.review_round_refs, result === "PASS");
  const exceptions = identifiers(value.exception_refs, false);
  if (evidence === null || reviews === null || exceptions === null || exceptions.length !== 0
    || result === "FAIL" && (evidence.length !== 0 || reviews.length !== 0)) {
    throw new WorkflowChecklistRecordError("WORKFLOW_CHECKLIST_UNCERTAIN");
  }
  return Object.freeze({
    record_id: value.record_id, workflow_id: value.workflow_id, project_id: value.project_id,
    definition_version: 1, stage_key: value.stage_key as SupportedChecklistStage,
    item_key: value.item_key as SupportedChecklistItemKey, result,
    item_version: value.item_version, recorded_workflow_version: value.recorded_workflow_version,
    current_workflow_version: value.current_workflow_version,
    supersedes_record_id: value.supersedes_record_id as string | null,
    evidence_refs: evidence, review_round_refs: reviews, exception_refs: exceptions,
    reason: value.reason as string | null, impact: value.impact as string | null,
    occurred_at: value.occurred_at, etag: value.etag as string,
  });
}

export class WorkflowChecklistRecordClient {
  constructor(private readonly session: SessionClient) {
    if (!(session instanceof SessionClient)) {
      throw new WorkflowChecklistRecordError("WORKFLOW_CHECKLIST_INVALID_INPUT");
    }
  }

  async record(projectId: string, input: WorkflowChecklistRecordInput): Promise<WorkflowChecklistFirstReceipt> {
    if (!identifier(projectId) || !record(input)
      || checklistStageForItem(input.item_key) === null
      || !["PASS", "FAIL"].includes(input.result)
      || typeof input.idempotency_key !== "string"
      || !/^[\x20-\x7e]{16,128}$/.test(input.idempotency_key)) {
      throw new WorkflowChecklistRecordError("WORKFLOW_CHECKLIST_INVALID_INPUT");
    }
    let before: WorkflowView;
    try { before = parseWorkflow(input.before); }
    catch { throw new WorkflowChecklistRecordError("WORKFLOW_CHECKLIST_INVALID_INPUT"); }
    const workflowVersion = versionFromEtag(before.etag);
    const expectedStage = checklistStageForItem(input.item_key);
    const currentStage = before.stages.find((stage) => stage.stage_key === expectedStage);
    const evidence = identifiers(input.evidence_refs, input.result === "PASS");
    const reason = optionalText(input.reason);
    const impact = optionalText(input.impact);
    if (before.state !== "ACTIVE" || expectedStage === null
      || before.current_stage !== expectedStage || currentStage === undefined
      || !["ACTIVE", "BLOCKED"].includes(currentStage.state)
      || currentStage.checklist_items.every((item) => item.item_key !== input.item_key)
      || workflowVersion === null || evidence === null
      || input.result === "FAIL" && evidence.length !== 0
      || reason === undefined || impact === undefined) {
      throw new WorkflowChecklistRecordError("WORKFLOW_CHECKLIST_INVALID_INPUT");
    }
    const body = JSON.stringify({ result: input.result, reason, impact,
      evidence_refs: evidence, exception_refs: [] });
    let response: Response;
    try {
      response = await this.session.postProjectWorkflowChecklistRecord(
        projectId, input.item_key, body, before.etag, input.idempotency_key,
      );
    } catch (failure) {
      if (failure instanceof SessionClientError && failure.code === "AUTH_RELOGIN_REQUIRED") {
        throw new WorkflowChecklistRecordError("AUTH_RELOGIN_REQUIRED");
      }
      if (failure instanceof SessionClientError && failure.code === "AUTH_CLIENT_BUSY") {
        throw new WorkflowChecklistRecordError("AUTH_CLIENT_BUSY");
      }
      throw new WorkflowChecklistRecordError("WORKFLOW_CHECKLIST_UNCERTAIN");
    }
    try {
      if (response.headers.get("content-type")?.split(";")[0].trim().toLowerCase() !== "application/json") {
        throw new WorkflowChecklistRecordError("WORKFLOW_CHECKLIST_UNCERTAIN");
      }
      const payload: unknown = await response.json();
      if (!record(payload) || !identifier(payload.trace_id)) {
        throw new WorkflowChecklistRecordError("WORKFLOW_CHECKLIST_UNCERTAIN");
      }
      if (response.status !== 200) {
        const code = record(payload.error) ? payload.error.code : null;
        const known: Record<string, number> = {
          AUTH_SESSION_EXPIRED: 401, AUTH_CSRF_INVALID: 403,
          LICENSE_OPERATION_DENIED: 403, RESOURCE_NOT_FOUND: 404,
          PROJECT_ARCHIVED: 409, CONFLICT_VERSION: 409, CONFLICT_STATE: 409,
          CONFLICT_IDEMPOTENCY: 409, WORKFLOW_GATE_NOT_SATISFIED: 409,
          REQUEST_MALFORMED: 400, VALIDATION_FAILED: 422, CONFLICT_VERSION_REQUIRED: 428,
        };
        if (typeof code === "string" && Object.hasOwn(known, code) && known[code] === response.status) {
          const projected = ["REQUEST_MALFORMED", "VALIDATION_FAILED", "CONFLICT_VERSION_REQUIRED"].includes(code)
            ? "WORKFLOW_CHECKLIST_INVALID_INPUT" : code as WorkflowChecklistRecordErrorCode;
          throw new WorkflowChecklistRecordError(projected);
        }
        throw new WorkflowChecklistRecordError("WORKFLOW_CHECKLIST_UNCERTAIN");
      }
      const first = parseResponse(payload.data);
      if (first.project_id !== projectId || first.workflow_id !== before.workflow_id
        || first.stage_key !== expectedStage || first.item_key !== input.item_key
        || first.result !== input.result
        || first.recorded_workflow_version !== workflowVersion + 1
        || response.headers.get("etag") !== first.etag
        || !sameSet(first.evidence_refs, evidence)
        || first.reason !== reason || first.impact !== impact) {
        throw new WorkflowChecklistRecordError("WORKFLOW_CHECKLIST_UNCERTAIN");
      }
      return Object.freeze({ first_record: first, is_current_state_proof: false as const });
    } catch (failure) {
      if (failure instanceof WorkflowChecklistRecordError) throw failure;
      throw new WorkflowChecklistRecordError("WORKFLOW_CHECKLIST_UNCERTAIN");
    }
  }
}
