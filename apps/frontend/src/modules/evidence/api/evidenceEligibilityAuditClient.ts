import { SessionClient } from "@/modules/auth/api/sessionClient";

export interface EvidenceEligibilityAuditEvent {
  readonly audit_event_id: string;
  readonly occurred_at: string;
  readonly trace_id: string;
  readonly after_state: "ELIGIBLE" | "INELIGIBLE";
}
export interface EvidenceEligibilityAuditPage {
  readonly items: readonly EvidenceEligibilityAuditEvent[];
  readonly next_cursor: string | null;
  readonly has_more: boolean;
}

const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const cursorPattern = /^[A-Za-z0-9_-]{1,2048}\.[A-Za-z0-9_-]{43}$/;
function id(value: unknown): value is string {
  return typeof value === "string" && uuid.test(value)
    && value !== "00000000-0000-0000-0000-000000000000";
}
function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
function utc(value: unknown): value is string {
  return typeof value === "string"
    && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$/.test(value)
    && Number.isFinite(Date.parse(value));
}
const messages = {
  EVIDENCE_AUDIT_INVALID: "审计查询参数无效。",
  EVIDENCE_AUDIT_DENIED: "当前身份无权查看项目审计；请联系项目负责人核对。",
  EVIDENCE_AUDIT_UNAVAILABLE: "暂时无法核对资格审计；请保留操作号，不要重复提交。",
} as const;
export type EvidenceEligibilityAuditErrorCode = keyof typeof messages;
export class EvidenceEligibilityAuditError extends Error {
  constructor(readonly code: EvidenceEligibilityAuditErrorCode) {
    super(messages[code]); this.name = "EvidenceEligibilityAuditError";
  }
}

function parseEvent(value: unknown, projectId: string, evidenceId: string,
                    actorId: string): EvidenceEligibilityAuditEvent {
  if (!record(value) || !id(value.audit_event_id) || !utc(value.occurred_at)
    || !id(value.trace_id) || value.event_scope !== "PROJECT"
    || value.project_id !== projectId || !record(value.actor)
    || value.actor.type !== "USER" || value.actor.user_id !== actorId
    || value.action !== "EVIDENCE_ELIGIBILITY_SET" || value.outcome !== "SUCCESS"
    || !record(value.target) || value.target.owner_module !== "evidence"
    || value.target.object_type !== "EVD-01" || value.target.object_id !== evidenceId
    || !record(value.summary) || value.summary.before_state !== "CANDIDATE"
    || !["ELIGIBLE", "INELIGIBLE"].includes(String(value.summary.after_state))) {
    throw new EvidenceEligibilityAuditError("EVIDENCE_AUDIT_UNAVAILABLE");
  }
  return Object.freeze({ audit_event_id: value.audit_event_id,
    occurred_at: value.occurred_at, trace_id: value.trace_id,
    after_state: value.summary.after_state as EvidenceEligibilityAuditEvent["after_state"] });
}

export class EvidenceEligibilityAuditClient {
  constructor(private readonly session: SessionClient,
    private readonly fetcher: typeof fetch = fetch, private readonly timeoutMs = 10_000) {
    if (!(session instanceof SessionClient) || !Number.isInteger(timeoutMs)
      || timeoutMs < 1 || timeoutMs > 30_000) {
      throw new EvidenceEligibilityAuditError("EVIDENCE_AUDIT_INVALID");
    }
  }

  async list(projectId: string, evidenceId: string,
    cursor: string | null = null): Promise<EvidenceEligibilityAuditPage> {
    const actorId = this.session.view?.user.user_id;
    if (!id(projectId) || !id(evidenceId) || !id(actorId)
      || this.session.view?.password_change_required
      || this.session.view?.authorized_projects.find((item) => item.project_id === projectId)?.role
        !== "PROJECT_MANAGER") {
      throw new EvidenceEligibilityAuditError("EVIDENCE_AUDIT_DENIED");
    }
    if (cursor !== null && (typeof cursor !== "string" || !cursorPattern.test(cursor))) {
      throw new EvidenceEligibilityAuditError("EVIDENCE_AUDIT_INVALID");
    }
    const params = new URLSearchParams({ page_size: "50", action: "EVIDENCE_ELIGIBILITY_SET",
      outcome: "SUCCESS", actor_id: actorId, target_object_type: "EVD-01",
      target_object_id: evidenceId });
    if (cursor !== null) params.set("cursor", cursor);
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      const response = await this.fetcher(`/api/v1/projects/${projectId}/audit-events?${params}`, {
        method: "GET", credentials: "same-origin", cache: "no-store", redirect: "error",
        headers: { Accept: "application/json" }, signal: controller.signal,
      });
      if (controller.signal.aborted || response.headers.get("content-type")?.split(";")[0]
        .trim().toLowerCase() !== "application/json") {
        throw new EvidenceEligibilityAuditError("EVIDENCE_AUDIT_UNAVAILABLE");
      }
      const payload: unknown = await response.json();
      if (!record(payload) || !id(payload.trace_id)) {
        throw new EvidenceEligibilityAuditError("EVIDENCE_AUDIT_UNAVAILABLE");
      }
      if (response.status !== 200) {
        const code = record(payload.error) ? payload.error.code : null;
        if ((response.status === 401 && code === "AUTH_SESSION_EXPIRED")
          || (response.status === 404 && code === "RESOURCE_NOT_FOUND")) {
          throw new EvidenceEligibilityAuditError("EVIDENCE_AUDIT_DENIED");
        }
        throw new EvidenceEligibilityAuditError("EVIDENCE_AUDIT_UNAVAILABLE");
      }
      const data = payload.data;
      if (!record(data) || !Array.isArray(data.items) || data.items.length > 50
        || typeof data.has_more !== "boolean"
        || (data.has_more && (data.items.length === 0 || typeof data.next_cursor !== "string"
          || !cursorPattern.test(data.next_cursor) || data.next_cursor === cursor))
        || (!data.has_more && data.next_cursor !== null)
        || this.session.view?.user.user_id !== actorId) {
        throw new EvidenceEligibilityAuditError("EVIDENCE_AUDIT_UNAVAILABLE");
      }
      const items = data.items.map((item) => parseEvent(item, projectId, evidenceId, actorId));
      if (new Set(items.map((item) => item.audit_event_id)).size !== items.length) {
        throw new EvidenceEligibilityAuditError("EVIDENCE_AUDIT_UNAVAILABLE");
      }
      return Object.freeze({ items: Object.freeze(items),
        next_cursor: data.has_more ? data.next_cursor as string : null, has_more: data.has_more });
    } catch (failure) {
      if (failure instanceof EvidenceEligibilityAuditError) throw failure;
      throw new EvidenceEligibilityAuditError("EVIDENCE_AUDIT_UNAVAILABLE");
    } finally { window.clearTimeout(timer); }
  }
}
