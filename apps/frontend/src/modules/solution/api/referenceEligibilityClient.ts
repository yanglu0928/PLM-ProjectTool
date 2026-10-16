/** Human Reference eligibility command; an accepted receipt is historical, not current state. */
import { SessionClient, SessionClientError } from "@/modules/auth/api/sessionClient";
import type { ReferenceCurrent } from "./referenceReadClient";
import type { GlobalReferenceCurrent } from "./globalReferenceReadClient";

export type EligibilityTarget = "ELIGIBLE" | "RESTRICTED" | "REVOKED";
export interface ReferenceEligibilityReceipt {
  readonly eligibility_event_id: string;
  readonly reference_solution_id: string;
  readonly reference_version_id: string;
  readonly scope: "PROJECT" | "GLOBAL";
  readonly project_id: string | null;
  readonly eligibility_state: EligibilityTarget;
  readonly eligibility_reason: string;
  readonly etag: string;
}
const messages = {
  REFERENCE_ELIGIBILITY_INVALID: "当前版本、资格状态、理由或操作号无效，请重新读取后核对。",
  REFERENCE_ELIGIBILITY_UNCERTAIN: "提交结果不确定；保留原操作号，先重新读取，勿换号重试。",
  AUTH_RELOGIN_REQUIRED: "请重新登录。", AUTH_CLIENT_BUSY: "账户操作进行中，请稍候。",
  AUTH_SESSION_EXPIRED: "登录已失效，请重新登录。", AUTH_CSRF_INVALID: "登录状态已变化，请重新登录。",
  LICENSE_OPERATION_DENIED: "当前许可不允许资格决定。", RESOURCE_NOT_FOUND: "参考方案不存在或无权访问。",
  PROJECT_ARCHIVED: "项目已归档。", VALIDATION_FAILED: "资格决定或理由不符合要求。",
  CONFLICT_VERSION: "当前版本已变化，请重新读取后再决定。",
  CONFLICT_STATE: "当前资格状态不允许此转换，请重新读取。",
  CONFLICT_IDEMPOTENCY: "操作号已用于不同内容，请核对历史。",
  SYSTEM_UNAVAILABLE: "来源或服务暂不可用，请核对原操作。",
} as const;
export type ReferenceEligibilityErrorCode = keyof typeof messages;
export class ReferenceEligibilityClientError extends Error {
  readonly uncertain: boolean;
  constructor(readonly code: ReferenceEligibilityErrorCode) {
    super(messages[code]); this.name = "ReferenceEligibilityClientError";
    this.uncertain = code === "REFERENCE_ELIGIBILITY_UNCERTAIN";
  }
}
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const etagPattern = /^"v(0|[1-9][0-9]*)"$/;
const allowed: Readonly<Record<string, readonly EligibilityTarget[]>> = {
  REFERENCE_ONLY: ["ELIGIBLE", "RESTRICTED", "REVOKED"],
  ELIGIBLE: ["RESTRICTED", "REVOKED"], RESTRICTED: ["ELIGIBLE", "REVOKED"], REVOKED: [],
};
function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
function exact(value: Record<string, unknown>, fields: readonly string[]): boolean {
  return Object.keys(value).length === fields.length && fields.every(field => Object.hasOwn(value, field));
}
function id(value: unknown): value is string {
  return typeof value === "string" && uuid.test(value) && value !== "00000000-0000-0000-0000-000000000000";
}
function etag(value: unknown): value is string {
  return typeof value === "string" && etagPattern.test(value) && Number.isSafeInteger(Number(value.slice(2, -1)));
}
function invalid(): never { throw new ReferenceEligibilityClientError("REFERENCE_ELIGIBILITY_INVALID"); }
function uncertain(): never { throw new ReferenceEligibilityClientError("REFERENCE_ELIGIBILITY_UNCERTAIN"); }

export class ReferenceEligibilityClient {
  constructor(private readonly session: SessionClient) {
    if (!(session instanceof SessionClient)) invalid();
  }

  async set(current: ReferenceCurrent | GlobalReferenceCurrent, target: EligibilityTarget,
    reason: string, operationKey: string): Promise<ReferenceEligibilityReceipt> {
    const scope = current?.scope, projectId = current?.project_id;
    const view = this.session.view;
    if (!current || !id(current.reference_solution_id) || !id(current.reference_version_id)
      || !etag(current.etag) || !["PROJECT", "GLOBAL"].includes(scope)
      || (scope === "PROJECT" ? !id(projectId) : projectId !== null)
      || !allowed[current.eligibility_state]?.includes(target)
      || typeof reason !== "string" || reason.length < 1 || reason.length > 2000
      || reason !== reason.trim() || reason !== reason.normalize("NFC") || /\p{Cc}/u.test(reason)
      || typeof operationKey !== "string" || !/^[\x20-\x7e]{16,128}$/.test(operationKey)
      || !view || view.password_change_required || !this.session.canSubmit
      || (scope === "GLOBAL" ? view.deployment_role !== "DEPLOYMENT_ADMIN"
        : !view.authorized_projects.some(item => item.project_id === projectId && item.role === "PROJECT_MANAGER"))) invalid();
    const body = JSON.stringify({ eligibility_state: target, reason });
    let response: Response;
    try {
      response = await this.session.postReferenceEligibility(scope, current.reference_solution_id,
        projectId, body, current.etag, operationKey);
    } catch (failure) {
      if (failure instanceof SessionClientError
        && (failure.code === "AUTH_RELOGIN_REQUIRED" || failure.code === "AUTH_CLIENT_BUSY")) {
        throw new ReferenceEligibilityClientError(failure.code);
      }
      return uncertain();
    }
    try {
      if (response.headers.get("content-type")?.split(";")[0].trim().toLowerCase() !== "application/json"
        || response.headers.get("cache-control") !== "no-store") uncertain();
      const payload: unknown = await response.json();
      if (!record(payload) || !id(payload.trace_id)
        || response.headers.get("x-trace-id") !== payload.trace_id) uncertain();
      if (response.status !== 200) {
        const code = record(payload.error) ? payload.error.code : null;
        const statuses: Readonly<Record<string, number>> = {
          AUTH_SESSION_EXPIRED: 401, AUTH_CSRF_INVALID: 403, LICENSE_OPERATION_DENIED: 403,
          RESOURCE_NOT_FOUND: 404, PROJECT_ARCHIVED: 409, VALIDATION_FAILED: 422,
          CONFLICT_VERSION: 409, CONFLICT_STATE: 409, CONFLICT_IDEMPOTENCY: 409,
          SYSTEM_UNAVAILABLE: 503,
        };
        if (typeof code === "string" && statuses[code] === response.status)
          throw new ReferenceEligibilityClientError(code as ReferenceEligibilityErrorCode);
        uncertain();
      }
      if (!exact(payload, ["data", "trace_id"]) || !record(payload.data)) uncertain();
      const value = payload.data;
      const next = Number(current.etag.slice(2, -1)) + 1;
      if (!exact(value, ["eligibility_event_id", "reference_solution_id", "reference_version_id",
        "scope", "project_id", "eligibility_state", "eligibility_reason", "etag"])
        || !id(value.eligibility_event_id) || value.reference_solution_id !== current.reference_solution_id
        || value.reference_version_id !== current.reference_version_id
        || value.scope !== scope || value.project_id !== projectId
        || value.eligibility_state !== target || value.eligibility_reason !== reason
        || !Number.isSafeInteger(next) || value.etag !== `"v${next}"`
        || response.headers.get("etag") !== value.etag) uncertain();
      return Object.freeze({ ...value }) as unknown as ReferenceEligibilityReceipt;
    } catch (failure) {
      if (failure instanceof ReferenceEligibilityClientError) throw failure;
      return uncertain();
    }
  }
}
