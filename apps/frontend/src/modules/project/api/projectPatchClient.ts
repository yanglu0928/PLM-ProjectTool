import { SessionClient, SessionClientError } from "@/modules/auth/api/sessionClient";
import { parseProject, ProjectReadError, type ProjectView } from "./projectReadClient";

const messages = {
  PROJECT_PATCH_INVALID_INPUT: "请检查当前项目、版本和新名称。",
  AUTH_RELOGIN_REQUIRED: "修改项目前请重新登录。",
  AUTH_CLIENT_BUSY: "正在处理会话操作，请稍候。",
  AUTH_SESSION_EXPIRED: "会话已失效，请重新登录。",
  AUTH_CSRF_INVALID: "登录状态已变化，请重新登录。",
  LICENSE_OPERATION_DENIED: "当前许可不允许修改项目。",
  RESOURCE_NOT_FOUND: "项目不存在或当前账户无权修改。",
  PROJECT_ARCHIVED: "项目已归档，无法修改。",
  CONFLICT_VERSION: "项目信息已变化，请重新读取后再决定。",
  PROJECT_PATCH_UNCERTAIN: "项目修改结果无法确认。请重新读取项目，勿直接重试。",
} as const;
export type ProjectPatchErrorCode = keyof typeof messages;
export class ProjectPatchError extends Error {
  readonly uncertain: boolean;
  constructor(readonly code: ProjectPatchErrorCode) {
    super(messages[code]); this.name = "ProjectPatchError";
    this.uncertain = code === "PROJECT_PATCH_UNCERTAIN";
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
  const value = Number(etag.slice(2, -1));
  return Number.isSafeInteger(value) && value < Number.MAX_SAFE_INTEGER - 1 ? value : null;
}
function normalized(value: unknown): string {
  if (typeof value !== "string") throw new ProjectPatchError("PROJECT_PATCH_INVALID_INPUT");
  const result = value.normalize("NFKC").trim();
  if (result.length < 1 || result.length > 255 || /\p{C}/u.test(result)) {
    throw new ProjectPatchError("PROJECT_PATCH_INVALID_INPUT");
  }
  return result;
}

/** A non-idempotent PATCH response is a bounded result, not a substitute for a fresh GET. */
export class ProjectPatchClient {
  constructor(private readonly session: SessionClient) {
    if (!(session instanceof SessionClient)) throw new ProjectPatchError("PROJECT_PATCH_INVALID_INPUT");
  }

  async patch(projectId: string, before: ProjectView, newName: string): Promise<ProjectView> {
    if (!identifier(projectId)) throw new ProjectPatchError("PROJECT_PATCH_INVALID_INPUT");
    let original: ProjectView;
    try { original = parseProject(before); }
    catch { throw new ProjectPatchError("PROJECT_PATCH_INVALID_INPUT"); }
    const prior = version(original.etag);
    if (original.project_id !== projectId || original.state !== "ACTIVE" || prior === null) {
      throw new ProjectPatchError("PROJECT_PATCH_INVALID_INPUT");
    }
    const name = normalized(newName);
    let response: Response;
    try {
      response = await this.session.patchProject(projectId, original.etag, JSON.stringify({ name }));
    } catch (failure) {
      if (failure instanceof SessionClientError && failure.code === "AUTH_RELOGIN_REQUIRED") {
        throw new ProjectPatchError("AUTH_RELOGIN_REQUIRED");
      }
      if (failure instanceof SessionClientError && failure.code === "AUTH_CLIENT_BUSY") {
        throw new ProjectPatchError("AUTH_CLIENT_BUSY");
      }
      throw new ProjectPatchError("PROJECT_PATCH_UNCERTAIN");
    }
    try {
      if (response.headers.get("content-type")?.split(";")[0].trim().toLowerCase() !== "application/json") {
        throw new ProjectPatchError("PROJECT_PATCH_UNCERTAIN");
      }
      const payload: unknown = await response.json();
      if (!record(payload) || !identifier(payload.trace_id)) {
        throw new ProjectPatchError("PROJECT_PATCH_UNCERTAIN");
      }
      if (response.status !== 200) {
        const code = record(payload.error) ? payload.error.code : null;
        const expected: Record<string, number> = {
          AUTH_SESSION_EXPIRED: 401, AUTH_CSRF_INVALID: 403, LICENSE_OPERATION_DENIED: 403,
          RESOURCE_NOT_FOUND: 404, PROJECT_ARCHIVED: 409, CONFLICT_VERSION: 409,
          VALIDATION_FAILED: 422, REQUEST_MALFORMED: 400, CONFLICT_VERSION_REQUIRED: 428,
        };
        if (typeof code === "string" && Object.hasOwn(expected, code) && response.status === expected[code]) {
          throw new ProjectPatchError(["VALIDATION_FAILED", "REQUEST_MALFORMED",
            "CONFLICT_VERSION_REQUIRED"].includes(code)
            ? "PROJECT_PATCH_INVALID_INPUT" : code as ProjectPatchErrorCode);
        }
        throw new ProjectPatchError("PROJECT_PATCH_UNCERTAIN");
      }
      const updated = parseProject(payload.data);
      const expectedEtag = `"v${prior + 1}"`;
      if (updated.project_id !== original.project_id || updated.code !== original.code
        || updated.created_at !== original.created_at || updated.state !== "ACTIVE"
        || updated.name !== name || updated.etag !== expectedEtag
        || response.headers.get("etag") !== expectedEtag) {
        throw new ProjectPatchError("PROJECT_PATCH_UNCERTAIN");
      }
      return updated;
    } catch (failure) {
      if (failure instanceof ProjectPatchError) throw failure;
      if (failure instanceof ProjectReadError) throw new ProjectPatchError("PROJECT_PATCH_UNCERTAIN");
      throw new ProjectPatchError("PROJECT_PATCH_UNCERTAIN");
    }
  }
}
