/** Project-only GLOBAL candidates are current choices, never an authorization proof for CREATE. */
export interface ProjectGlobalReferenceCandidate {
  readonly reference_solution_id: string;
  readonly reference_version_id: string;
  readonly display_label: string;
  readonly version_no: number;
  readonly eligibility_state: "ELIGIBLE";
}
export interface ProjectGlobalReferenceCandidatePage {
  readonly items: readonly ProjectGlobalReferenceCandidate[];
  readonly next_cursor: string | null;
  readonly has_more: boolean;
}

const messages = {
  CANDIDATE_INVALID_INPUT: "项目或翻页参数无效。",
  AUTH_SESSION_EXPIRED: "会话已失效，请重新登录。",
  LICENSE_OPERATION_DENIED: "当前许可不允许读取候选。",
  RESOURCE_NOT_FOUND: "项目不存在或无权查看候选。",
  PROJECT_ARCHIVED: "项目已归档，不能选择当前候选。",
  CANDIDATE_UNAVAILABLE: "无法完整核对当前候选，已停止选择；请稍后重试。",
} as const;
export type ProjectGlobalReferenceCandidateErrorCode = keyof typeof messages;
export class ProjectGlobalReferenceCandidateError extends Error {
  constructor(readonly code: ProjectGlobalReferenceCandidateErrorCode) {
    super(messages[code]); this.name = "ProjectGlobalReferenceCandidateError";
  }
}

const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const cursorPattern = /^[A-Za-z0-9_-]{1,512}\.[A-Za-z0-9_-]{43}$/;
function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
function exact(value: Record<string, unknown>, fields: readonly string[]): boolean {
  return Object.keys(value).length === fields.length && fields.every(field => Object.hasOwn(value, field));
}
function id(value: unknown): value is string {
  return typeof value === "string" && uuid.test(value) && value !== "00000000-0000-0000-0000-000000000000";
}
function unavailable(): never { throw new ProjectGlobalReferenceCandidateError("CANDIDATE_UNAVAILABLE"); }

export function parseProjectGlobalReferenceCandidatePage(
  value: unknown, pageSize: number, previousCursor: string | null = null,
): ProjectGlobalReferenceCandidatePage {
  if (!record(value) || !exact(value, ["items", "next_cursor", "has_more"])
    || !Array.isArray(value.items) || value.items.length > pageSize
    || typeof value.has_more !== "boolean"
    || value.has_more && (typeof value.next_cursor !== "string"
      || !cursorPattern.test(value.next_cursor) || value.next_cursor === previousCursor)
    || !value.has_more && value.next_cursor !== null) unavailable();
  const items = value.items.map((raw: unknown): ProjectGlobalReferenceCandidate => {
    if (!record(raw) || !exact(raw, ["reference_solution_id", "reference_version_id",
      "display_label", "version_no", "eligibility_state"])
      || !id(raw.reference_solution_id) || !id(raw.reference_version_id)
      || typeof raw.display_label !== "string" || raw.display_label.length < 1
      || raw.display_label.length > 160 || raw.display_label.trim() !== raw.display_label
      || /\p{C}/u.test(raw.display_label) || !Number.isSafeInteger(raw.version_no)
      || (raw.version_no as number) < 1 || raw.eligibility_state !== "ELIGIBLE") unavailable();
    return Object.freeze({ reference_solution_id: raw.reference_solution_id,
      reference_version_id: raw.reference_version_id, display_label: raw.display_label,
      version_no: raw.version_no as number, eligibility_state: "ELIGIBLE" });
  });
  if (items.some((item, index) => index > 0
    && items[index - 1]!.reference_solution_id >= item.reference_solution_id)) unavailable();
  return Object.freeze({ items: Object.freeze(items),
    next_cursor: value.next_cursor as string | null, has_more: value.has_more });
}

export class ProjectGlobalReferenceCandidateClient {
  constructor(private readonly fetcher: typeof fetch = fetch, private readonly timeoutMs = 10_000) {}
  async list(projectId: string, pageSize = 50,
             cursor: string | null = null): Promise<ProjectGlobalReferenceCandidatePage> {
    if (!id(projectId) || !Number.isSafeInteger(pageSize) || pageSize < 1 || pageSize > 100
      || cursor !== null && !cursorPattern.test(cursor)) {
      throw new ProjectGlobalReferenceCandidateError("CANDIDATE_INVALID_INPUT");
    }
    const params = new URLSearchParams({ page_size: String(pageSize) });
    if (cursor !== null) params.set("cursor", cursor);
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      const fetcher = this.fetcher;
      const response = await fetcher(`/api/v1/projects/${projectId}/global-reference-candidates?${params}`,
        { method: "GET", credentials: "same-origin", cache: "no-store", redirect: "error",
          headers: { Accept: "application/json" }, signal: controller.signal });
      if (controller.signal.aborted
        || response.headers.get("content-type")?.split(";")[0].trim().toLowerCase() !== "application/json"
        || response.headers.get("cache-control")?.toLowerCase() !== "no-store") unavailable();
      const payload: unknown = await response.json();
      if (!record(payload) || !id(payload.trace_id)) unavailable();
      if (response.status !== 200) {
        const code = record(payload.error) ? payload.error.code : null;
        const status: Readonly<Record<string, number>> = { AUTH_SESSION_EXPIRED: 401,
          LICENSE_OPERATION_DENIED: 403, RESOURCE_NOT_FOUND: 404, PROJECT_ARCHIVED: 409 };
        if (typeof code === "string" && status[code] === response.status) {
          throw new ProjectGlobalReferenceCandidateError(code as ProjectGlobalReferenceCandidateErrorCode);
        }
        unavailable();
      }
      if (!exact(payload, ["data", "trace_id"])) unavailable();
      return parseProjectGlobalReferenceCandidatePage(payload.data, pageSize, cursor);
    } catch (failure) {
      if (failure instanceof ProjectGlobalReferenceCandidateError) throw failure;
      return unavailable();
    } finally { clearTimeout(timer); }
  }
}
