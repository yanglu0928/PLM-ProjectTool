/** SOL_SPEC_GET fixed history; a DRAFT is not an approved solution. */
import type { SpecType, SpecRequirementRef, SpecSectionRef } from "./structuredSpecCreateClient";

export interface StructuredSpecDetail {
  readonly structured_solution_spec_id: string;
  readonly spec_series_id: string;
  readonly project_id: string;
  readonly spec_type: SpecType;
  readonly version_no: number;
  readonly version_state: "DRAFT" | "IN_REVIEW" | "APPROVED" | "RETURNED" | "SUPERSEDED" | "RESTRICTED";
  readonly content_fingerprint: string;
  readonly payload: Readonly<Record<string, unknown>>;
  readonly payload_fingerprint: string;
  readonly requirement_refs: readonly SpecRequirementRef[];
  readonly section_refs: readonly SpecSectionRef[];
  readonly evidence_ids: readonly string[];
  readonly artifact_ids: readonly string[];
  readonly declared_requirement_count: number;
  readonly declared_section_count: number;
  readonly declared_evidence_count: number;
  readonly supersedes_version_ref: string | null;
  readonly review_ref: string | null;
  readonly review_round_ref: string | null;
  readonly created_by: string;
  readonly created_at: string;
}

const messages = {
  STRUCTURED_SPEC_READ_INVALID: "项目或专项版本编号无效。",
  AUTH_SESSION_EXPIRED: "会话已失效，请重新登录。",
  LICENSE_OPERATION_DENIED: "当前许可不允许读取专项。",
  RESOURCE_NOT_FOUND: "专项版本不存在或无权查看。",
  STRUCTURED_SPEC_READ_UNAVAILABLE: "暂时无法读取专项版本，请稍后重试。",
} as const;
export type StructuredSpecReadErrorCode = keyof typeof messages;
export class StructuredSpecReadError extends Error {
  constructor(readonly code: StructuredSpecReadErrorCode) {
    super(messages[code]); this.name = "StructuredSpecReadError";
  }
}

const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const digest = /^[0-9a-f]{64}$/;
const stamp = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$/;
const fields = ["structured_solution_spec_id", "spec_series_id", "project_id",
  "spec_type", "version_no", "version_state", "content_fingerprint", "payload",
  "payload_fingerprint", "requirement_refs", "section_refs", "evidence_ids",
  "artifact_ids", "declared_requirement_count", "declared_section_count",
  "declared_evidence_count", "supersedes_version_ref", "review_ref",
  "review_round_ref", "created_by", "created_at"] as const;
function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
function exact(value: Record<string, unknown>, keys: readonly string[]): boolean {
  return Object.keys(value).length === keys.length && keys.every(key => Object.hasOwn(value, key));
}
function id(value: unknown): value is string {
  return typeof value === "string" && uuid.test(value)
    && value !== "00000000-0000-0000-0000-000000000000";
}
function optionalId(value: unknown): value is string | null { return value === null || id(value); }
function count(value: unknown, maximum: number): value is number {
  return typeof value === "number" && Number.isSafeInteger(value) && value >= 0 && value <= maximum;
}
function unique(values: readonly unknown[]): boolean { return new Set(values).size === values.length; }
function fail(): never { throw new StructuredSpecReadError("STRUCTURED_SPEC_READ_UNAVAILABLE"); }
function refs(value: unknown, keys: readonly [string, string]): value is readonly Record<string, string>[] {
  return Array.isArray(value) && value.length >= 1 && value.length <= 500
    && value.every(item => record(item) && exact(item, keys)
      && id(item[keys[0]]) && id(item[keys[1]]))
    && unique(value.map(item => item[keys[0]])) && unique(value.map(item => item[keys[1]]));
}

export function parseStructuredSpecDetail(value: unknown, project: string,
                                          spec: string): StructuredSpecDetail {
  if (!record(value) || !exact(value, fields)
    || value.project_id !== project || value.structured_solution_spec_id !== spec
    || !id(value.spec_series_id)
    || !["PROCESS_MODEL", "INTERFACE_SPEC", "MIGRATION_SPEC", "PERMISSION_DESIGN"]
      .includes(value.spec_type as string)
    || !count(value.version_no, Number.MAX_SAFE_INTEGER) || value.version_no < 1
    || !["DRAFT", "IN_REVIEW", "APPROVED", "RETURNED", "SUPERSEDED", "RESTRICTED"]
      .includes(value.version_state as string)
    || typeof value.content_fingerprint !== "string" || !digest.test(value.content_fingerprint)
    || typeof value.payload_fingerprint !== "string" || !digest.test(value.payload_fingerprint)
    || !record(value.payload) || !Object.keys(value.payload).length
    || !refs(value.requirement_refs, ["requirement_id", "requirement_version_id"])
    || !refs(value.section_refs, ["solution_section_id", "solution_section_version_id"])
    || !Array.isArray(value.evidence_ids) || value.evidence_ids.length > 500
    || !value.evidence_ids.every(id) || !unique(value.evidence_ids)
    || !Array.isArray(value.artifact_ids) || value.artifact_ids.length !== 0
    || value.declared_requirement_count !== value.requirement_refs.length
    || value.declared_section_count !== value.section_refs.length
    || value.declared_evidence_count !== value.evidence_ids.length
    || !optionalId(value.supersedes_version_ref)
    || (value.supersedes_version_ref === null) !== (value.version_no === 1)
    || !optionalId(value.review_ref) || !optionalId(value.review_round_ref)
    || (value.review_ref === null) !== (value.review_round_ref === null)
    || !id(value.created_by) || typeof value.created_at !== "string"
    || !stamp.test(value.created_at) || !Number.isFinite(Date.parse(value.created_at))) fail();
  try {
    if (new TextEncoder().encode(JSON.stringify(value.payload)).length > 1024 * 1024) fail();
  } catch { fail(); }
  return Object.freeze({ ...value,
    payload: Object.freeze({ ...value.payload }),
    requirement_refs: Object.freeze(value.requirement_refs.map(item => Object.freeze({ ...item }))),
    section_refs: Object.freeze(value.section_refs.map(item => Object.freeze({ ...item }))),
    evidence_ids: Object.freeze([...value.evidence_ids]),
    artifact_ids: Object.freeze([]),
  }) as unknown as StructuredSpecDetail;
}

export class StructuredSpecReadClient {
  constructor(private readonly fetcher: typeof fetch = (input, init) => fetch(input, init),
              private readonly timeoutMs = 10_000) {}

  async detail(project: string, spec: string): Promise<StructuredSpecDetail> {
    if (!id(project) || !id(spec)) {
      throw new StructuredSpecReadError("STRUCTURED_SPEC_READ_INVALID");
    }
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      const response = await this.fetcher(
        `/api/v1/projects/${project}/structured-solution-specs/${spec}`,
        { method: "GET", credentials: "same-origin", cache: "no-store", redirect: "error",
          headers: { Accept: "application/json" }, signal: controller.signal });
      if (controller.signal.aborted
        || response.headers.get("content-type")?.split(";")[0].trim().toLowerCase() !== "application/json"
        || response.headers.get("cache-control") !== "no-store") fail();
      const body: unknown = await response.json();
      if (!record(body) || !id(body.trace_id)
        || response.headers.get("x-trace-id") !== body.trace_id) fail();
      if (response.status !== 200) {
        const code = record(body.error) ? body.error.code : null;
        const statuses: Readonly<Record<string, number>> = {
          AUTH_SESSION_EXPIRED: 401, LICENSE_OPERATION_DENIED: 403, RESOURCE_NOT_FOUND: 404,
        };
        if (typeof code === "string" && statuses[code] === response.status) {
          throw new StructuredSpecReadError(code as StructuredSpecReadErrorCode);
        }
        fail();
      }
      if (!exact(body, ["data", "trace_id"]) || response.headers.has("etag")) fail();
      return parseStructuredSpecDetail(body.data, project, spec);
    } catch (error) {
      if (error instanceof StructuredSpecReadError) throw error;
      return fail();
    } finally { clearTimeout(timer); }
  }
}
