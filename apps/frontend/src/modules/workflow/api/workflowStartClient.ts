import { SessionClient, SessionClientError } from "@/modules/auth/api/sessionClient";
import { parseWorkflow, WorkflowReadError, type WorkflowView } from "./workflowReadClient";

export interface WorkflowStartFirstReceipt {
  readonly first_result: WorkflowView;
  readonly is_current_state_proof: false;
}

const messages = {
  WORKFLOW_START_INVALID_INPUT: "请重新读取流程初态与版本后再启动。",
  AUTH_RELOGIN_REQUIRED: "启动流程前请重新登录。",
  AUTH_CLIENT_BUSY: "正在处理会话操作，请稍候。",
  AUTH_SESSION_EXPIRED: "会话已失效，请重新登录。",
  AUTH_CSRF_INVALID: "登录状态已变化，请重新登录。",
  LICENSE_OPERATION_DENIED: "当前许可不允许启动流程。",
  RESOURCE_NOT_FOUND: "项目流程不存在或无权启动。",
  PROJECT_ARCHIVED: "项目已归档，请重新读取。",
  CONFLICT_VERSION: "流程版本已变化，请重新读取。",
  CONFLICT_STATE: "流程状态已变化，请重新读取。",
  CONFLICT_IDEMPOTENCY: "原操作记录与请求不一致，已停止重试。",
  WORKFLOW_START_UNCERTAIN: "启动结果无法确认；保留原操作记录和版本，先重新读取流程与审计。",
} as const;
export type WorkflowStartErrorCode = keyof typeof messages;

export class WorkflowStartError extends Error {
  readonly uncertain: boolean;
  constructor(readonly code: WorkflowStartErrorCode) {
    super(messages[code]); this.name = "WorkflowStartError";
    this.uncertain = code === "WORKFLOW_START_UNCERTAIN";
  }
}

const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
function identifier(value: unknown): value is string {
  return typeof value === "string" && uuid.test(value)
    && value !== "00000000-0000-0000-0000-000000000000";
}

/** A 200 replay is the initial v1 result, not evidence of the current stage. */
export class WorkflowStartClient {
  constructor(private readonly session: SessionClient) {
    if (!(session instanceof SessionClient)) {
      throw new WorkflowStartError("WORKFLOW_START_INVALID_INPUT");
    }
  }

  async start(projectId: string, before: WorkflowView,
    key: string): Promise<WorkflowStartFirstReceipt> {
    if (!identifier(projectId) || typeof key !== "string" || !/^[\x20-\x7e]{16,128}$/.test(key)) {
      throw new WorkflowStartError("WORKFLOW_START_INVALID_INPUT");
    }
    let original: WorkflowView;
    try { original = parseWorkflow(before); }
    catch { throw new WorkflowStartError("WORKFLOW_START_INVALID_INPUT"); }
    if (original.state !== "NOT_STARTED" || original.current_stage !== null || original.etag !== '"v0"') {
      throw new WorkflowStartError("WORKFLOW_START_INVALID_INPUT");
    }
    let response: Response;
    try {
      response = await this.session.postProjectWorkflowStart(projectId, original.etag, key);
    } catch (failure) {
      if (failure instanceof SessionClientError && failure.code === "AUTH_RELOGIN_REQUIRED") {
        throw new WorkflowStartError("AUTH_RELOGIN_REQUIRED");
      }
      if (failure instanceof SessionClientError && failure.code === "AUTH_CLIENT_BUSY") {
        throw new WorkflowStartError("AUTH_CLIENT_BUSY");
      }
      throw new WorkflowStartError("WORKFLOW_START_UNCERTAIN");
    }
    try {
      if (response.headers.get("content-type")?.split(";")[0].trim().toLowerCase() !== "application/json") {
        throw new WorkflowStartError("WORKFLOW_START_UNCERTAIN");
      }
      const payload: unknown = await response.json();
      if (!record(payload) || !identifier(payload.trace_id)) {
        throw new WorkflowStartError("WORKFLOW_START_UNCERTAIN");
      }
      if (response.status !== 200) {
        const code = record(payload.error) ? payload.error.code : null;
        const known: Record<string, number> = {
          AUTH_SESSION_EXPIRED: 401, AUTH_CSRF_INVALID: 403,
          LICENSE_OPERATION_DENIED: 403, RESOURCE_NOT_FOUND: 404,
          PROJECT_ARCHIVED: 409, CONFLICT_VERSION: 409, CONFLICT_STATE: 409,
          CONFLICT_IDEMPOTENCY: 409, REQUEST_MALFORMED: 400,
          VALIDATION_FAILED: 422, CONFLICT_VERSION_REQUIRED: 428,
        };
        if (typeof code === "string" && Object.hasOwn(known, code) && known[code] === response.status) {
          throw new WorkflowStartError(["REQUEST_MALFORMED", "VALIDATION_FAILED",
            "CONFLICT_VERSION_REQUIRED"].includes(code)
            ? "WORKFLOW_START_INVALID_INPUT" : code as WorkflowStartErrorCode);
        }
        throw new WorkflowStartError("WORKFLOW_START_UNCERTAIN");
      }
      const first = parseWorkflow(payload.data);
      if (first.workflow_id !== original.workflow_id || first.version !== 1
        || first.state !== "ACTIVE" || first.current_stage !== "HANDOVER"
        || first.etag !== '"v1"' || response.headers.get("etag") !== first.etag
        || first.stages.some((stage, index) => stage.state !== (index === 0 ? "ACTIVE" : "NOT_STARTED")
          || stage.checklist_items.some((item) => item.state !== "PENDING"))) {
        throw new WorkflowStartError("WORKFLOW_START_UNCERTAIN");
      }
      return Object.freeze({ first_result: first, is_current_state_proof: false as const });
    } catch (failure) {
      if (failure instanceof WorkflowStartError) throw failure;
      if (failure instanceof WorkflowReadError) {
        throw new WorkflowStartError("WORKFLOW_START_UNCERTAIN");
      }
      throw new WorkflowStartError("WORKFLOW_START_UNCERTAIN");
    }
  }
}
