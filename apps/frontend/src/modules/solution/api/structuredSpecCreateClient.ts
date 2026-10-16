/** SOL-06 fixed DRAFT command; an unknown result retains the exact key and body. */
import { SessionClient, SessionClientError } from "@/modules/auth/api/sessionClient";

export type SpecType = "PROCESS_MODEL" | "INTERFACE_SPEC" | "MIGRATION_SPEC" | "PERMISSION_DESIGN";
export interface SpecRequirementRef { readonly requirement_id: string; readonly requirement_version_id: string }
export interface SpecSectionRef { readonly solution_section_id: string; readonly solution_section_version_id: string }
export interface StructuredSpecDraft {
  readonly spec_type: SpecType;
  readonly payload: Readonly<Record<string, unknown>>;
  readonly requirement_refs: readonly SpecRequirementRef[];
  readonly section_refs: readonly SpecSectionRef[];
  readonly evidence_ids: readonly string[];
  readonly artifact_ids: readonly [];
}
export interface StructuredSpecCreated extends StructuredSpecDraft {
  readonly structured_solution_spec_id: string;
  readonly spec_series_id: string;
  readonly project_id: string;
  readonly version_no: number;
  readonly version_state: "DRAFT";
  readonly content_fingerprint: string;
  readonly payload_fingerprint: string;
  readonly declared_requirement_count: number;
  readonly declared_section_count: number;
  readonly declared_evidence_count: number;
  readonly supersedes_version_ref: null;
  readonly review_ref: null;
  readonly review_round_ref: null;
  readonly created_by: string;
  readonly created_at: string;
}

const messages = {
  STRUCTURED_SPEC_CREATE_INVALID: "项目、专项类型、固定来源、载荷或操作号无效。",
  STRUCTURED_SPEC_CREATE_UNCERTAIN: "结果无法确认；请保留原操作号与原内容，勿换号重试。",
  AUTH_RELOGIN_REQUIRED: "请重新登录。",
  AUTH_CLIENT_BUSY: "账户操作进行中，请稍候。",
  AUTH_SESSION_EXPIRED: "会话已失效，请重新登录。",
  AUTH_CSRF_INVALID: "登录状态已变化，请重新登录。",
  LICENSE_OPERATION_DENIED: "当前许可不允许创建专项草案。",
  RESOURCE_NOT_FOUND: "项目或固定来源不存在，或无权访问。",
  PROJECT_ARCHIVED: "项目已归档，不可创建专项草案。",
  VALIDATION_FAILED: "专项载荷或固定来源不符合要求。",
  CONFLICT_IDEMPOTENCY: "操作号已用于不同内容；请核对历史。",
  SYSTEM_UNAVAILABLE: "服务暂不可用；请核对原操作。",
} as const;
export type StructuredSpecCreateErrorCode = keyof typeof messages;
export class StructuredSpecCreateError extends Error {
  readonly uncertain: boolean;
  constructor(readonly code: StructuredSpecCreateErrorCode) {
    super(messages[code]); this.name = "StructuredSpecCreateError";
    this.uncertain = code === "STRUCTURED_SPEC_CREATE_UNCERTAIN";
  }
}
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const digest = /^[0-9a-f]{64}$/;
const stamp = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$/;
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
function unique(values: readonly string[]): boolean { return new Set(values).size === values.length; }
export function stableStructuredSpecValue(value: unknown): string {
  return JSON.stringify(value, (_key, item: unknown) => {
    if (record(item)) return Object.fromEntries(Object.entries(item).sort(([a], [b]) => a.localeCompare(b)));
    return item;
  });
}
function invalid(): never { throw new StructuredSpecCreateError("STRUCTURED_SPEC_CREATE_INVALID"); }
function uncertain(): never { throw new StructuredSpecCreateError("STRUCTURED_SPEC_CREATE_UNCERTAIN"); }
function refs(value: unknown, fields: readonly [string, string]): value is readonly Record<string, string>[] {
  return Array.isArray(value) && value.length >= 1 && value.length <= 500
    && value.every(item => record(item) && exact(item, fields) && id(item[fields[0]]) && id(item[fields[1]]))
    && unique(value.map(item => item[fields[0]])) && unique(value.map(item => item[fields[1]]));
}
export function isStructuredSpecDraft(value: unknown): value is StructuredSpecDraft {
  if (!record(value) || !exact(value, ["spec_type", "payload", "requirement_refs",
    "section_refs", "evidence_ids", "artifact_ids"])
    || !["PROCESS_MODEL", "INTERFACE_SPEC", "MIGRATION_SPEC", "PERMISSION_DESIGN"]
      .includes(value.spec_type as string)
    || !record(value.payload) || Object.keys(value.payload).length === 0
    || !refs(value.requirement_refs, ["requirement_id", "requirement_version_id"])
    || !refs(value.section_refs, ["solution_section_id", "solution_section_version_id"])
    || !Array.isArray(value.evidence_ids) || value.evidence_ids.length > 500
    || !value.evidence_ids.every(id) || !unique(value.evidence_ids)
    || !Array.isArray(value.artifact_ids) || value.artifact_ids.length !== 0) return false;
  try { return new TextEncoder().encode(JSON.stringify(value)).length <= 512 * 1024; }
  catch { return false; }
}
const fields = ["structured_solution_spec_id", "spec_series_id", "project_id",
  "spec_type", "version_no", "version_state", "content_fingerprint", "payload",
  "payload_fingerprint", "requirement_refs", "section_refs", "evidence_ids",
  "artifact_ids", "declared_requirement_count", "declared_section_count",
  "declared_evidence_count", "supersedes_version_ref", "review_ref",
  "review_round_ref", "created_by", "created_at"] as const;
function created(value: unknown, project: string, response: Response,
                 trace: string, draft: StructuredSpecDraft): StructuredSpecCreated {
  if (!record(value) || !exact(value, fields) || !id(value.structured_solution_spec_id)
    || !id(value.spec_series_id) || value.project_id !== project
    || value.spec_type !== draft.spec_type || value.version_no !== 1
    || value.version_state !== "DRAFT"
    || typeof value.content_fingerprint !== "string" || !digest.test(value.content_fingerprint)
    || typeof value.payload_fingerprint !== "string" || !digest.test(value.payload_fingerprint)
    || !record(value.payload) || stableStructuredSpecValue(value.payload) !== stableStructuredSpecValue(draft.payload)
    || stableStructuredSpecValue(value.requirement_refs) !== stableStructuredSpecValue(draft.requirement_refs)
    || stableStructuredSpecValue(value.section_refs) !== stableStructuredSpecValue(draft.section_refs)
    || stableStructuredSpecValue(value.evidence_ids) !== stableStructuredSpecValue(draft.evidence_ids)
    || !Array.isArray(value.artifact_ids) || value.artifact_ids.length !== 0
    || value.declared_requirement_count !== draft.requirement_refs.length
    || value.declared_section_count !== draft.section_refs.length
    || value.declared_evidence_count !== draft.evidence_ids.length
    || value.supersedes_version_ref !== null || value.review_ref !== null
    || value.review_round_ref !== null || !id(value.created_by)
    || typeof value.created_at !== "string" || !stamp.test(value.created_at)
    || !Number.isFinite(Date.parse(value.created_at))
    || response.headers.get("location") !== `/api/v1/projects/${project}/structured-solution-specs/`
      + value.structured_solution_spec_id
    || response.headers.get("x-trace-id") !== trace) uncertain();
  return Object.freeze(value) as unknown as StructuredSpecCreated;
}

export class StructuredSpecCreateClient {
  constructor(private readonly session: SessionClient) {
    if (!(session instanceof SessionClient)) invalid();
  }
  async create(project: string, draft: StructuredSpecDraft,
               key: string): Promise<StructuredSpecCreated> {
    if (!id(project) || !isStructuredSpecDraft(draft)
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
    try { response = await this.session.postProjectStructuredSpecCreate(project, body, key); }
    catch (failure) {
      if (failure instanceof SessionClientError
        && (failure.code === "AUTH_RELOGIN_REQUIRED" || failure.code === "AUTH_CLIENT_BUSY")) {
        throw new StructuredSpecCreateError(failure.code);
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
          AUTH_SESSION_EXPIRED: 401, AUTH_CSRF_INVALID: 403, LICENSE_OPERATION_DENIED: 403,
          RESOURCE_NOT_FOUND: 404, PROJECT_ARCHIVED: 409, VALIDATION_FAILED: 422,
          CONFLICT_IDEMPOTENCY: 409, SYSTEM_UNAVAILABLE: 503,
        };
        if (typeof code === "string" && statuses[code] === response.status) {
          throw new StructuredSpecCreateError(code as StructuredSpecCreateErrorCode);
        }
        uncertain();
      }
      if (!exact(payload, ["data", "trace_id"])) uncertain();
      return created(payload.data, project, response, payload.trace_id as string, draft);
    } catch (failure) {
      if (failure instanceof StructuredSpecCreateError) throw failure;
      return uncertain();
    }
  }
}
