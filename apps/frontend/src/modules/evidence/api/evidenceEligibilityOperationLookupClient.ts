import { SessionClient, SessionClientError } from "@/modules/auth/api/sessionClient";

export type EvidenceEligibilityOperationLookup = Readonly<
  { status: "UNCONFIRMED"; is_current_state_proof: false }
  | { status: "COMPLETED"; evidence_id: string; first_status_code: 200;
      is_current_state_proof: false }>;

const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
function id(value: unknown): value is string {
  return typeof value === "string" && uuid.test(value)
    && value !== "00000000-0000-0000-0000-000000000000";
}
function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
const messages = {
  EVIDENCE_LOOKUP_INVALID: "回查参数无效；请保留原操作号。",
  EVIDENCE_LOOKUP_DENIED: "当前身份或许可不允许回查；请保留原操作号。",
  EVIDENCE_LOOKUP_UNAVAILABLE: "暂时无法核对原操作；请保留原操作号，不要重新提交。",
  AUTH_RELOGIN_REQUIRED: "请重新登录后使用原操作号回查。",
  AUTH_CLIENT_BUSY: "正在处理其他账户操作，请稍候。",
} as const;
export type EvidenceEligibilityOperationLookupErrorCode = keyof typeof messages;
export class EvidenceEligibilityOperationLookupError extends Error {
  constructor(readonly code: EvidenceEligibilityOperationLookupErrorCode) {
    super(messages[code]); this.name = "EvidenceEligibilityOperationLookupError";
  }
}

export class EvidenceEligibilityOperationLookupClient {
  constructor(private readonly session: SessionClient) {
    if (!(session instanceof SessionClient)) {
      throw new EvidenceEligibilityOperationLookupError("EVIDENCE_LOOKUP_INVALID");
    }
  }

  async lookup(projectId: string, evidenceId: string,
    operationKey: string): Promise<EvidenceEligibilityOperationLookup> {
    const view = this.session.view;
    const actorId = view?.user.user_id;
    const role = view?.authorized_projects.find((item) => item.project_id === projectId)?.role;
    if (!id(projectId) || !id(evidenceId) || !id(actorId)
      || view?.password_change_required || (role !== "PROJECT_MANAGER" && role !== "CUSTOMER_MANAGER")) {
      throw new EvidenceEligibilityOperationLookupError("EVIDENCE_LOOKUP_DENIED");
    }
    if (typeof operationKey !== "string" || !/^[\x20-\x7e]{16,128}$/.test(operationKey)) {
      throw new EvidenceEligibilityOperationLookupError("EVIDENCE_LOOKUP_INVALID");
    }
    return this.#perform(evidenceId, actorId,
      this.session.postEvidenceEligibilityOperationLookup(projectId, evidenceId, operationKey));
  }

  async lookupGlobal(evidenceId: string,
    operationKey: string): Promise<EvidenceEligibilityOperationLookup> {
    const view = this.session.view;
    const actorId = view?.user.user_id;
    if (!id(evidenceId) || !id(actorId) || view?.password_change_required
      || view?.deployment_role !== "DEPLOYMENT_ADMIN") {
      throw new EvidenceEligibilityOperationLookupError("EVIDENCE_LOOKUP_DENIED");
    }
    if (typeof operationKey !== "string" || !/^[\x20-\x7e]{16,128}$/.test(operationKey)) {
      throw new EvidenceEligibilityOperationLookupError("EVIDENCE_LOOKUP_INVALID");
    }
    return this.#perform(evidenceId, actorId,
      this.session.postGlobalEvidenceEligibilityOperationLookup(evidenceId, operationKey));
  }

  async #perform(evidenceId: string, actorId: string,
    request: Promise<Response>): Promise<EvidenceEligibilityOperationLookup> {
    let response: Response;
    try {
      response = await request;
    } catch (failure) {
      if (failure instanceof SessionClientError && failure.code === "AUTH_RELOGIN_REQUIRED") {
        throw new EvidenceEligibilityOperationLookupError("AUTH_RELOGIN_REQUIRED");
      }
      if (failure instanceof SessionClientError && failure.code === "AUTH_CLIENT_BUSY") {
        throw new EvidenceEligibilityOperationLookupError("AUTH_CLIENT_BUSY");
      }
      throw new EvidenceEligibilityOperationLookupError("EVIDENCE_LOOKUP_UNAVAILABLE");
    }
    try {
      if (response.headers.get("content-type")?.split(";")[0].trim().toLowerCase()
        !== "application/json" || response.headers.get("cache-control") !== "no-store") {
        throw new EvidenceEligibilityOperationLookupError("EVIDENCE_LOOKUP_UNAVAILABLE");
      }
      const payload: unknown = await response.json();
      if (!record(payload) || !id(payload.trace_id)) {
        throw new EvidenceEligibilityOperationLookupError("EVIDENCE_LOOKUP_UNAVAILABLE");
      }
      if (response.status !== 200) {
        const code = record(payload.error) ? payload.error.code : null;
        if (response.status === 401 && code === "AUTH_SESSION_EXPIRED") {
          throw new EvidenceEligibilityOperationLookupError("AUTH_RELOGIN_REQUIRED");
        }
        if ((response.status === 403 && (code === "LICENSE_OPERATION_DENIED"
          || code === "AUTH_CSRF_INVALID"))
          || (response.status === 404 && code === "RESOURCE_NOT_FOUND")) {
          throw new EvidenceEligibilityOperationLookupError("EVIDENCE_LOOKUP_DENIED");
        }
        throw new EvidenceEligibilityOperationLookupError("EVIDENCE_LOOKUP_UNAVAILABLE");
      }
      const data = payload.data;
      if (!record(data) || this.session.view?.user.user_id !== actorId) {
        throw new EvidenceEligibilityOperationLookupError("EVIDENCE_LOOKUP_UNAVAILABLE");
      }
      if (data.status === "UNCONFIRMED" && Object.keys(data).length === 1) {
        return Object.freeze({ status: "UNCONFIRMED", is_current_state_proof: false });
      }
      if (data.status === "COMPLETED" && Object.keys(data).length === 3
        && data.evidence_id === evidenceId && data.first_status_code === 200) {
        return Object.freeze({ status: "COMPLETED", evidence_id: evidenceId,
          first_status_code: 200, is_current_state_proof: false });
      }
      throw new EvidenceEligibilityOperationLookupError("EVIDENCE_LOOKUP_UNAVAILABLE");
    } catch (failure) {
      if (failure instanceof EvidenceEligibilityOperationLookupError) throw failure;
      throw new EvidenceEligibilityOperationLookupError("EVIDENCE_LOOKUP_UNAVAILABLE");
    }
  }
}
