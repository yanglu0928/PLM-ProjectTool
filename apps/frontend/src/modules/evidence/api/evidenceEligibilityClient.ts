import { SessionClient, SessionClientError } from "@/modules/auth/api/sessionClient";
import type { EvidenceViewerDescriptor } from "./evidenceViewerClient";

export interface CurrentEvidenceEligibility {
  readonly evidence_id: string;
  readonly document_id: string;
  readonly document_version_id: string;
  readonly eligibility_state: "CANDIDATE" | "ELIGIBLE" | "INELIGIBLE" | "REVOKED";
  readonly etag: string;
}
export interface EvidenceEligibilityFirstReceipt {
  readonly evidence_id: string;
  readonly eligibility_state: "ELIGIBLE" | "INELIGIBLE";
  readonly eligibility_reason: string;
  readonly etag: string;
  readonly is_current_state_proof: false;
}

const messages = {
  EVIDENCE_ELIGIBILITY_INVALID: "请重新读取证据和固定原文后再确认。",
  EVIDENCE_ELIGIBILITY_UNCERTAIN: "提交结果暂无法确认；请保留当前操作记录，重新查看资格和审计，勿换新操作号重复提交。",
  AUTH_RELOGIN_REQUIRED: "请重新登录后再确认。",
  AUTH_CLIENT_BUSY: "正在处理账户操作，请稍候。",
  AUTH_SESSION_EXPIRED: "会话已失效，请重新登录。",
  AUTH_CSRF_INVALID: "登录状态已变化，请重新登录。",
  LICENSE_OPERATION_DENIED: "当前许可不允许确认资格。",
  RESOURCE_NOT_FOUND: "证据或原文不存在，或您无权确认。",
  PROJECT_ARCHIVED: "项目已归档，不允许确认资格。",
  CONFLICT_VERSION: "证据资格已变化，请重新读取后再决定。",
  CONFLICT_STATE: "此来源或当前状态不允许这样确认；模板不得作为客户事实。",
  CONFLICT_IDEMPOTENCY: "此操作号已用于不同内容，请停止提交并核对历史。",
} as const;
export type EvidenceEligibilityErrorCode = keyof typeof messages;
export class EvidenceEligibilityClientError extends Error {
  constructor(readonly code: EvidenceEligibilityErrorCode) {
    super(messages[code]); this.name = "EvidenceEligibilityClientError";
  }
}

const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const etagPattern = /^"v(0|[1-9][0-9]*)"$/;
function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
function id(value: unknown): value is string {
  return typeof value === "string" && uuid.test(value)
    && value !== "00000000-0000-0000-0000-000000000000";
}
function version(value: unknown): number | null {
  if (typeof value !== "string" || !etagPattern.test(value)) return null;
  const parsed = Number(value.slice(2, -1));
  return Number.isSafeInteger(parsed) && parsed < Number.MAX_SAFE_INTEGER - 1 ? parsed : null;
}
function parseCurrent(value: unknown, header: string | null): CurrentEvidenceEligibility {
  if (!record(value) || !id(value.evidence_id) || !id(value.document_id)
    || !id(value.document_version_id)
    || !["CANDIDATE", "ELIGIBLE", "INELIGIBLE", "REVOKED"].includes(String(value.eligibility_state))
    || version(value.etag) === null || value.etag !== header) {
    throw new EvidenceEligibilityClientError("EVIDENCE_ELIGIBILITY_UNCERTAIN");
  }
  return Object.freeze({ evidence_id: value.evidence_id,
    document_id: value.document_id, document_version_id: value.document_version_id,
    eligibility_state: value.eligibility_state as CurrentEvidenceEligibility["eligibility_state"],
    etag: value.etag as string });
}
function reason(value: string): boolean {
  return typeof value === "string" && value.length >= 1 && value.length <= 1024
    && value.trim() === value && !/\p{C}/u.test(value);
}

export class EvidenceEligibilityClient {
  constructor(private readonly session: SessionClient,
    private readonly fetcher: typeof fetch = fetch, private readonly timeoutMs = 10_000) {
    if (!(session instanceof SessionClient) || !Number.isInteger(timeoutMs)
      || timeoutMs < 1 || timeoutMs > 30_000) {
      throw new EvidenceEligibilityClientError("EVIDENCE_ELIGIBILITY_INVALID");
    }
  }

  async current(projectId: string, evidenceId: string): Promise<CurrentEvidenceEligibility> {
    if (!id(projectId) || !id(evidenceId) || !this.session.view
      || this.session.view.password_change_required) {
      throw new EvidenceEligibilityClientError("EVIDENCE_ELIGIBILITY_INVALID");
    }
    return this.#current(`/api/v1/projects/${projectId}/evidence/${evidenceId}`,
      evidenceId, this.session.view.user.user_id);
  }

  async currentGlobal(evidenceId: string): Promise<CurrentEvidenceEligibility> {
    if (!id(evidenceId) || !this.session.view
      || this.session.view.password_change_required
      || this.session.view.deployment_role !== "DEPLOYMENT_ADMIN") {
      throw new EvidenceEligibilityClientError("EVIDENCE_ELIGIBILITY_INVALID");
    }
    return this.#current(`/api/v1/global/evidence/${evidenceId}`,
      evidenceId, this.session.view.user.user_id);
  }

  async #current(path: string, evidenceId: string,
    actor: string): Promise<CurrentEvidenceEligibility> {
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      // Native browser fetch rejects a class-instance receiver in Edge.
      const fetcher = this.fetcher;
      const response = await fetcher(path, {
        method: "GET", credentials: "same-origin", cache: "no-store", redirect: "error",
        headers: { Accept: "application/json" }, signal: controller.signal,
      });
      if (controller.signal.aborted || response.headers.get("content-type")?.split(";")[0].trim().toLowerCase()
        !== "application/json") throw new EvidenceEligibilityClientError("EVIDENCE_ELIGIBILITY_UNCERTAIN");
      const payload: unknown = await response.json();
      if (!record(payload) || !id(payload.trace_id)) {
        throw new EvidenceEligibilityClientError("EVIDENCE_ELIGIBILITY_UNCERTAIN");
      }
      if (response.status !== 200) {
        const code = record(payload.error) ? payload.error.code : null;
        const known: Record<string, number> = { AUTH_SESSION_EXPIRED: 401,
          LICENSE_OPERATION_DENIED: 403, RESOURCE_NOT_FOUND: 404 };
        if (typeof code === "string" && Object.hasOwn(known, code) && known[code] === response.status) {
          throw new EvidenceEligibilityClientError(code as EvidenceEligibilityErrorCode);
        }
        throw new EvidenceEligibilityClientError("EVIDENCE_ELIGIBILITY_UNCERTAIN");
      }
      const current = parseCurrent(payload.data, response.headers.get("etag"));
      if (current.evidence_id !== evidenceId || this.session.view?.user.user_id !== actor) {
        throw new EvidenceEligibilityClientError("EVIDENCE_ELIGIBILITY_UNCERTAIN");
      }
      return current;
    } catch (failure) {
      if (failure instanceof EvidenceEligibilityClientError) throw failure;
      throw new EvidenceEligibilityClientError("EVIDENCE_ELIGIBILITY_UNCERTAIN");
    } finally { window.clearTimeout(timer); }
  }

  async set(projectId: string, before: CurrentEvidenceEligibility,
    verified: EvidenceViewerDescriptor, target: "ELIGIBLE" | "INELIGIBLE",
    justification: string, key: string): Promise<EvidenceEligibilityFirstReceipt> {
    if (!id(projectId)) throw new EvidenceEligibilityClientError("EVIDENCE_ELIGIBILITY_INVALID");
    return this.#set(`/api/v1/projects/${projectId}`, before, verified, target, justification, key,
      () => this.session.postEvidenceEligibility(projectId, before.evidence_id, before.etag, key,
        JSON.stringify({ eligibility_state: target, reason: justification })));
  }

  async setGlobal(before: CurrentEvidenceEligibility, verified: EvidenceViewerDescriptor,
    target: "ELIGIBLE" | "INELIGIBLE", justification: string,
    key: string): Promise<EvidenceEligibilityFirstReceipt> {
    if (this.session.view?.deployment_role !== "DEPLOYMENT_ADMIN"
      || this.session.view.password_change_required) {
      throw new EvidenceEligibilityClientError("EVIDENCE_ELIGIBILITY_INVALID");
    }
    return this.#set("/api/v1/global", before, verified, target, justification, key,
      () => this.session.postGlobalEvidenceEligibility(before.evidence_id, before.etag, key,
        JSON.stringify({ eligibility_state: target, reason: justification })));
  }

  async #set(scopeBase: string, before: CurrentEvidenceEligibility,
    verified: EvidenceViewerDescriptor, target: "ELIGIBLE" | "INELIGIBLE",
    justification: string, key: string,
    send: () => Promise<Response>): Promise<EvidenceEligibilityFirstReceipt> {
    const prior = version(before?.etag);
    if (!id(before?.evidence_id) || !id(before?.document_id)
      || !id(before?.document_version_id) || before.eligibility_state !== "CANDIDATE"
      || prior === null || !id(verified?.evidence_id)
      || verified.evidence_id !== before.evidence_id
      || verified.document_id !== before.document_id
      || verified.document_version_id !== before.document_version_id
      || verified.content_url !== `${scopeBase}/documents/${before.document_id}/versions/${before.document_version_id}/content`
      || (target !== "ELIGIBLE" && target !== "INELIGIBLE")
      || !reason(justification) || !/^[\x20-\x7e]{16,128}$/.test(key)) {
      throw new EvidenceEligibilityClientError("EVIDENCE_ELIGIBILITY_INVALID");
    }
    let response: Response;
    try {
      response = await send();
    } catch (failure) {
      if (failure instanceof SessionClientError && failure.code === "AUTH_RELOGIN_REQUIRED") {
        throw new EvidenceEligibilityClientError("AUTH_RELOGIN_REQUIRED");
      }
      if (failure instanceof SessionClientError && failure.code === "AUTH_CLIENT_BUSY") {
        throw new EvidenceEligibilityClientError("AUTH_CLIENT_BUSY");
      }
      throw new EvidenceEligibilityClientError("EVIDENCE_ELIGIBILITY_UNCERTAIN");
    }
    try {
      if (response.headers.get("content-type")?.split(";")[0].trim().toLowerCase()
        !== "application/json") throw new EvidenceEligibilityClientError("EVIDENCE_ELIGIBILITY_UNCERTAIN");
      const payload: unknown = await response.json();
      if (!record(payload) || !id(payload.trace_id)) {
        throw new EvidenceEligibilityClientError("EVIDENCE_ELIGIBILITY_UNCERTAIN");
      }
      if (response.status !== 200) {
        const code = record(payload.error) ? payload.error.code : null;
        const known: Record<string, number> = {
          AUTH_SESSION_EXPIRED: 401, AUTH_CSRF_INVALID: 403,
          LICENSE_OPERATION_DENIED: 403, RESOURCE_NOT_FOUND: 404,
          PROJECT_ARCHIVED: 409, CONFLICT_VERSION: 409, CONFLICT_STATE: 409,
          CONFLICT_IDEMPOTENCY: 409, VALIDATION_FAILED: 422,
        };
        if (typeof code === "string" && Object.hasOwn(known, code) && known[code] === response.status) {
          throw new EvidenceEligibilityClientError(code === "VALIDATION_FAILED"
            ? "EVIDENCE_ELIGIBILITY_INVALID" : code as EvidenceEligibilityErrorCode);
        }
        throw new EvidenceEligibilityClientError("EVIDENCE_ELIGIBILITY_UNCERTAIN");
      }
      const data = payload.data;
      const expected = `"v${prior + 1}"`;
      if (!record(data) || data.evidence_id !== before.evidence_id
        || data.eligibility_state !== target || data.eligibility_reason !== justification
        || data.etag !== expected || response.headers.get("etag") !== expected) {
        throw new EvidenceEligibilityClientError("EVIDENCE_ELIGIBILITY_UNCERTAIN");
      }
      return Object.freeze({ evidence_id: before.evidence_id,
        eligibility_state: target, eligibility_reason: justification,
        etag: expected, is_current_state_proof: false as const });
    } catch (failure) {
      if (failure instanceof EvidenceEligibilityClientError) throw failure;
      throw new EvidenceEligibilityClientError("EVIDENCE_ELIGIBILITY_UNCERTAIN");
    }
  }
}
