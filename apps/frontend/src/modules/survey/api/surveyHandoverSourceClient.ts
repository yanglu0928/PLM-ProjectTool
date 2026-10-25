/** Read-only Handover candidates for Survey authoring; candidates are not confirmed Survey facts. */
import { SessionClient } from "@/modules/auth/api/sessionClient";

export type SurveyHandoverSourceCursor = string & { readonly __family: "survey-handover-sources" };
export interface SurveyHandoverSourceCandidate {
  readonly handover_item_row_id: string;
  readonly handover_analysis_version_id: string;
  readonly handover_analysis_id: string;
  readonly analysis_item_id: string;
  readonly project_id: string;
  readonly title: string;
  readonly state: "CONFIRMED" | "RESOLVED" | "ACCEPTED_RISK";
}
export interface SurveyHandoverSourcePage {
  readonly items: readonly SurveyHandoverSourceCandidate[];
  readonly next_cursor: SurveyHandoverSourceCursor | null;
  readonly has_more: boolean;
}
export class SurveyHandoverSourceError extends Error {
  constructor(readonly code: "INVALID_INPUT" | "ACCESS_DENIED" | "UNAVAILABLE"
    | "AUTH_SESSION_EXPIRED" | "LICENSE_OPERATION_DENIED" | "RESOURCE_NOT_FOUND"
    | "PROJECT_ARCHIVED" | "REQUEST_MALFORMED" | "VALIDATION_FAILED") {
    super({ INVALID_INPUT: "交接来源翻页参数无效。", ACCESS_DENIED: "当前账户无权选择此项目交接来源。",
      UNAVAILABLE: "交接来源暂不可用，请重新读取并核对当前批准版本。",
      AUTH_SESSION_EXPIRED: "会话已失效，请重新登录。",
      LICENSE_OPERATION_DENIED: "当前许可不允许读取交接来源。",
      RESOURCE_NOT_FOUND: "项目不存在或当前账户无权读取交接来源。",
      PROJECT_ARCHIVED: "项目已归档，不能读取当前交接来源。",
      REQUEST_MALFORMED: "翻页参数已失效，请从第一页重新读取。",
      VALIDATION_FAILED: "页长无效，请调整后重新读取。" }[code]);
    this.name = "SurveyHandoverSourceError";
  }
}

const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const cursorPattern = /^[A-Za-z0-9_-]{1,1024}\.[A-Za-z0-9_-]{43}$/;
function id(value: unknown): value is string {
  return typeof value === "string" && uuid.test(value)
    && value !== "00000000-0000-0000-0000-000000000000";
}
function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
function exact(value: Record<string, unknown>, fields: readonly string[]): boolean {
  return Object.keys(value).length === fields.length && fields.every(field => Object.hasOwn(value, field));
}

export class SurveyHandoverSourceClient {
  constructor(private readonly session: SessionClient,
    private readonly fetcher: typeof fetch = fetch) {
    if (!(session instanceof SessionClient)) throw new SurveyHandoverSourceError("INVALID_INPUT");
  }

  async list(projectId: string, pageSize = 50,
    next: SurveyHandoverSourceCursor | null = null): Promise<SurveyHandoverSourcePage> {
    if (!id(projectId) || !Number.isSafeInteger(pageSize) || pageSize < 1 || pageSize > 200
      || next !== null && (typeof next !== "string" || !cursorPattern.test(next))) {
      throw new SurveyHandoverSourceError("INVALID_INPUT");
    }
    const view = this.session.view;
    if (!view || view.password_change_required || !view.authorized_projects.some(item =>
      item.project_id === projectId && (item.role === "PROJECT_MANAGER"
        || item.role === "IMPLEMENTATION_MEMBER"))) {
      throw new SurveyHandoverSourceError("ACCESS_DENIED");
    }
    const path = `/api/v1/projects/${projectId}/survey-handover-sources?page_size=${pageSize}`
      + (next === null ? "" : `&cursor=${encodeURIComponent(next)}`);
    let response: Response;
    try {
      const fetcher = this.fetcher;
      response = await fetcher(path, { method: "GET", credentials: "same-origin",
        cache: "no-store", redirect: "error", headers: { Accept: "application/json" } });
    } catch { throw new SurveyHandoverSourceError("UNAVAILABLE"); }
    try {
      if (response.headers.get("content-type")?.split(";")[0].trim().toLowerCase() !== "application/json"
        || response.headers.get("cache-control") !== "no-store") throw new Error();
      const payload: unknown = await response.json();
      if (!record(payload) || !id(payload.trace_id)
        || response.headers.get("x-trace-id") !== payload.trace_id) throw new Error();
      if (response.status !== 200) {
        const code = record(payload.error) ? payload.error.code : null;
        const statuses: Readonly<Record<string, number>> = {
          AUTH_SESSION_EXPIRED: 401, LICENSE_OPERATION_DENIED: 403,
          RESOURCE_NOT_FOUND: 404, PROJECT_ARCHIVED: 409,
          REQUEST_MALFORMED: 400, VALIDATION_FAILED: 422,
        };
        if (typeof code === "string" && statuses[code] === response.status) {
          throw new SurveyHandoverSourceError(code as SurveyHandoverSourceError["code"]);
        }
        throw new Error();
      }
      if (!exact(payload, ["data", "trace_id"]) || !record(payload.data)
        || !exact(payload.data, ["items", "next_cursor", "has_more"])
        || !Array.isArray(payload.data.items) || payload.data.items.length > pageSize
        || typeof payload.data.has_more !== "boolean"
        || payload.data.has_more !== (payload.data.next_cursor !== null)
        || payload.data.has_more && (payload.data.items.length === 0
          || typeof payload.data.next_cursor !== "string"
          || !cursorPattern.test(payload.data.next_cursor))) throw new Error();
      const seen = new Set<string>();
      const items = payload.data.items.map((value: unknown) => {
        if (!record(value) || !exact(value, ["handover_item_row_id",
          "handover_analysis_version_id", "handover_analysis_id", "analysis_item_id",
          "project_id", "title", "state"])
          || !id(value.handover_item_row_id) || !id(value.handover_analysis_version_id)
          || !id(value.handover_analysis_id) || !id(value.analysis_item_id)
          || value.project_id !== projectId || seen.has(value.handover_item_row_id)
          || typeof value.title !== "string" || value.title.length < 1
          || value.title.length > 255 || value.title !== value.title.trim()
          || !["CONFIRMED", "RESOLVED", "ACCEPTED_RISK"].includes(String(value.state))) throw new Error();
        seen.add(value.handover_item_row_id);
        return Object.freeze({ ...value }) as unknown as SurveyHandoverSourceCandidate;
      });
      return Object.freeze({ items: Object.freeze(items),
        next_cursor: payload.data.next_cursor as SurveyHandoverSourceCursor | null,
        has_more: payload.data.has_more });
    } catch (failure) {
      if (failure instanceof SurveyHandoverSourceError) throw failure;
      throw new SurveyHandoverSourceError("UNAVAILABLE");
    }
  }
}
