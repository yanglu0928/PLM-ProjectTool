import { checklistStageForItem, type HandoverChecklistItemKey,
  type RequirementChecklistItemKey, type SupportedChecklistItemKey,
  type SurveyChecklistItemKey,
} from "./workflowChecklistRecordClient";

interface WorkflowChecklistQualificationBase {
  readonly workflow_id: string;
  readonly project_id: string;
  readonly definition_version: 1;
  readonly current_item_state: "PENDING" | "PASS" | "FAIL" | "WAIVED";
  readonly workflow_etag: string;
  readonly evidence_refs: readonly string[];
}

export interface HandoverChecklistQualificationView extends WorkflowChecklistQualificationBase {
  readonly stage_key: "HANDOVER";
  readonly item_key: HandoverChecklistItemKey;
  readonly handover_analysis_version_id: string;
  readonly review_round_ref: string;
}

export interface SurveyChecklistQualificationView extends WorkflowChecklistQualificationBase {
  readonly stage_key: "SURVEY";
  readonly item_key: SurveyChecklistItemKey;
  readonly survey_conclusion_id: string;
  readonly review_round_ref: string;
}

export interface RequirementChecklistQualificationView extends WorkflowChecklistQualificationBase {
  readonly stage_key: "REQUIREMENT";
  readonly item_key: RequirementChecklistItemKey;
  readonly requirement_version_refs: readonly string[];
  readonly review_round_refs: readonly string[];
}

export type WorkflowChecklistQualificationView =
  HandoverChecklistQualificationView | SurveyChecklistQualificationView
  | RequirementChecklistQualificationView;

const messages = {
  WORKFLOW_QUALIFICATION_INVALID_INPUT: "请重新读取当前项目流程。",
  AUTH_SESSION_EXPIRED: "会话已失效，请重新登录。",
  AUTH_CSRF_INVALID: "当前站点来源不受信任，请重新登录。",
  LICENSE_OPERATION_DENIED: "当前许可不允许读取流程资格。",
  RESOURCE_NOT_FOUND: "项目流程不存在或无权记录。",
  PROJECT_ARCHIVED: "项目已归档，请重新读取。",
  CONFLICT_STATE: "流程状态已变化，请重新读取。",
  CONFLICT_VERSION: "流程版本已变化，请重新读取。",
  WORKFLOW_GATE_NOT_SATISFIED: "当前事实尚不满足通过条件，请处理待办后重试。",
  WORKFLOW_QUALIFICATION_UNAVAILABLE: "暂时无法确认权威资格，请稍后重试。",
} as const;
export type WorkflowChecklistQualificationErrorCode = keyof typeof messages;

export class WorkflowChecklistQualificationError extends Error {
  constructor(readonly code: WorkflowChecklistQualificationErrorCode) {
    super(messages[code]);
    this.name = "WorkflowChecklistQualificationError";
  }
}

const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const etag = /^"v[1-9][0-9]{0,18}"$/;
const commonFields = [
  "workflow_id", "project_id", "definition_version", "stage_key", "item_key",
  "current_item_state", "workflow_etag", "evidence_refs",
] as const;
const handoverFields = new Set([...commonFields, "handover_analysis_version_id", "review_round_ref"]);
const surveyFields = new Set([...commonFields, "survey_conclusion_id", "review_round_ref"]);
const requirementFields = new Set([...commonFields, "requirement_version_refs", "review_round_refs"]);

function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
function identifier(value: unknown): value is string {
  return typeof value === "string" && uuid.test(value)
    && value !== "00000000-0000-0000-0000-000000000000";
}
function identifiers(value: unknown): readonly string[] | null {
  if (!Array.isArray(value) || value.length === 0 || value.length > 500
    || value.some((item) => !identifier(item))
    || new Set(value).size !== value.length) return null;
  return Object.freeze([...(value as string[])]);
}
function parse(value: unknown): WorkflowChecklistQualificationView {
  if (!record(value) || typeof value.item_key !== "string"
    || checklistStageForItem(value.item_key) !== value.stage_key) {
    throw new WorkflowChecklistQualificationError("WORKFLOW_QUALIFICATION_UNAVAILABLE");
  }
  const stage = value.stage_key as "HANDOVER" | "SURVEY" | "REQUIREMENT";
  const fields = stage === "HANDOVER" ? handoverFields
    : stage === "SURVEY" ? surveyFields : requirementFields;
  const evidence = identifiers(value.evidence_refs);
  if (Object.keys(value).length !== fields.size
    || Object.keys(value).some((key) => !fields.has(key))
    || !identifier(value.workflow_id) || !identifier(value.project_id)
    || value.definition_version !== 1
    || !["PENDING", "PASS", "FAIL", "WAIVED"].includes(value.current_item_state as string)
    || typeof value.workflow_etag !== "string" || !etag.test(value.workflow_etag)
    || !Number.isSafeInteger(Number(value.workflow_etag.slice(2, -1)))
    || evidence === null) {
    throw new WorkflowChecklistQualificationError("WORKFLOW_QUALIFICATION_UNAVAILABLE");
  }
  const common = {
    workflow_id: value.workflow_id,
    project_id: value.project_id,
    definition_version: 1,
    current_item_state: value.current_item_state as WorkflowChecklistQualificationView["current_item_state"],
    workflow_etag: value.workflow_etag,
    evidence_refs: evidence,
  } as const;
  if (stage === "HANDOVER") {
    if (!identifier(value.handover_analysis_version_id)
      || !identifier(value.review_round_ref)) {
      throw new WorkflowChecklistQualificationError("WORKFLOW_QUALIFICATION_UNAVAILABLE");
    }
    return Object.freeze({ ...common, stage_key: "HANDOVER" as const,
      item_key: value.item_key as HandoverChecklistItemKey,
      handover_analysis_version_id: value.handover_analysis_version_id,
      review_round_ref: value.review_round_ref });
  }
  if (stage === "SURVEY") {
    if (!identifier(value.survey_conclusion_id)
      || !identifier(value.review_round_ref)) {
      throw new WorkflowChecklistQualificationError("WORKFLOW_QUALIFICATION_UNAVAILABLE");
    }
    return Object.freeze({ ...common, stage_key: "SURVEY" as const,
      item_key: value.item_key as SurveyChecklistItemKey,
      survey_conclusion_id: value.survey_conclusion_id,
      review_round_ref: value.review_round_ref });
  }
  const versions = identifiers(value.requirement_version_refs);
  const rounds = identifiers(value.review_round_refs);
  if (stage !== "REQUIREMENT" || versions === null || rounds === null
    || versions.length !== rounds.length) {
    throw new WorkflowChecklistQualificationError("WORKFLOW_QUALIFICATION_UNAVAILABLE");
  }
  return Object.freeze({ ...common, stage_key: "REQUIREMENT" as const,
    item_key: value.item_key as RequirementChecklistItemKey,
    requirement_version_refs: versions, review_round_refs: rounds });
}

export class WorkflowChecklistQualificationClient {
  constructor(private readonly fetcher: typeof fetch = fetch,
    private readonly timeoutMs = 10_000) {
    if (!Number.isInteger(timeoutMs) || timeoutMs < 1 || timeoutMs > 30_000) {
      throw new WorkflowChecklistQualificationError("WORKFLOW_QUALIFICATION_UNAVAILABLE");
    }
  }

  async get(projectId: string, itemKey: SupportedChecklistItemKey): Promise<WorkflowChecklistQualificationView> {
    if (!identifier(projectId) || checklistStageForItem(itemKey) === null) {
      throw new WorkflowChecklistQualificationError("WORKFLOW_QUALIFICATION_INVALID_INPUT");
    }
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      const fetcher = this.fetcher;
      const response = await fetcher(
        `/api/v1/projects/${projectId}/workflow/checklist-items/${itemKey}/qualification`, {
          method: "GET", credentials: "same-origin", cache: "no-store", redirect: "error",
          headers: { Accept: "application/json" }, signal: controller.signal,
        });
      if (controller.signal.aborted
        || response.headers.get("content-type")?.split(";")[0].trim().toLowerCase() !== "application/json") {
        throw new WorkflowChecklistQualificationError("WORKFLOW_QUALIFICATION_UNAVAILABLE");
      }
      const payload: unknown = await response.json();
      if (controller.signal.aborted || !record(payload) || !identifier(payload.trace_id)) {
        throw new WorkflowChecklistQualificationError("WORKFLOW_QUALIFICATION_UNAVAILABLE");
      }
      if (response.status !== 200) {
        const code = record(payload.error) ? payload.error.code : null;
        const known: Record<string, number> = {
          AUTH_SESSION_EXPIRED: 401, AUTH_CSRF_INVALID: 403,
          LICENSE_OPERATION_DENIED: 403,
          RESOURCE_NOT_FOUND: 404, PROJECT_ARCHIVED: 409, CONFLICT_STATE: 409,
          CONFLICT_VERSION: 409, WORKFLOW_GATE_NOT_SATISFIED: 409,
        };
        if (typeof code === "string" && Object.hasOwn(known, code)
          && known[code] === response.status) {
          throw new WorkflowChecklistQualificationError(
            code as WorkflowChecklistQualificationErrorCode,
          );
        }
        throw new WorkflowChecklistQualificationError("WORKFLOW_QUALIFICATION_UNAVAILABLE");
      }
      const result = parse(payload.data);
      if (result.project_id !== projectId || result.item_key !== itemKey
        || result.stage_key !== checklistStageForItem(itemKey)
        || response.headers.get("etag") !== result.workflow_etag
        || response.headers.get("cache-control")?.toLowerCase() !== "no-store") {
        throw new WorkflowChecklistQualificationError("WORKFLOW_QUALIFICATION_UNAVAILABLE");
      }
      return result;
    } catch (failure) {
      if (failure instanceof WorkflowChecklistQualificationError) throw failure;
      throw new WorkflowChecklistQualificationError("WORKFLOW_QUALIFICATION_UNAVAILABLE");
    } finally { window.clearTimeout(timer); }
  }
}
