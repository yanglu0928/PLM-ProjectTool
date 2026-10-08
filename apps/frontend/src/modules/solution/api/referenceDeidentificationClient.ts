/** GLOBAL Reference deidentification is a human attestation, never an AI approval. */
import { SessionClient, SessionClientError } from "@/modules/auth/api/sessionClient";

export interface DeidentificationSources {
  readonly document_version_ids: readonly string[];
  readonly evidence_ids: readonly string[];
  readonly source_project_class: string;
  readonly deidentification_class: string;
  readonly applicability: Readonly<Record<string, unknown>>;
}
export interface DeidentificationPreview {
  readonly source_fingerprint: string;
  readonly document_refs: readonly Readonly<{ document_id: string; document_version_id: string }>[];
  readonly evidence_ids: readonly string[];
  readonly previewed_at: string;
}
export interface DeidentificationConfirmation {
  readonly confirmation_id: string; readonly source_fingerprint: string;
  readonly confirmed_by: string; readonly confirmed_at: string;
  readonly expires_at: string; readonly trace_id: string;
}
export interface DeidentificationRevocation {
  readonly confirmation_id: string; readonly revoked_at: string; readonly trace_id: string;
}
export type DeidentificationOperationStatus =
  | Readonly<{ status: "UNCONFIRMED" }>
  | Readonly<{ status: "COMPLETED"; confirmation_id: string;
      first_status_code: 200 | 201;
      current_state: "CONFIRMED" | "REVOKED" | "EXPIRED" | "SUPERSEDED" }>;

const messages = {
  DEIDENTIFICATION_INVALID: "来源或确认内容无效，请重新填写。",
  DEIDENTIFICATION_UNCERTAIN: "提交结果暂无法确定；保留原操作号，核查审计后再处理。",
  AUTH_RELOGIN_REQUIRED: "请重新登录。",
  AUTH_CLIENT_BUSY: "账户操作进行中，请稍候。",
  AUTH_SESSION_EXPIRED: "登录已失效，请重新登录。",
  AUTH_CSRF_INVALID: "登录状态已变化，请重新登录。",
  LICENSE_OPERATION_DENIED: "当前许可不允许执行此操作。",
  RESOURCE_NOT_FOUND: "来源不存在或无权访问。",
  SOURCE_SNAPSHOT_CHANGED: "来源在预览后发生变化，请重新预览并逐项核查。",
  CONFLICT_IDEMPOTENCY: "操作号已用于不同内容，请核对历史，不要换号重试。",
  CONFLICT_STATE: "当前确认状态不允许撤回。",
} as const;
export type DeidentificationErrorCode = keyof typeof messages;
export class ReferenceDeidentificationError extends Error {
  constructor(readonly code: DeidentificationErrorCode) {
    super(messages[code]); this.name = "ReferenceDeidentificationError";
  }
}

const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const hash = /^[0-9a-f]{64}$/;
const stamp = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$/;
function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
function exact(value: Record<string, unknown>, fields: readonly string[]): boolean {
  return Object.keys(value).length === fields.length && fields.every(field => Object.hasOwn(value, field));
}
function id(value: unknown): value is string {
  return typeof value === "string" && uuid.test(value) && value !== "00000000-0000-0000-0000-000000000000";
}
function instant(value: unknown): value is string {
  return typeof value === "string" && stamp.test(value) && Number.isFinite(Date.parse(value))
    && new Date(value).toISOString().slice(0, 19) === value.slice(0, 19);
}
function invalid(): never { throw new ReferenceDeidentificationError("DEIDENTIFICATION_INVALID"); }
function uncertain(): never { throw new ReferenceDeidentificationError("DEIDENTIFICATION_UNCERTAIN"); }
function validSources(value: DeidentificationSources): boolean {
  if (!record(value) || !exact(value, ["document_version_ids", "evidence_ids",
    "source_project_class", "deidentification_class", "applicability"])
    || !Array.isArray(value.document_version_ids) || value.document_version_ids.length < 1
    || value.document_version_ids.length > 100 || !value.document_version_ids.every(id)
    || new Set(value.document_version_ids).size !== value.document_version_ids.length
    || !Array.isArray(value.evidence_ids) || value.evidence_ids.length > 500
    || !value.evidence_ids.every(id) || new Set(value.evidence_ids).size !== value.evidence_ids.length
    || !record(value.applicability)) return false;
  return [value.source_project_class, value.deidentification_class].every(item =>
    typeof item === "string" && item.length > 0 && item.length <= 128 && item.trim() === item);
}
function previewData(value: unknown, source: DeidentificationSources): DeidentificationPreview {
  if (!record(value) || !exact(value, ["source_fingerprint", "document_refs", "evidence_ids", "previewed_at"])
    || typeof value.source_fingerprint !== "string" || !hash.test(value.source_fingerprint)
    || !instant(value.previewed_at) || !Array.isArray(value.document_refs)
    || value.document_refs.length !== source.document_version_ids.length
    || !value.document_refs.every((item, index) => record(item)
      && exact(item, ["document_id", "document_version_id"])
      && id(item.document_id) && item.document_version_id === source.document_version_ids[index])
    || !Array.isArray(value.evidence_ids)
    || value.evidence_ids.length !== source.evidence_ids.length
    || value.evidence_ids.some((item, index) => item !== source.evidence_ids[index])) uncertain();
  return Object.freeze({
    source_fingerprint: value.source_fingerprint as string,
    document_refs: Object.freeze((value.document_refs as { document_id: string; document_version_id: string }[])
      .map(item => Object.freeze({ document_id: item.document_id,
        document_version_id: item.document_version_id }))),
    evidence_ids: Object.freeze([...(value.evidence_ids as string[])]),
    previewed_at: value.previewed_at as string,
  });
}
function confirmationData(value: unknown, fingerprint: string,
  expiry: string): DeidentificationConfirmation {
  if (!record(value) || !exact(value, ["confirmation_id", "source_fingerprint", "confirmed_by",
    "confirmed_at", "expires_at", "trace_id"])
    || !id(value.confirmation_id) || value.source_fingerprint !== fingerprint
    || !id(value.confirmed_by) || !instant(value.confirmed_at)
    || value.expires_at !== expiry || !instant(value.expires_at)
    || !id(value.trace_id)) uncertain();
  return Object.freeze(value) as unknown as DeidentificationConfirmation;
}
function revocationData(value: unknown, target: string): DeidentificationRevocation {
  if (!record(value) || !exact(value, ["confirmation_id", "revoked_at", "trace_id"])
    || value.confirmation_id !== target || !instant(value.revoked_at)
    || !id(value.trace_id)) uncertain();
  return Object.freeze(value) as unknown as DeidentificationRevocation;
}

export class ReferenceDeidentificationClient {
  constructor(private readonly session: SessionClient) {
    if (!(session instanceof SessionClient)) invalid();
  }
  async preview(source: DeidentificationSources): Promise<DeidentificationPreview> {
    if (!validSources(source)) invalid();
    const body = this.body(source);
    const response = await this.transport(() => this.session.postGlobalReferenceDeidentificationPreview(body));
    return previewData(await this.read(response, 200), source);
  }
  async confirm(source: DeidentificationSources, fingerprint: string,
    expiry: string, key: string): Promise<DeidentificationConfirmation> {
    if (!validSources(source) || !hash.test(fingerprint) || !instant(expiry)
      || Date.parse(expiry) <= Date.now() || Date.parse(expiry) > Date.now() + 30 * 86_400_000) invalid();
    const body = this.body({ ...source, expected_source_fingerprint: fingerprint,
      attestation_statement: "I_VERIFIED_DEIDENTIFICATION", expires_at: expiry });
    const response = await this.transport(() =>
      this.session.postGlobalReferenceDeidentificationConfirm(body, key));
    return confirmationData(await this.read(response, 201), fingerprint, expiry);
  }
  async revoke(target: string, reason: "SOURCE_EXPOSED" | "SCOPE_CHANGED" | "ADMIN_REVIEW",
    key: string): Promise<DeidentificationRevocation> {
    if (!id(target) || !["SOURCE_EXPOSED", "SCOPE_CHANGED", "ADMIN_REVIEW"].includes(reason)) invalid();
    const response = await this.transport(() =>
      this.session.postGlobalReferenceDeidentificationRevoke(target, JSON.stringify({ reason_code: reason }), key));
    return revocationData(await this.read(response, 200), target);
  }
  async lookup(kind: "CONFIRM" | "REVOKE", key: string): Promise<DeidentificationOperationStatus> {
    if (!["CONFIRM", "REVOKE"].includes(kind) || typeof key !== "string"
      || !/^[\x20-\x7e]{16,128}$/.test(key)) invalid();
    const response = await this.transport(() =>
      this.session.postGlobalReferenceDeidentificationOperationLookup(
        JSON.stringify({ operation_kind: kind, operation_key: key })));
    const data = await this.read(response, 200);
    if (!record(data)) uncertain();
    if (data.status === "UNCONFIRMED" && exact(data, ["status"])) {
      return Object.freeze({ status: "UNCONFIRMED" });
    }
    if (data.status !== "COMPLETED" || !exact(data, ["status", "confirmation_id",
      "first_status_code", "current_state"]) || !id(data.confirmation_id)
      || data.first_status_code !== (kind === "CONFIRM" ? 201 : 200)
      || !["CONFIRMED", "REVOKED", "EXPIRED", "SUPERSEDED"].includes(String(data.current_state))) uncertain();
    return Object.freeze({ status: "COMPLETED", confirmation_id: data.confirmation_id as string,
      first_status_code: data.first_status_code as 200 | 201,
      current_state: data.current_state as "CONFIRMED" | "REVOKED" | "EXPIRED" | "SUPERSEDED" });
  }
  private body(value: object): string {
    try {
      const body = JSON.stringify(value);
      if (new TextEncoder().encode(body).length > 128 * 1024) invalid();
      return body;
    } catch { return invalid(); }
  }
  private async transport(action: () => Promise<Response>): Promise<Response> {
    if (!this.session.view || this.session.view.password_change_required
      || this.session.view.deployment_role !== "DEPLOYMENT_ADMIN") invalid();
    try { return await action(); }
    catch (failure) {
      if (failure instanceof SessionClientError
        && ["AUTH_RELOGIN_REQUIRED", "AUTH_CLIENT_BUSY"].includes(failure.code)) {
        throw new ReferenceDeidentificationError(failure.code as DeidentificationErrorCode);
      }
      return uncertain();
    }
  }
  private async read(response: Response, expected: number): Promise<unknown> {
    try {
      if (response.headers.get("content-type")?.split(";")[0].trim().toLowerCase() !== "application/json") uncertain();
      const payload: unknown = await response.json();
      if (!record(payload) || !id(payload.trace_id)) uncertain();
      if (response.status !== expected) {
        const code = record(payload.error) ? payload.error.code : null;
        const statuses: Readonly<Record<string, number>> = {
          AUTH_SESSION_EXPIRED: 401, AUTH_CSRF_INVALID: 403, LICENSE_OPERATION_DENIED: 403,
          RESOURCE_NOT_FOUND: 404, SOURCE_SNAPSHOT_CHANGED: 409,
          CONFLICT_IDEMPOTENCY: 409, CONFLICT_STATE: 409,
        };
        if (typeof code === "string" && statuses[code] === response.status) {
          throw new ReferenceDeidentificationError(code as DeidentificationErrorCode);
        }
        uncertain();
      }
      if (!exact(payload, ["data", "trace_id"])) uncertain();
      return payload.data;
    } catch (failure) {
      if (failure instanceof ReferenceDeidentificationError) throw failure;
      return uncertain();
    }
  }
}
