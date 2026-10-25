/** SOL_SPEC_REVISE keeps the exact predecessor, body and key after an unknown result. */
import { SessionClient, SessionClientError } from "@/modules/auth/api/sessionClient";
import { isStructuredSpecDraft, stableStructuredSpecValue,
  type StructuredSpecDraft } from "./structuredSpecCreateClient";
import { parseStructuredSpecDetail, type StructuredSpecDetail } from "./structuredSpecReadClient";

export type StructuredSpecRevised = StructuredSpecDetail & {
  readonly version_state: "DRAFT";
  readonly supersedes_version_ref: string;
  readonly review_ref: null;
  readonly review_round_ref: null;
};

const messages = {
  STRUCTURED_SPEC_REVISE_INVALID: "项目、原专项版本、固定来源、载荷或操作号无效。",
  STRUCTURED_SPEC_REVISE_UNCERTAIN: "修订结果无法确认；请保留原操作号与原内容，勿换号重试。",
  AUTH_RELOGIN_REQUIRED: "请重新登录。",
  AUTH_CLIENT_BUSY: "账户操作进行中，请稍候。",
  AUTH_SESSION_EXPIRED: "会话已失效，请重新登录。",
  AUTH_CSRF_INVALID: "登录状态已变化，请重新登录。",
  LICENSE_OPERATION_DENIED: "当前许可不允许修订专项草案。",
  RESOURCE_NOT_FOUND: "专项版本不存在、来源不可用或无权访问。",
  PROJECT_ARCHIVED: "项目已归档，不可修订专项草案。",
  CONFLICT_VERSION: "该版本已不是最新版本，请返回历史并选择最新版本。",
  CONFLICT_STATE: "专项当前状态不允许修订。",
  CONFLICT_IDEMPOTENCY: "操作号已用于不同内容；请核对历史。",
  VALIDATION_FAILED: "专项载荷或固定来源不符合要求。",
  SYSTEM_UNAVAILABLE: "服务暂不可用；请核对原操作。",
} as const;
export type StructuredSpecReviseErrorCode = keyof typeof messages;
export class StructuredSpecReviseError extends Error {
  readonly uncertain: boolean;
  constructor(readonly code: StructuredSpecReviseErrorCode) {
    super(messages[code]); this.name = "StructuredSpecReviseError";
    this.uncertain = code === "STRUCTURED_SPEC_REVISE_UNCERTAIN";
  }
}

const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
function exact(value: Record<string, unknown>, fields: readonly string[]): boolean {
  return Object.keys(value).length === fields.length && fields.every(field => Object.hasOwn(value, field));
}
function id(value: unknown): value is string {
  return typeof value === "string" && uuid.test(value)
    && value !== "00000000-0000-0000-0000-000000000000";
}
function invalid(): never { throw new StructuredSpecReviseError("STRUCTURED_SPEC_REVISE_INVALID"); }
function uncertain(): never { throw new StructuredSpecReviseError("STRUCTURED_SPEC_REVISE_UNCERTAIN"); }

function revised(value: unknown, project: string, predecessor: string,
                 response: Response, trace: string,
                 draft: StructuredSpecDraft): StructuredSpecRevised {
  if (!record(value) || !id(value.structured_solution_spec_id)) uncertain();
  let item: StructuredSpecDetail;
  try { item = parseStructuredSpecDetail(value, project, value.structured_solution_spec_id); }
  catch { return uncertain(); }
  if (item.version_state !== "DRAFT" || item.version_no < 2
    || item.supersedes_version_ref !== predecessor || item.review_ref !== null
    || item.review_round_ref !== null || item.spec_type !== draft.spec_type
    || stableStructuredSpecValue(item.payload) !== stableStructuredSpecValue(draft.payload)
    || stableStructuredSpecValue(item.requirement_refs) !== stableStructuredSpecValue(draft.requirement_refs)
    || stableStructuredSpecValue(item.section_refs) !== stableStructuredSpecValue(draft.section_refs)
    || stableStructuredSpecValue(item.evidence_ids) !== stableStructuredSpecValue(draft.evidence_ids)
    || item.artifact_ids.length !== 0
    || response.headers.get("location") !== `/api/v1/projects/${project}/structured-solution-specs/`
      + item.structured_solution_spec_id
    || response.headers.get("x-trace-id") !== trace) uncertain();
  return item as StructuredSpecRevised;
}

export class StructuredSpecReviseClient {
  constructor(private readonly session: SessionClient) {
    if (!(session instanceof SessionClient)) invalid();
  }

  async revise(project: string, predecessor: string, draft: StructuredSpecDraft,
               key: string): Promise<StructuredSpecRevised> {
    if (!id(project) || !id(predecessor) || !isStructuredSpecDraft(draft)
      || typeof key !== "string" || !/^[\x20-\x7e]{16,128}$/.test(key)) invalid();
    const view = this.session.view;
    if (!view || view.password_change_required || !this.session.canSubmit
      || !view.authorized_projects.some(item => item.project_id === project
        && (item.role === "PROJECT_MANAGER" || item.role === "IMPLEMENTATION_MEMBER"))) invalid();
    let body: string;
    try { body = JSON.stringify(draft); }
    catch { return invalid(); }
    if (new TextEncoder().encode(body).length > 512 * 1024) invalid();
    let response: Response;
    try {
      response = await this.session.postProjectStructuredSpecRevise(
        project, predecessor, body, key);
    } catch (failure) {
      if (failure instanceof SessionClientError
        && (failure.code === "AUTH_RELOGIN_REQUIRED" || failure.code === "AUTH_CLIENT_BUSY")) {
        throw new StructuredSpecReviseError(failure.code);
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
          PROJECT_ARCHIVED: 409, CONFLICT_VERSION: 409, CONFLICT_STATE: 409,
          CONFLICT_IDEMPOTENCY: 409, VALIDATION_FAILED: 422,
          SYSTEM_UNAVAILABLE: 503,
        };
        if (typeof code === "string" && statuses[code] === response.status) {
          throw new StructuredSpecReviseError(code as StructuredSpecReviseErrorCode);
        }
        uncertain();
      }
      if (!exact(payload, ["data", "trace_id"])) uncertain();
      return revised(payload.data, project, predecessor, response,
        payload.trace_id as string, draft);
    } catch (failure) {
      if (failure instanceof StructuredSpecReviseError) throw failure;
      return uncertain();
    }
  }
}
