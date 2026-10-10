/** Current Job detail transport. ETag is a version, never a permission token. */
import { JobListError, parseJobItem, type JobListItem } from "./jobListClient";

const messages = {
  AUTH_SESSION_EXPIRED: "会话已失效，请重新登录。",
  LICENSE_OPERATION_DENIED: "当前许可不允许查看任务。",
  RESOURCE_NOT_FOUND: "任务不存在或无权查看。",
  JOB_DETAIL_INVALID_ID: "任务或项目标识无效。",
  JOB_DETAIL_UNAVAILABLE: "暂时无法读取任务详情，请稍后重试。",
} as const;
export type JobDetailErrorCode = keyof typeof messages;
export class JobDetailError extends Error {
  constructor(readonly code: JobDetailErrorCode) { super(messages[code]); this.name = "JobDetailError"; }
}
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
function identifier(value: unknown): value is string {
  return typeof value === "string" && uuid.test(value) && value !== "00000000-0000-0000-0000-000000000000";
}
function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export class JobDetailClient {
  constructor(private readonly fetcher: typeof fetch = fetch, private readonly timeoutMs = 10_000) {
    if (!Number.isInteger(timeoutMs) || timeoutMs < 1 || timeoutMs > 30_000) throw new JobDetailError("JOB_DETAIL_UNAVAILABLE");
  }

  async getProject(projectId: string, jobId: string): Promise<JobListItem> {
    if (!identifier(projectId) || !identifier(jobId)) throw new JobDetailError("JOB_DETAIL_INVALID_ID");
    return this.#get(`/api/v1/projects/${projectId}/jobs/${jobId}`, projectId, jobId);
  }

  async getAdmin(jobId: string): Promise<JobListItem> {
    if (!identifier(jobId)) throw new JobDetailError("JOB_DETAIL_INVALID_ID");
    return this.#get(`/api/v1/admin/jobs/${jobId}`, null, jobId);
  }

  async #get(path: string, projectId: string | null, jobId: string): Promise<JobListItem> {
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      const fetcher = this.fetcher;
      const response = await fetcher(path, { method: "GET", credentials: "same-origin", cache: "no-store",
        redirect: "error", headers: { Accept: "application/json" }, signal: controller.signal });
      if (controller.signal.aborted || response.headers.get("content-type")?.split(";")[0].trim().toLowerCase() !== "application/json") {
        throw new JobDetailError("JOB_DETAIL_UNAVAILABLE");
      }
      const payload: unknown = await response.json();
      if (controller.signal.aborted || !record(payload) || !identifier(payload.trace_id)) throw new JobDetailError("JOB_DETAIL_UNAVAILABLE");
      if (response.status !== 200) {
        const code = record(payload.error) ? payload.error.code : null;
        const expected: Record<string, number> = { AUTH_SESSION_EXPIRED: 401, LICENSE_OPERATION_DENIED: 403, RESOURCE_NOT_FOUND: 404 };
        if (typeof code === "string" && Object.hasOwn(expected, code) && response.status === expected[code]) {
          throw new JobDetailError(code as JobDetailErrorCode);
        }
        throw new JobDetailError("JOB_DETAIL_UNAVAILABLE");
      }
      const item = parseJobItem(payload.data, projectId, null);
      if (item.job_id !== jobId || response.headers.get("etag") !== item.etag) throw new JobDetailError("JOB_DETAIL_UNAVAILABLE");
      return item;
    } catch (error) {
      if (error instanceof JobDetailError) throw error;
      if (error instanceof JobListError) throw new JobDetailError("JOB_DETAIL_UNAVAILABLE");
      throw new JobDetailError("JOB_DETAIL_UNAVAILABLE");
    } finally { window.clearTimeout(timer); }
  }
}
