import { SessionClient, SessionClientError } from "@/modules/auth/api/sessionClient";
import { parseProject, ProjectReadError, type ProjectView } from "./projectReadClient";

export interface ProjectArchiveFirstReceipt {
  readonly first_result: ProjectView;
  readonly is_current_state_proof: false;
}

const messages = {
  PROJECT_ARCHIVE_INVALID_INPUT: "请重新读取项目及版本后再操作。",
  AUTH_RELOGIN_REQUIRED: "归档项目前请重新登录。",
  AUTH_CLIENT_BUSY: "正在处理会话操作，请稍候。",
  AUTH_SESSION_EXPIRED: "会话已失效，请重新登录。",
  AUTH_CSRF_INVALID: "登录状态已变化，请重新登录。",
  LICENSE_OPERATION_DENIED: "当前许可不允许归档项目。",
  RESOURCE_NOT_FOUND: "项目不存在或当前账户无权操作。",
  PROJECT_ARCHIVED: "项目已归档，请重新读取后核对。",
  CONFLICT_VERSION: "项目信息已变化，请重新读取后再决定。",
  CONFLICT_STATE: "项目状态已变化，请重新读取后再决定。",
  CONFLICT_IDEMPOTENCY: "原操作记录与请求不一致，已停止重试。",
  PROJECT_ARCHIVE_UNCERTAIN: "归档结果无法确认；保留原操作记录和版本，先核对项目历史与审计。",
} as const;
export type ProjectArchiveErrorCode = keyof typeof messages;
export class ProjectArchiveError extends Error {
  readonly uncertain: boolean;
  constructor(readonly code: ProjectArchiveErrorCode) {
    super(messages[code]); this.name = "ProjectArchiveError";
    this.uncertain = code === "PROJECT_ARCHIVE_UNCERTAIN";
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
function version(etag: string): number | null {
  if (!/^"v(0|[1-9][0-9]*)"$/.test(etag)) return null;
  const prior = Number(etag.slice(2, -1));
  return Number.isSafeInteger(prior) && prior < Number.MAX_SAFE_INTEGER ? prior : null;
}

/** A replayed archive 200 is a first-result receipt, never a fresh Project GET. */
export class ProjectArchiveClient {
  constructor(private readonly session: SessionClient) {
    if (!(session instanceof SessionClient)) {
      throw new ProjectArchiveError("PROJECT_ARCHIVE_INVALID_INPUT");
    }
  }

  async archive(projectId: string, before: ProjectView, key: string): Promise<ProjectArchiveFirstReceipt> {
    if (!identifier(projectId) || typeof key !== "string" || !/^[\x20-\x7e]{16,128}$/.test(key)) {
      throw new ProjectArchiveError("PROJECT_ARCHIVE_INVALID_INPUT");
    }
    let original: ProjectView;
    try { original = parseProject(before); }
    catch { throw new ProjectArchiveError("PROJECT_ARCHIVE_INVALID_INPUT"); }
    const prior = version(original.etag);
    if (original.project_id !== projectId || original.state !== "ACTIVE"
      || prior === null || prior >= Number.MAX_SAFE_INTEGER - 1) {
      throw new ProjectArchiveError("PROJECT_ARCHIVE_INVALID_INPUT");
    }
    const expectedEtag = `"v${prior + 1}"`;
    let response: Response;
    try {
      response = await this.session.postProjectArchive(projectId, original.etag, key);
    } catch (failure) {
      if (failure instanceof SessionClientError && failure.code === "AUTH_RELOGIN_REQUIRED") {
        throw new ProjectArchiveError("AUTH_RELOGIN_REQUIRED");
      }
      if (failure instanceof SessionClientError && failure.code === "AUTH_CLIENT_BUSY") {
        throw new ProjectArchiveError("AUTH_CLIENT_BUSY");
      }
      throw new ProjectArchiveError("PROJECT_ARCHIVE_UNCERTAIN");
    }
    try {
      if (response.headers.get("content-type")?.split(";")[0].trim().toLowerCase() !== "application/json") {
        throw new ProjectArchiveError("PROJECT_ARCHIVE_UNCERTAIN");
      }
      const payload: unknown = await response.json();
      if (!record(payload) || !identifier(payload.trace_id)) {
        throw new ProjectArchiveError("PROJECT_ARCHIVE_UNCERTAIN");
      }
      if (response.status !== 200) {
        const code = record(payload.error) ? payload.error.code : null;
        const known: Record<string, number> = {
          AUTH_SESSION_EXPIRED: 401, AUTH_CSRF_INVALID: 403, LICENSE_OPERATION_DENIED: 403,
          RESOURCE_NOT_FOUND: 404, PROJECT_ARCHIVED: 409, CONFLICT_VERSION: 409,
          CONFLICT_STATE: 409, CONFLICT_IDEMPOTENCY: 409, REQUEST_MALFORMED: 400,
          VALIDATION_FAILED: 422, CONFLICT_VERSION_REQUIRED: 428,
        };
        if (typeof code === "string" && Object.hasOwn(known, code) && known[code] === response.status) {
          throw new ProjectArchiveError(["REQUEST_MALFORMED", "VALIDATION_FAILED",
            "CONFLICT_VERSION_REQUIRED"].includes(code)
            ? "PROJECT_ARCHIVE_INVALID_INPUT" : code as ProjectArchiveErrorCode);
        }
        throw new ProjectArchiveError("PROJECT_ARCHIVE_UNCERTAIN");
      }
      const first = parseProject(payload.data);
      if (first.project_id !== original.project_id || first.code !== original.code
        || first.name !== original.name || first.created_at !== original.created_at
        || first.state !== "ARCHIVED" || first.etag !== expectedEtag
        || response.headers.get("etag") !== expectedEtag) {
        throw new ProjectArchiveError("PROJECT_ARCHIVE_UNCERTAIN");
      }
      return Object.freeze({ first_result: first, is_current_state_proof: false as const });
    } catch (failure) {
      if (failure instanceof ProjectArchiveError) throw failure;
      if (failure instanceof ProjectReadError) {
        throw new ProjectArchiveError("PROJECT_ARCHIVE_UNCERTAIN");
      }
      throw new ProjectArchiveError("PROJECT_ARCHIVE_UNCERTAIN");
    }
  }
}
