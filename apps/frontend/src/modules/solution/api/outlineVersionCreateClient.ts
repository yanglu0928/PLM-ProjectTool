/** Frozen SOL_OUTLINE_VERSION_CREATE transport. An unknown commit keeps its original key. */
import { SessionClient, SessionClientError } from "@/modules/auth/api/sessionClient";

export interface OutlineRequirementRef {
  readonly requirement_id: string;
  readonly requirement_version_id: string;
}
export interface OutlineReferenceRef {
  readonly scope: "PROJECT" | "GLOBAL";
  readonly reference_solution_id: string;
  readonly reference_version_id: string;
}
export interface OutlineVersionDraft {
  readonly section_ids: readonly string[];
  readonly requirement_refs: readonly OutlineRequirementRef[];
  readonly reference_refs: readonly OutlineReferenceRef[];
  readonly missing_declarations: readonly Record<string, unknown>[];
  readonly conflict_declarations: readonly Record<string, unknown>[];
}
export interface OutlineVersionCreated {
  readonly solution_outline_version_id: string;
  readonly solution_outline_id: string;
  readonly project_id: string;
  readonly version_no: number;
  readonly version_state: "DRAFT";
  readonly content_fingerprint: string;
  readonly missing_declarations: readonly Record<string, unknown>[];
  readonly conflict_declarations: readonly Record<string, unknown>[];
  readonly declared_section_count: number;
  readonly declared_requirement_count: number;
  readonly declared_reference_count: number;
  readonly supersedes_version_ref: string | null;
  readonly review_ref: null;
  readonly review_round_ref: null;
  readonly created_by: string;
  readonly created_at: string;
}

const messages = {
  OUTLINE_VERSION_CREATE_INVALID: "项目、方案目录、固定来源、声明或操作号无效。",
  OUTLINE_VERSION_CREATE_UNCERTAIN: "创建结果无法确认；请保留原操作号与原内容，勿换号重试。",
  AUTH_RELOGIN_REQUIRED: "请重新登录。",
  AUTH_CLIENT_BUSY: "账户操作进行中，请稍候。",
  AUTH_SESSION_EXPIRED: "会话已失效，请重新登录。",
  AUTH_CSRF_INVALID: "登录状态已变化，请重新登录。",
  LICENSE_OPERATION_DENIED: "当前许可不允许创建方案版本。",
  RESOURCE_NOT_FOUND: "项目或方案目录不存在，或无权访问。",
  PROJECT_ARCHIVED: "项目已归档，不可创建方案版本。",
  VALIDATION_FAILED: "固定来源或声明不符合要求。",
  CONFLICT_IDEMPOTENCY: "操作号已用于不同内容；请核对历史。",
  SYSTEM_UNAVAILABLE: "服务暂不可用；请核对原操作。",
} as const;
export type OutlineVersionCreateErrorCode = keyof typeof messages;
export class OutlineVersionCreateError extends Error {
  readonly uncertain: boolean;
  constructor(readonly code: OutlineVersionCreateErrorCode) {
    super(messages[code]);
    this.name = "OutlineVersionCreateError";
    this.uncertain = code === "OUTLINE_VERSION_CREATE_UNCERTAIN";
  }
}
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const stamp = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$/;
const fields = ["solution_outline_version_id", "solution_outline_id", "project_id", "version_no",
  "version_state", "content_fingerprint", "missing_declarations", "conflict_declarations",
  "declared_section_count", "declared_requirement_count", "declared_reference_count",
  "supersedes_version_ref", "review_ref", "review_round_ref", "created_by", "created_at"] as const;
function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
function exact(value: Record<string, unknown>, keys: readonly string[]): boolean {
  return Object.keys(value).length === keys.length && keys.every(key => Object.hasOwn(value, key));
}
function id(value: unknown): value is string {
  return typeof value === "string" && uuid.test(value) && value !== "00000000-0000-0000-0000-000000000000";
}
function invalid(): never { throw new OutlineVersionCreateError("OUTLINE_VERSION_CREATE_INVALID"); }
function uncertain(): never { throw new OutlineVersionCreateError("OUTLINE_VERSION_CREATE_UNCERTAIN"); }
function declarations(value: unknown): value is readonly Record<string, unknown>[] {
  if (!Array.isArray(value) || value.length > 100 || value.some(item => !record(item))) return false;
  try { return new TextEncoder().encode(JSON.stringify(value)).length <= 64_000; }
  catch { return false; }
}
function unique(values: readonly string[]): boolean { return new Set(values).size === values.length; }
function validDraft(value: OutlineVersionDraft): boolean {
  if (!record(value) || !exact(value, ["section_ids", "requirement_refs", "reference_refs",
    "missing_declarations", "conflict_declarations"])
    || !Array.isArray(value.section_ids) || value.section_ids.length < 1 || value.section_ids.length > 100
    || !value.section_ids.every(id) || !unique(value.section_ids)
    || !Array.isArray(value.requirement_refs) || value.requirement_refs.length > 500
    || !Array.isArray(value.reference_refs) || value.reference_refs.length > 500
    || !declarations(value.missing_declarations) || !declarations(value.conflict_declarations)
    || value.requirement_refs.length === 0 && value.reference_refs.length === 0
      && value.missing_declarations.length === 0) return false;
  const requirements = value.requirement_refs;
  const references = value.reference_refs;
  return requirements.every(item => record(item) && exact(item, ["requirement_id", "requirement_version_id"])
      && id(item.requirement_id) && id(item.requirement_version_id))
    && unique(requirements.map(item => item.requirement_id))
    && unique(requirements.map(item => item.requirement_version_id))
    && references.every(item => record(item) && exact(item, ["scope", "reference_solution_id", "reference_version_id"])
      && (item.scope === "PROJECT" || item.scope === "GLOBAL")
      && id(item.reference_solution_id) && id(item.reference_version_id))
    && unique(references.map(item => item.reference_solution_id))
    && unique(references.map(item => item.reference_version_id));
}
function created(value: unknown, projectId: string, outlineId: string, response: Response,
                 trace: string, draft: OutlineVersionDraft): OutlineVersionCreated {
  if (!record(value) || !exact(value, fields) || !id(value.solution_outline_version_id)
    || value.solution_outline_id !== outlineId || value.project_id !== projectId
    || !Number.isSafeInteger(value.version_no) || (value.version_no as number) < 1
    || value.version_state !== "DRAFT"
    || typeof value.content_fingerprint !== "string" || !/^[0-9a-f]{64}$/.test(value.content_fingerprint)
    || !declarations(value.missing_declarations) || !declarations(value.conflict_declarations)
    || !Number.isSafeInteger(value.declared_section_count)
    || value.declared_section_count !== draft.section_ids.length
    || value.declared_requirement_count !== draft.requirement_refs.length
    || value.declared_reference_count !== draft.reference_refs.length
    || value.supersedes_version_ref !== null && !id(value.supersedes_version_ref)
    || value.review_ref !== null || value.review_round_ref !== null || !id(value.created_by)
    || typeof value.created_at !== "string" || !stamp.test(value.created_at)
    || !Number.isFinite(Date.parse(value.created_at))
    || response.headers.get("location") !== `/api/v1/projects/${projectId}/solution-outlines/${outlineId}`
      + `/versions/${value.solution_outline_version_id}`
    || response.headers.get("x-trace-id") !== trace) uncertain();
  return Object.freeze(value) as unknown as OutlineVersionCreated;
}

export class OutlineVersionCreateClient {
  constructor(private readonly session: SessionClient) {
    if (!(session instanceof SessionClient)) invalid();
  }
  async create(projectId: string, outlineId: string, draft: OutlineVersionDraft,
               key: string): Promise<OutlineVersionCreated> {
    if (!id(projectId) || !id(outlineId) || !validDraft(draft)
      || typeof key !== "string" || !/^[\x20-\x7e]{16,128}$/.test(key)) invalid();
    const view = this.session.view;
    if (!view || view.password_change_required || !this.session.canSubmit
      || !view.authorized_projects.some(item => item.project_id === projectId
        && (item.role === "PROJECT_MANAGER" || item.role === "IMPLEMENTATION_MEMBER"))) invalid();
    let body: string;
    try { body = JSON.stringify(draft); }
    catch { return invalid(); }
    if (new TextEncoder().encode(body).length > 512 * 1024) invalid();
    let response: Response;
    try { response = await this.session.postProjectOutlineVersionCreate(projectId, outlineId, body, key); }
    catch (failure) {
      if (failure instanceof SessionClientError
        && (failure.code === "AUTH_RELOGIN_REQUIRED" || failure.code === "AUTH_CLIENT_BUSY")) {
        throw new OutlineVersionCreateError(failure.code);
      }
      return uncertain();
    }
    try {
      if (response.headers.get("content-type")?.split(";")[0].trim().toLowerCase() !== "application/json") uncertain();
      const payload: unknown = await response.json();
      if (!record(payload) || !id(payload.trace_id)) uncertain();
      if (response.status !== 201) {
        const code = record(payload.error) ? payload.error.code : null;
        const statuses: Readonly<Record<string, number>> = { AUTH_SESSION_EXPIRED: 401,
          AUTH_CSRF_INVALID: 403, LICENSE_OPERATION_DENIED: 403, RESOURCE_NOT_FOUND: 404,
          PROJECT_ARCHIVED: 409, VALIDATION_FAILED: 422, CONFLICT_IDEMPOTENCY: 409,
          SYSTEM_UNAVAILABLE: 503 };
        if (typeof code === "string" && statuses[code] === response.status) {
          throw new OutlineVersionCreateError(code as OutlineVersionCreateErrorCode);
        }
        uncertain();
      }
      if (!exact(payload, ["data", "trace_id"])) uncertain();
      return created(payload.data, projectId, outlineId, response, payload.trace_id as string, draft);
    } catch (failure) {
      if (failure instanceof OutlineVersionCreateError) throw failure;
      return uncertain();
    }
  }
}
