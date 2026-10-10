import { SessionClient, SessionClientError } from "@/modules/auth/api/sessionClient";
import type { JobListItem } from "./jobListClient";

export interface JobCancelFirstReceipt {
  readonly first_result: Readonly<{
    job_id: string;
    state: "CANCEL_REQUESTED" | "CANCELLED" | "SUCCEEDED" | "FAILED";
    changed: boolean;
    etag: string;
    status_url: string;
  }>;
  readonly is_current_state_proof: false;
}

const messages = {
  JOB_CANCEL_INVALID_INPUT: "请重新读取任务及版本后再操作。",
  AUTH_RELOGIN_REQUIRED: "取消任务前请重新登录。",
  AUTH_CLIENT_BUSY: "正在处理会话操作，请稍候。",
  AUTH_SESSION_EXPIRED: "会话已失效，请重新登录。",
  AUTH_CSRF_INVALID: "登录状态已变化，请重新登录。",
  LICENSE_OPERATION_DENIED: "当前许可不允许取消任务。",
  RESOURCE_NOT_FOUND: "任务不存在或当前账户无权操作。",
  CONFLICT_VERSION: "任务状态已变化，请重新读取后再决定。",
  CONFLICT_IDEMPOTENCY: "原操作记录与请求不一致，已停止重试。",
  JOB_CANCEL_UNCERTAIN: "取消结果无法确认；保留原操作号和版本，核对当前任务与操作记录。",
} as const;
export type JobCancelErrorCode = keyof typeof messages;
export class JobCancelError extends Error {
  readonly uncertain: boolean;
  constructor(readonly code: JobCancelErrorCode) {
    super(messages[code]); this.name = "JobCancelError";
    this.uncertain = code === "JOB_CANCEL_UNCERTAIN";
  }
}

const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const versionPattern = /^"v(0|[1-9][0-9]*)"$/;
function identifier(value: unknown): value is string {
  return typeof value === "string" && uuid.test(value) && value !== "00000000-0000-0000-0000-000000000000";
}
function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
function version(value: unknown): number | null {
  if (typeof value !== "string" || !versionPattern.test(value)) return null;
  const number = Number(value.slice(2, -1));
  return Number.isSafeInteger(number) && number < Number.MAX_SAFE_INTEGER ? number : null;
}

/** An original cancellation receipt can be replayed after the Job has advanced. */
export class JobCancelClient {
  constructor(private readonly session: SessionClient) {
    if (!(session instanceof SessionClient)) throw new JobCancelError("JOB_CANCEL_INVALID_INPUT");
  }

  async cancel(projectId: string, before: JobListItem, key: string, reason: string): Promise<JobCancelFirstReceipt> {
    const prior = record(before) ? version(before.etag) : null;
    if (!identifier(projectId) || !record(before) || !identifier(before.job_id)
      || before.project_id !== projectId || before.scope !== "PROJECT" || prior === null
      || typeof key !== "string" || !/^[\x20-\x7e]{16,128}$/.test(key)
      || typeof reason !== "string" || reason.trim().length < 1 || reason.trim().length > 1024
      || /\p{C}/u.test(reason.trim())) {
      throw new JobCancelError("JOB_CANCEL_INVALID_INPUT");
    }
    let response: Response;
    try {
      response = await this.session.postProjectJobCancel(projectId, before.job_id, before.etag, key, reason);
    } catch (failure) {
      if (failure instanceof SessionClientError && failure.code === "AUTH_RELOGIN_REQUIRED") {
        throw new JobCancelError("AUTH_RELOGIN_REQUIRED");
      }
      if (failure instanceof SessionClientError && failure.code === "AUTH_CLIENT_BUSY") {
        throw new JobCancelError("AUTH_CLIENT_BUSY");
      }
      throw new JobCancelError("JOB_CANCEL_UNCERTAIN");
    }
    try {
      if (response.headers.get("content-type")?.split(";")[0].trim().toLowerCase() !== "application/json") {
        throw new JobCancelError("JOB_CANCEL_UNCERTAIN");
      }
      const payload: unknown = await response.json();
      if (!record(payload) || !identifier(payload.trace_id)) throw new JobCancelError("JOB_CANCEL_UNCERTAIN");
      if (response.status !== 200) {
        const code = record(payload.error) ? payload.error.code : null;
        const known: Record<string, number> = {
          AUTH_SESSION_EXPIRED: 401, AUTH_CSRF_INVALID: 403, LICENSE_OPERATION_DENIED: 403,
          RESOURCE_NOT_FOUND: 404, CONFLICT_VERSION: 409, CONFLICT_IDEMPOTENCY: 409,
          REQUEST_MALFORMED: 400, VALIDATION_FAILED: 422, CONFLICT_VERSION_REQUIRED: 428,
        };
        if (typeof code === "string" && Object.hasOwn(known, code) && known[code] === response.status) {
          throw new JobCancelError(["REQUEST_MALFORMED", "VALIDATION_FAILED", "CONFLICT_VERSION_REQUIRED"].includes(code)
            ? "JOB_CANCEL_INVALID_INPUT" : code as JobCancelErrorCode);
        }
        throw new JobCancelError("JOB_CANCEL_UNCERTAIN");
      }
      const first = payload.data;
      const resultVersion = record(first) ? version(first.etag) : null;
      const statusUrl = `/api/v1/projects/${projectId}/jobs/${before.job_id}`;
      if (!record(first) || first.job_id !== before.job_id
        || !["CANCEL_REQUESTED", "CANCELLED", "SUCCEEDED", "FAILED"].includes(String(first.state))
        || typeof first.changed !== "boolean" || (first.changed && ["SUCCEEDED", "FAILED"].includes(String(first.state)))
        || resultVersion === null || resultVersion < prior
        || response.headers.get("etag") !== first.etag || first.status_url !== statusUrl) {
        throw new JobCancelError("JOB_CANCEL_UNCERTAIN");
      }
      return Object.freeze({ first_result: Object.freeze({ job_id: first.job_id as string,
        state: first.state as JobCancelFirstReceipt["first_result"]["state"], changed: first.changed,
        etag: first.etag as string, status_url: first.status_url as string }), is_current_state_proof: false as const });
    } catch (failure) {
      if (failure instanceof JobCancelError) throw failure;
      throw new JobCancelError("JOB_CANCEL_UNCERTAIN");
    }
  }
}
