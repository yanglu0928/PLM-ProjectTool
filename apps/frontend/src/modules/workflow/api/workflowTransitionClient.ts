import { SessionClient, SessionClientError } from "@/modules/auth/api/sessionClient";
import { parseWorkflow, type WorkflowView } from "./workflowReadClient";

export interface WorkflowTransitionView {
  readonly stage_transition_id: string;
  readonly workflow_id: string;
  readonly project_id: string;
  readonly definition_version: 1;
  readonly from_stage: SupportedTransitionFromStage;
  readonly to_stage: SupportedTransitionToStage;
  readonly before_workflow_version: number;
  readonly transitioned_workflow_version: number;
  readonly current_workflow_version: number;
  readonly reason: string;
  readonly occurred_at: string;
  readonly etag: string;
}

export type SupportedTransitionFromStage = "HANDOVER" | "SURVEY";
export type SupportedTransitionToStage = "SURVEY" | "REQUIREMENT";
const transitionTargets = Object.freeze({
  HANDOVER: "SURVEY",
  SURVEY: "REQUIREMENT",
} as const satisfies Record<SupportedTransitionFromStage, SupportedTransitionToStage>);

export function transitionTargetForStage(stage: string | null): SupportedTransitionToStage | null {
  return stage !== null && Object.hasOwn(transitionTargets, stage)
    ? transitionTargets[stage as SupportedTransitionFromStage] : null;
}

export interface WorkflowTransitionFirstReceipt {
  readonly first_transition: WorkflowTransitionView;
  /** A replay is immutable history, never proof of the current Workflow state. */
  readonly is_current_state_proof: false;
}

export interface WorkflowTransitionInput {
  readonly before: WorkflowView;
  readonly reason: string;
  readonly idempotency_key: string;
}

const messages = {
  WORKFLOW_TRANSITION_INVALID_INPUT: "请重新读取流程和版本后再推进。",
  AUTH_RELOGIN_REQUIRED: "推进阶段前请重新登录。",
  AUTH_CLIENT_BUSY: "正在处理会话操作，请稍候。",
  AUTH_SESSION_EXPIRED: "会话已失效，请重新登录。",
  AUTH_CSRF_INVALID: "登录状态已变化，请重新登录。",
  LICENSE_OPERATION_DENIED: "当前许可不允许推进项目阶段。",
  RESOURCE_NOT_FOUND: "项目流程不存在或无权推进。",
  PROJECT_ARCHIVED: "项目已归档，请重新读取。",
  CONFLICT_VERSION: "流程版本已变化，请重新读取。",
  CONFLICT_STATE: "流程状态已变化，请重新读取。",
  CONFLICT_IDEMPOTENCY: "原推进操作与请求不一致，已停止重试。",
  WORKFLOW_GATE_NOT_SATISFIED: "服务端当前 Gate 复验未通过，请重新读取并处理检查项。",
  WORKFLOW_TRANSITION_INVALID: "当前阶段不能按此目标推进，请重新读取。",
  WORKFLOW_TRANSITION_UNCERTAIN: "推进结果无法确认；保留原请求、操作号和版本，先重新读取流程与审计。",
} as const;
export type WorkflowTransitionErrorCode = keyof typeof messages;

export class WorkflowTransitionError extends Error {
  readonly uncertain: boolean;
  constructor(readonly code: WorkflowTransitionErrorCode) {
    super(messages[code]);
    this.name = "WorkflowTransitionError";
    this.uncertain = code === "WORKFLOW_TRANSITION_UNCERTAIN";
  }
}

const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const strongEtag = /^"v([1-9][0-9]{0,18})"$/;
const responseFields = new Set([
  "stage_transition_id", "workflow_id", "project_id", "definition_version",
  "from_stage", "to_stage", "before_workflow_version",
  "transitioned_workflow_version", "current_workflow_version", "reason",
  "occurred_at", "etag",
]);

function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
function identifier(value: unknown): value is string {
  return typeof value === "string" && uuid.test(value)
    && value !== "00000000-0000-0000-0000-000000000000";
}
function version(value: unknown): value is number {
  return typeof value === "number" && Number.isSafeInteger(value)
    && value >= 1 && value < Number.MAX_SAFE_INTEGER;
}
function versionFromEtag(value: unknown): number | null {
  if (typeof value !== "string") return null;
  const match = strongEtag.exec(value);
  if (match === null) return null;
  const parsed = Number(match[1]);
  return Number.isSafeInteger(parsed) && parsed < Number.MAX_SAFE_INTEGER ? parsed : null;
}
function text(value: unknown): string | null {
  if (typeof value !== "string") return null;
  const normalized = value.trim();
  return normalized.length > 0 && normalized.length <= 2000
    && !normalized.includes("\u0000") ? normalized : null;
}
function utcInstant(value: unknown): value is string {
  if (typeof value !== "string"
    || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$/.test(value)) return false;
  const parsed = Date.parse(value);
  const calendar = Date.parse(value.slice(0, 19) + "Z");
  return Number.isFinite(parsed) && Number.isFinite(calendar)
    && new Date(calendar).toISOString().slice(0, 19) === value.slice(0, 19);
}

function parseTransition(value: unknown): WorkflowTransitionView {
  const normalizedReason = record(value) ? text(value.reason) : null;
  if (!record(value) || Object.keys(value).length !== responseFields.size
    || !Object.keys(value).every((key) => responseFields.has(key))
    || !identifier(value.stage_transition_id) || !identifier(value.workflow_id)
    || !identifier(value.project_id) || value.definition_version !== 1
    || typeof value.from_stage !== "string"
    || transitionTargetForStage(value.from_stage) !== value.to_stage
    || !version(value.before_workflow_version)
    || !version(value.transitioned_workflow_version)
    || !version(value.current_workflow_version)
    || value.transitioned_workflow_version !== value.before_workflow_version + 1
    || value.current_workflow_version < value.transitioned_workflow_version
    || normalizedReason === null || normalizedReason !== value.reason
    || !utcInstant(value.occurred_at)
    || versionFromEtag(value.etag) !== value.current_workflow_version) {
    throw new WorkflowTransitionError("WORKFLOW_TRANSITION_UNCERTAIN");
  }
  return Object.freeze({
    stage_transition_id: value.stage_transition_id,
    workflow_id: value.workflow_id, project_id: value.project_id,
    definition_version: 1,
    from_stage: value.from_stage as SupportedTransitionFromStage,
    to_stage: value.to_stage as SupportedTransitionToStage,
    before_workflow_version: value.before_workflow_version,
    transitioned_workflow_version: value.transitioned_workflow_version,
    current_workflow_version: value.current_workflow_version,
    reason: normalizedReason, occurred_at: value.occurred_at,
    etag: value.etag as string,
  });
}

export class WorkflowTransitionClient {
  constructor(private readonly session: SessionClient) {
    if (!(session instanceof SessionClient)) {
      throw new WorkflowTransitionError("WORKFLOW_TRANSITION_INVALID_INPUT");
    }
  }

  async transition(projectId: string,
    input: WorkflowTransitionInput): Promise<WorkflowTransitionFirstReceipt> {
    if (!identifier(projectId) || !record(input)
      || typeof input.idempotency_key !== "string"
      || !/^[\x20-\x7e]{16,128}$/.test(input.idempotency_key)) {
      throw new WorkflowTransitionError("WORKFLOW_TRANSITION_INVALID_INPUT");
    }
    let before: WorkflowView;
    try { before = parseWorkflow(input.before); }
    catch { throw new WorkflowTransitionError("WORKFLOW_TRANSITION_INVALID_INPUT"); }
    const beforeVersion = versionFromEtag(before.etag);
    const targetStage = transitionTargetForStage(before.current_stage);
    const sourceStage = before.stages.find((stage) => stage.stage_key === before.current_stage);
    const reason = text(input.reason);
    if (before.state !== "ACTIVE" || targetStage === null || sourceStage === undefined
      || sourceStage.state !== "ACTIVE"
      || sourceStage.checklist_items.some((item) => item.state !== "PASS")
      || beforeVersion === null || reason === null) {
      throw new WorkflowTransitionError("WORKFLOW_TRANSITION_INVALID_INPUT");
    }
    const body = JSON.stringify({ target_stage_key: targetStage, reason,
      gate_snapshot_refs: [] });
    let response: Response;
    try {
      response = await this.session.postProjectWorkflowTransition(
        projectId, body, before.etag, input.idempotency_key,
      );
    } catch (failure) {
      if (failure instanceof SessionClientError && failure.code === "AUTH_RELOGIN_REQUIRED") {
        throw new WorkflowTransitionError("AUTH_RELOGIN_REQUIRED");
      }
      if (failure instanceof SessionClientError && failure.code === "AUTH_CLIENT_BUSY") {
        throw new WorkflowTransitionError("AUTH_CLIENT_BUSY");
      }
      throw new WorkflowTransitionError("WORKFLOW_TRANSITION_UNCERTAIN");
    }
    try {
      if (response.headers.get("content-type")?.split(";")[0].trim().toLowerCase()
          !== "application/json") {
        throw new WorkflowTransitionError("WORKFLOW_TRANSITION_UNCERTAIN");
      }
      const payload: unknown = await response.json();
      if (!record(payload) || !identifier(payload.trace_id)) {
        throw new WorkflowTransitionError("WORKFLOW_TRANSITION_UNCERTAIN");
      }
      if (response.status !== 200) {
        const code = record(payload.error) ? payload.error.code : null;
        const known: Record<string, number> = {
          AUTH_SESSION_EXPIRED: 401, AUTH_CSRF_INVALID: 403,
          LICENSE_OPERATION_DENIED: 403, RESOURCE_NOT_FOUND: 404,
          PROJECT_ARCHIVED: 409, CONFLICT_VERSION: 409, CONFLICT_STATE: 409,
          CONFLICT_IDEMPOTENCY: 409, WORKFLOW_GATE_NOT_SATISFIED: 409,
          WORKFLOW_TRANSITION_INVALID: 409,
          REQUEST_MALFORMED: 400, VALIDATION_FAILED: 422,
          CONFLICT_VERSION_REQUIRED: 428,
        };
        if (typeof code === "string" && Object.hasOwn(known, code)
          && known[code] === response.status) {
          const projected = ["REQUEST_MALFORMED", "VALIDATION_FAILED",
            "CONFLICT_VERSION_REQUIRED"].includes(code)
            ? "WORKFLOW_TRANSITION_INVALID_INPUT" : code as WorkflowTransitionErrorCode;
          throw new WorkflowTransitionError(projected);
        }
        throw new WorkflowTransitionError("WORKFLOW_TRANSITION_UNCERTAIN");
      }
      const first = parseTransition(payload.data);
      if (first.project_id !== projectId || first.workflow_id !== before.workflow_id
        || first.from_stage !== before.current_stage || first.to_stage !== targetStage
        || first.before_workflow_version !== beforeVersion
        || first.transitioned_workflow_version !== beforeVersion + 1
        || first.current_workflow_version !== beforeVersion + 1
        || first.reason !== reason || response.headers.get("etag") !== first.etag) {
        throw new WorkflowTransitionError("WORKFLOW_TRANSITION_UNCERTAIN");
      }
      return Object.freeze({ first_transition: first,
        is_current_state_proof: false as const });
    } catch (failure) {
      if (failure instanceof WorkflowTransitionError) throw failure;
      throw new WorkflowTransitionError("WORKFLOW_TRANSITION_UNCERTAIN");
    }
  }
}
