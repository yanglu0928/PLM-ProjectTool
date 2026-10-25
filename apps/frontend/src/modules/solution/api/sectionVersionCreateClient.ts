/** Frozen SectionVersion CREATE transport; unknown commits retain original key and body. */
import { SessionClient, SessionClientError } from "@/modules/auth/api/sessionClient";
import type { SectionRequirementRef } from "./sectionVersionReadClient";

export interface SectionVersionDraft {
  readonly title: string;
  readonly content_document_version_ref: string;
  readonly content_artifact_ref: null;
  readonly requirement_refs: readonly SectionRequirementRef[];
  readonly evidence_ids: readonly string[];
  readonly assumptions: readonly Record<string, unknown>[];
  readonly exclusions: readonly Record<string, unknown>[];
}
export interface SectionVersionCreated extends SectionVersionDraft {
  readonly solution_section_version_id: string;
  readonly solution_section_id: string;
  readonly project_id: string;
  readonly version_no: number;
  readonly version_state: "DRAFT";
  readonly content_fingerprint: string;
  readonly declared_requirement_count: number;
  readonly declared_evidence_count: number;
  readonly supersedes_version_ref: string | null;
  readonly review_ref: null;
  readonly review_round_ref: null;
  readonly created_by: string;
  readonly created_at: string;
}

const messages = {
  SECTION_VERSION_CREATE_INVALID: "项目、章节、固定来源、声明或操作号无效。",
  SECTION_VERSION_CREATE_UNCERTAIN: "创建结果无法确认；请保留原操作号与原内容，勿换号重试。",
  AUTH_RELOGIN_REQUIRED: "请重新登录。",
  AUTH_CLIENT_BUSY: "账户操作进行中，请稍候。",
  AUTH_SESSION_EXPIRED: "会话已失效，请重新登录。",
  AUTH_CSRF_INVALID: "登录状态已变化，请重新登录。",
  LICENSE_OPERATION_DENIED: "当前许可不允许创建章节版本。",
  RESOURCE_NOT_FOUND: "项目或章节不存在，或无权访问。",
  PROJECT_ARCHIVED: "项目已归档，不可创建章节版本。",
  VALIDATION_FAILED: "固定来源或声明不符合要求。",
  CONFLICT_IDEMPOTENCY: "操作号已用于不同内容；请核对历史。",
  SYSTEM_UNAVAILABLE: "服务暂不可用；请核对原操作。",
} as const;
export type SectionVersionCreateErrorCode = keyof typeof messages;
export class SectionVersionCreateError extends Error {
  readonly uncertain: boolean;
  constructor(readonly code: SectionVersionCreateErrorCode) {
    super(messages[code]); this.name = "SectionVersionCreateError";
    this.uncertain = code === "SECTION_VERSION_CREATE_UNCERTAIN";
  }
}
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
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
function invalid(): never { throw new SectionVersionCreateError("SECTION_VERSION_CREATE_INVALID"); }
function uncertain(): never { throw new SectionVersionCreateError("SECTION_VERSION_CREATE_UNCERTAIN"); }
function unique(values: readonly string[]): boolean { return new Set(values).size === values.length; }
function stable(value: unknown): string {
  return JSON.stringify(value, (_key, item: unknown) => {
    if (record(item)) return Object.fromEntries(Object.entries(item).sort(([left], [right]) => left.localeCompare(right)));
    return item;
  });
}
function declarations(value: unknown): value is readonly Record<string, unknown>[] {
  if (!Array.isArray(value) || value.length > 100 || value.some(item => !record(item))) return false;
  try { return new TextEncoder().encode(stable(value)).length <= 64_000; }
  catch { return false; }
}
function validDraft(value: SectionVersionDraft): boolean {
  if (!record(value) || !exact(value, ["title", "content_document_version_ref",
    "content_artifact_ref", "requirement_refs", "evidence_ids", "assumptions", "exclusions"])
    || typeof value.title !== "string" || value.title.length < 1 || value.title.length > 500
    || value.title !== value.title.trim() || value.title !== value.title.normalize("NFC")
    || /[\p{Cc}\p{Cs}]/u.test(value.title)
    || !id(value.content_document_version_ref) || value.content_artifact_ref !== null
    || !Array.isArray(value.requirement_refs) || value.requirement_refs.length > 500
    || !Array.isArray(value.evidence_ids) || value.evidence_ids.length > 500
    || !value.evidence_ids.every(id) || !unique(value.evidence_ids)
    || !declarations(value.assumptions) || !declarations(value.exclusions)) return false;
  return value.requirement_refs.every(item => record(item)
      && exact(item, ["requirement_id", "requirement_version_id"])
      && id(item.requirement_id) && id(item.requirement_version_id))
    && unique(value.requirement_refs.map(item => item.requirement_id))
    && unique(value.requirement_refs.map(item => item.requirement_version_id));
}
const fields = ["solution_section_version_id", "solution_section_id", "project_id",
  "version_no", "version_state", "title", "content_document_version_ref",
  "content_artifact_ref", "content_fingerprint", "requirement_refs", "evidence_ids",
  "assumptions", "exclusions", "declared_requirement_count", "declared_evidence_count",
  "supersedes_version_ref", "review_ref", "review_round_ref", "created_by", "created_at"] as const;
function created(value: unknown, project: string, section: string, response: Response,
                 trace: string, draft: SectionVersionDraft): SectionVersionCreated {
  if (!record(value) || !exact(value, fields) || !id(value.solution_section_version_id)
    || value.project_id !== project || value.solution_section_id !== section
    || !Number.isSafeInteger(value.version_no) || (value.version_no as number) < 1
    || value.version_state !== "DRAFT" || value.title !== draft.title
    || value.content_document_version_ref !== draft.content_document_version_ref
    || value.content_artifact_ref !== null
    || typeof value.content_fingerprint !== "string" || !/^[0-9a-f]{64}$/.test(value.content_fingerprint)
    || !Array.isArray(value.requirement_refs)
    || stable(value.requirement_refs) !== stable(draft.requirement_refs)
    || !Array.isArray(value.evidence_ids)
    || stable(value.evidence_ids) !== stable(draft.evidence_ids)
    || !declarations(value.assumptions) || stable(value.assumptions) !== stable(draft.assumptions)
    || !declarations(value.exclusions) || stable(value.exclusions) !== stable(draft.exclusions)
    || value.declared_requirement_count !== draft.requirement_refs.length
    || value.declared_evidence_count !== draft.evidence_ids.length
    || value.supersedes_version_ref !== null && !id(value.supersedes_version_ref)
    || value.review_ref !== null || value.review_round_ref !== null
    || !id(value.created_by) || typeof value.created_at !== "string" || !stamp.test(value.created_at)
    || !Number.isFinite(Date.parse(value.created_at))
    || response.headers.get("location") !== `/api/v1/projects/${project}/solution-sections/${section}`
      + `/versions/${value.solution_section_version_id}`
    || response.headers.get("x-trace-id") !== trace) uncertain();
  return Object.freeze(value) as unknown as SectionVersionCreated;
}

export class SectionVersionCreateClient {
  constructor(private readonly session: SessionClient) {
    if (!(session instanceof SessionClient)) invalid();
  }
  async create(project: string, section: string, draft: SectionVersionDraft,
               key: string): Promise<SectionVersionCreated> {
    if (!id(project) || !id(section) || !validDraft(draft)
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
    try { response = await this.session.postProjectSectionVersionCreate(project, section, body, key); }
    catch (failure) {
      if (failure instanceof SessionClientError
        && (failure.code === "AUTH_RELOGIN_REQUIRED" || failure.code === "AUTH_CLIENT_BUSY")) {
        throw new SectionVersionCreateError(failure.code);
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
          throw new SectionVersionCreateError(code as SectionVersionCreateErrorCode);
        }
        uncertain();
      }
      if (!exact(payload, ["data", "trace_id"])) uncertain();
      return created(payload.data, project, section, response, payload.trace_id as string, draft);
    } catch (failure) {
      if (failure instanceof SectionVersionCreateError) throw failure;
      return uncertain();
    }
  }
}
