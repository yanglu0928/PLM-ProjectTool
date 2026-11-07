/** Strict fixed-payload client for user-initiated approved-requirement DOCX requests. */
import { SessionClient, SessionClientError } from "@/modules/auth/api/sessionClient";
import type { OutputRequestState } from "./outputRequestListClient";

export interface OutputRequestCreateReceipt {
  readonly output_request_id: string;
  readonly state: OutputRequestState;
}
const messages = {
  OUTPUT_CREATE_INVALID: "当前需求版本或账户状态不允许发起输出请求。",
  OUTPUT_CREATE_UNCERTAIN: "提交结果暂时无法确认；请先查看输出请求历史，不要换操作号重复提交。",
  AUTH_RELOGIN_REQUIRED: "请重新登录后再发起输出请求。",
  AUTH_CLIENT_BUSY: "账户操作正在进行，请稍候。",
  AUTH_SESSION_EXPIRED: "会话已失效，请重新登录。",
  AUTH_CSRF_INVALID: "登录状态已变化，请重新登录。",
  LICENSE_OPERATION_DENIED: "当前许可不允许发起输出请求。",
  RESOURCE_NOT_FOUND: "当前需求版本不存在或无权访问。",
  CONFLICT_IDEMPOTENCY: "该操作号已用于不同请求，请先核对输出请求历史。",
  VALIDATION_FAILED: "当前固定版本暂不满足输出请求条件。",
  SYSTEM_UNAVAILABLE: "输出服务暂不可用，请稍后查看输出请求历史。",
} as const;
export type OutputRequestCreateErrorCode = keyof typeof messages;
export class OutputRequestCreateError extends Error {
  readonly uncertain: boolean;
  constructor(readonly code: OutputRequestCreateErrorCode) {
    super(messages[code]); this.name = "OutputRequestCreateError";
    this.uncertain = code === "OUTPUT_CREATE_UNCERTAIN";
  }
}
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const allowedStates = new Set(["REQUESTED", "QUEUED"]);
function id(value: unknown): value is string {
  return typeof value === "string" && uuid.test(value) && value !== "00000000-0000-0000-0000-000000000000";
}
function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
function exact(value: Record<string, unknown>, keys: readonly string[]): boolean {
  return Object.keys(value).length === keys.length && keys.every(key => Object.hasOwn(value, key));
}
function invalid(): never { throw new OutputRequestCreateError("OUTPUT_CREATE_INVALID"); }
function uncertain(): never { throw new OutputRequestCreateError("OUTPUT_CREATE_UNCERTAIN"); }

export class OutputRequestCreateClient {
  constructor(private readonly session: SessionClient) {
    if (!(session instanceof SessionClient)) invalid();
  }
  async create(projectId: string, approvedVersionId: string, idempotencyKey: string): Promise<OutputRequestCreateReceipt> {
    if (!id(projectId) || !id(approvedVersionId)
      || typeof idempotencyKey !== "string" || !/^[\x20-\x7e]{16,128}$/.test(idempotencyKey)) invalid();
    const view = this.session.view;
    if (!view || view.password_change_required || !this.session.canSubmit
      || !view.authorized_projects.some(item => item.project_id === projectId
        && (item.role === "PROJECT_MANAGER" || item.role === "IMPLEMENTATION_MEMBER"))) invalid();
    const body = JSON.stringify({ output_type: "DOCX",
      template_version_ref: "a1272ce0-01f0-5e6c-9706-000000000001",
      source_version_refs: [approvedVersionId], output_policy_ref: "output.policy.requirement-docx.v1",
      plugin_operation: "word.generate" });
    let response: Response;
    try { response = await this.session.postProjectOutputRequestCreate(projectId, body, idempotencyKey); }
    catch (failure) {
      if (failure instanceof SessionClientError
        && (failure.code === "AUTH_RELOGIN_REQUIRED" || failure.code === "AUTH_CLIENT_BUSY")) {
        throw new OutputRequestCreateError(failure.code);
      }
      return uncertain();
    }
    try {
      if (response.headers.get("content-type")?.split(";")[0].trim().toLowerCase() !== "application/json") uncertain();
      const payload: unknown = await response.json();
      if (!record(payload) || !id(payload.trace_id)) uncertain();
      if (response.status !== 202) {
        const code = record(payload.error) ? payload.error.code : null;
        const statuses: Readonly<Record<string, number>> = { AUTH_SESSION_EXPIRED: 401,
          AUTH_CSRF_INVALID: 403, LICENSE_OPERATION_DENIED: 403, RESOURCE_NOT_FOUND: 404,
          CONFLICT_IDEMPOTENCY: 409, VALIDATION_FAILED: 422, SYSTEM_UNAVAILABLE: 503 };
        if (typeof code === "string" && statuses[code] === response.status) {
          throw new OutputRequestCreateError(code as OutputRequestCreateErrorCode);
        }
        uncertain();
      }
      if (!exact(payload, ["data", "trace_id"]) || !record(payload.data)) uncertain();
      const value = payload.data;
      if (!exact(value, ["output_request_id", "job_id", "state"]) || !id(value.output_request_id)
        || !id(value.job_id) || typeof value.state !== "string" || !allowedStates.has(value.state)) uncertain();
      return Object.freeze({ output_request_id: value.output_request_id,
        state: value.state as OutputRequestState });
    } catch (failure) {
      if (failure instanceof OutputRequestCreateError) throw failure;
      return uncertain();
    }
  }
}
