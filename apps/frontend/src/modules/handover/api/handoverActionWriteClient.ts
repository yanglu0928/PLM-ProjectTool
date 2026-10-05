import { SessionClient, SessionClientError } from "@/modules/auth/api/sessionClient";
import type { HandoverActionField, HandoverActionState } from "./handoverActionReadClient";

export type HandoverActionType = "PROVIDE_INFO" | "CONFIRM_DECISION" | "RESOLVE_CONFLICT" | "MITIGATE_RISK" | "DEFINE_SCOPE" | "OTHER";
export type HandoverActionPriority = "LOW" | "MEDIUM" | "HIGH" | "URGENT";
export interface HandoverActionDocumentRef { readonly document_id: string; readonly document_version_id: string; }
export interface CreateHandoverActionInput { readonly source_analysis_version_ref: string | null; readonly source_item_id: string | null;
  readonly human_source_reason: string | null; readonly action_type: HandoverActionType; readonly title: string;
  readonly requested_input_spec: Readonly<{ fields: readonly HandoverActionField[] }>; readonly owner_ref: string;
  readonly due_at: string; readonly priority: HandoverActionPriority; readonly created_reason: string; }
export interface PatchHandoverActionInput { readonly title?: string; readonly requested_input_spec?: Readonly<{ fields: readonly HandoverActionField[] }>;
  readonly owner_ref?: string; readonly due_at?: string; readonly priority?: HandoverActionPriority; }

export interface HandoverActionCreateResult extends CreateHandoverActionInput { readonly action_item_id: string; readonly project_id: string;
  readonly source_kind: "ANALYSIS_ITEM" | "HUMAN"; readonly created_by: string; readonly created_at: string;
  readonly initial_event_id: string; readonly action_state: "OPEN"; readonly etag: string; }
export interface HandoverActionPatchResult { readonly action_item_id: string; readonly project_id: string; readonly title: string;
  readonly requested_input_spec: Readonly<{ fields: readonly HandoverActionField[] }>; readonly owner_ref: string; readonly due_at: string;
  readonly priority: HandoverActionPriority; readonly action_state: "OPEN" | "IN_PROGRESS"; readonly updated_at: string; readonly etag: string; }
export interface HandoverActionStartResult { readonly action_item_id: string; readonly project_id: string; readonly action_state_event_id: string;
  readonly action_state: "IN_PROGRESS"; readonly occurred_at: string; readonly etag: string; }
export interface HandoverActionSubmitResult { readonly action_item_id: string; readonly project_id: string; readonly action_state_event_id: string;
  readonly action_state: "SUBMITTED"; readonly submitted_at: string; readonly response_documents: readonly HandoverActionDocumentRef[];
  readonly evidence_refs: readonly string[]; readonly etag: string; }
export interface HandoverActionVerifyResult { readonly action_item_id: string; readonly project_id: string; readonly action_state_event_id: string;
  readonly action_state: "VERIFIED"; readonly verified_by: string; readonly verified_at: string; readonly evidence_refs: readonly string[];
  readonly etag: string; }
export interface HandoverActionCloseResult { readonly action_item_id: string; readonly project_id: string; readonly action_state_event_id: string;
  readonly action_state: "CLOSED"; readonly resolution_trace_ref: string; readonly closed_at: string; readonly etag: string; }
export interface HandoverActionCancelResult { readonly action_item_id: string; readonly project_id: string; readonly action_state_event_id: string;
  readonly action_state: "CANCELLED"; readonly previous_state: Exclude<HandoverActionState, "CLOSED" | "CANCELLED">;
  readonly reason: string; readonly occurred_at: string; readonly etag: string; }
export interface HandoverActionFirstReceipt<T> { readonly first_result: Readonly<T>; readonly is_current_state_proof: false; }

const messages = {
  HANDOVER_ACTION_INVALID_INPUT: "待办输入、版本或操作号无效，请重新核对。",
  AUTH_RELOGIN_REQUIRED: "修改待办前请重新登录。", AUTH_CLIENT_BUSY: "正在处理会话操作，请稍候。",
  AUTH_SESSION_EXPIRED: "会话已失效，请重新登录。", AUTH_CSRF_INVALID: "登录状态已变化，请重新登录。",
  LICENSE_OPERATION_DENIED: "当前许可不允许修改交接待办。", RESOURCE_NOT_FOUND: "待办不存在，或当前账户无权操作。",
  PROJECT_ARCHIVED: "项目已归档，不能再修改待办。", CONFLICT_VERSION: "待办已被其他操作更新，请重新读取。",
  CONFLICT_IDEMPOTENCY: "原操作号与本次输入不一致，已停止提交。", HANDOVER_ACTION_STATE_INVALID: "当前待办状态不允许此操作。",
  HANDOVER_SOURCE_REQUIRED: "待办来源不完整或已不可用。", HANDOVER_ACTION_EVIDENCE_REQUIRED: "提交或验证所需证据不完整。",
  HANDOVER_ACTION_RESOLUTION_REQUIRED: "尚未形成可追溯的解决结果，不能关闭待办。",
  HANDOVER_ACTION_UNCERTAIN: "操作结果无法确认；请保留原操作号和版本，重新读取待办或核对操作记录。",
} as const;
export type HandoverActionWriteErrorCode = keyof typeof messages;
export class HandoverActionWriteError extends Error { readonly uncertain: boolean;
  constructor(readonly code: HandoverActionWriteErrorCode) { super(messages[code]); this.name = "HandoverActionWriteError";
    this.uncertain = code === "HANDOVER_ACTION_UNCERTAIN"; } }

const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const etagPattern = /^"v(0|[1-9][0-9]*)"$/; const keyPattern = /^[\x20-\x7e]{16,128}$/;
const actionTypes = new Set<HandoverActionType>(["PROVIDE_INFO", "CONFIRM_DECISION", "RESOLVE_CONFLICT", "MITIGATE_RISK", "DEFINE_SCOPE", "OTHER"]);
const priorities = new Set<HandoverActionPriority>(["LOW", "MEDIUM", "HIGH", "URGENT"]);
function record(value: unknown): value is Record<string, unknown> { return typeof value === "object" && value !== null && !Array.isArray(value); }
function exact(value: Record<string, unknown>, keys: readonly string[]) { return Object.keys(value).length === keys.length && keys.every(key => Object.hasOwn(value, key)); }
function id(value: unknown): value is string { return typeof value === "string" && uuid.test(value) && value !== "00000000-0000-0000-0000-000000000000"; }
function text(value: unknown, maximum: number): value is string { return typeof value === "string" && value.length >= 1 && value.length <= maximum
  && value.trim() === value && !/\p{C}/u.test(value); }
function instant(value: unknown): value is string { return typeof value === "string" && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})$/.test(value)
  && Number.isFinite(Date.parse(value)); }
function version(value: unknown): number | null { if (typeof value !== "string" || !etagPattern.test(value)) return null;
  const parsed = Number(value.slice(2, -1)); return Number.isSafeInteger(parsed) && parsed < Number.MAX_SAFE_INTEGER ? parsed : null; }
function fields(value: unknown): value is Readonly<{ fields: readonly HandoverActionField[] }> { if (!record(value) || !exact(value, ["fields"])
  || !Array.isArray(value.fields) || value.fields.length < 1 || value.fields.length > 32) return false;
  return value.fields.every(field => record(field) && exact(field, ["name", "format", "example", "required"])
    && text(field.name, 128) && text(field.format, 128) && text(field.example, 500) && typeof field.required === "boolean"); }
function same(left: unknown, right: unknown): boolean { return JSON.stringify(left) === JSON.stringify(right); }
function frozenFields(value: Readonly<{ fields: readonly HandoverActionField[] }>) { return Object.freeze({ fields: Object.freeze(value.fields.map(field => Object.freeze({ ...field }))) }); }
function validSource(input: CreateHandoverActionInput): boolean { const analysis = id(input.source_analysis_version_ref) && id(input.source_item_id) && input.human_source_reason === null;
  const human = input.source_analysis_version_ref === null && input.source_item_id === null && text(input.human_source_reason, 2000); return analysis || human; }
function validCreate(input: unknown): input is CreateHandoverActionInput { return record(input)
  && exact(input, ["source_analysis_version_ref", "source_item_id", "human_source_reason", "action_type", "title", "requested_input_spec", "owner_ref", "due_at", "priority", "created_reason"])
  && validSource(input as unknown as CreateHandoverActionInput) && actionTypes.has(input.action_type as HandoverActionType)
  && text(input.title, 255) && fields(input.requested_input_spec) && id(input.owner_ref) && instant(input.due_at)
  && priorities.has(input.priority as HandoverActionPriority) && text(input.created_reason, 2000); }
function validPatch(input: unknown): input is PatchHandoverActionInput { if (!record(input) || Object.keys(input).length < 1
  || !Object.keys(input).every(key => ["title", "requested_input_spec", "owner_ref", "due_at", "priority"].includes(key))) return false;
  return (!Object.hasOwn(input, "title") || text(input.title, 255)) && (!Object.hasOwn(input, "requested_input_spec") || fields(input.requested_input_spec))
    && (!Object.hasOwn(input, "owner_ref") || id(input.owner_ref)) && (!Object.hasOwn(input, "due_at") || instant(input.due_at))
    && (!Object.hasOwn(input, "priority") || priorities.has(input.priority as HandoverActionPriority)); }
function validIds(values: unknown, minimum: number, maximum: number): values is readonly string[] { return Array.isArray(values) && values.length >= minimum
  && values.length <= maximum && values.every(id) && new Set(values).size === values.length; }
function validDocuments(values: unknown): values is readonly HandoverActionDocumentRef[] { return Array.isArray(values) && values.length >= 1 && values.length <= 500
  && values.every(item => record(item) && exact(item, ["document_id", "document_version_id"]) && id(item.document_id) && id(item.document_version_id))
  && new Set(values.map(item => item.document_id)).size === values.length && new Set(values.map(item => item.document_version_id)).size === values.length; }

type Operation = "create" | "patch" | "start" | "submit" | "verify" | "close" | "cancel";
const resultKeys: Record<Operation, readonly string[]> = {
  create: ["action_item_id", "project_id", "source_kind", "source_analysis_version_ref", "source_item_id", "human_source_reason", "action_type", "title", "requested_input_spec", "owner_ref", "due_at", "priority", "created_by", "created_reason", "created_at", "initial_event_id", "action_state", "etag"],
  patch: ["action_item_id", "project_id", "title", "requested_input_spec", "owner_ref", "due_at", "priority", "action_state", "updated_at", "etag"],
  start: ["action_item_id", "project_id", "action_state_event_id", "action_state", "etag", "occurred_at"],
  submit: ["action_item_id", "project_id", "action_state_event_id", "action_state", "etag", "submitted_at", "response_documents", "evidence_refs"],
  verify: ["action_item_id", "project_id", "action_state_event_id", "action_state", "etag", "verified_by", "verified_at", "evidence_refs"],
  close: ["action_item_id", "project_id", "action_state_event_id", "action_state", "etag", "resolution_trace_ref", "closed_at"],
  cancel: ["action_item_id", "project_id", "action_state_event_id", "action_state", "etag", "previous_state", "reason", "occurred_at"],
};

export class HandoverActionWriteClient {
  constructor(private readonly session: SessionClient) { if (!(session instanceof SessionClient)) throw new HandoverActionWriteError("HANDOVER_ACTION_INVALID_INPUT"); }

  async create(projectId: string, input: CreateHandoverActionInput, key: string): Promise<HandoverActionFirstReceipt<HandoverActionCreateResult>> {
    if (!id(projectId) || !validCreate(input) || !keyPattern.test(key)) throw new HandoverActionWriteError("HANDOVER_ACTION_INVALID_INPUT");
    const response = await this.#transport(() => this.session.postProjectHandoverActionCreate(projectId, JSON.stringify(input), key));
    const result = await this.#result(response, "create", projectId, null, null);
    const path = `/api/v1/projects/${projectId}/handover-action-items/${String(result.action_item_id)}`;
    if (response.status !== 201 || response.headers.get("location") !== path || result.action_state !== "OPEN" || result.etag !== '"v0"'
      || result.source_kind !== (input.human_source_reason === null ? "ANALYSIS_ITEM" : "HUMAN")
      || !same(Object.fromEntries(Object.keys(input).map(key => [key, result[key]])), input)) throw new HandoverActionWriteError("HANDOVER_ACTION_UNCERTAIN");
    return this.#receipt({ ...result, requested_input_spec: frozenFields(result.requested_input_spec as Readonly<{ fields: readonly HandoverActionField[] }>) } as unknown as HandoverActionCreateResult);
  }

  async patch(projectId: string, actionId: string, priorEtag: string, input: PatchHandoverActionInput): Promise<HandoverActionFirstReceipt<HandoverActionPatchResult>> {
    if (!id(projectId) || !id(actionId) || version(priorEtag) === null || !validPatch(input)) throw new HandoverActionWriteError("HANDOVER_ACTION_INVALID_INPUT");
    const response = await this.#transport(() => this.session.patchProjectHandoverAction(projectId, actionId, priorEtag, JSON.stringify(input)));
    const result = await this.#result(response, "patch", projectId, actionId, priorEtag);
    if (!["OPEN", "IN_PROGRESS"].includes(String(result.action_state)) || Object.entries(input).some(([key, value]) => !same(result[key], value)))
      throw new HandoverActionWriteError("HANDOVER_ACTION_UNCERTAIN");
    return this.#receipt({ ...result, requested_input_spec: frozenFields(result.requested_input_spec as Readonly<{ fields: readonly HandoverActionField[] }>) } as unknown as HandoverActionPatchResult);
  }

  start(projectId: string, actionId: string, priorEtag: string, key: string, reason: string) {
    return this.#transition<HandoverActionStartResult>(projectId, actionId, priorEtag, key, "start", { reason }, result => result.action_state === "IN_PROGRESS" && instant(result.occurred_at));
  }
  submit(projectId: string, actionId: string, priorEtag: string, key: string, responseDocuments: readonly HandoverActionDocumentRef[], evidenceRefs: readonly string[], reason: string) {
    if (!validDocuments(responseDocuments) || !validIds(evidenceRefs, 1, 500)) return Promise.reject(new HandoverActionWriteError("HANDOVER_ACTION_INVALID_INPUT"));
    const body = { response_documents: responseDocuments, evidence_refs: evidenceRefs, reason };
    return this.#transition<HandoverActionSubmitResult>(projectId, actionId, priorEtag, key, "submit", body,
      result => result.action_state === "SUBMITTED" && instant(result.submitted_at) && validDocuments(result.response_documents)
        && validIds(result.evidence_refs, 1, 500) && same(result.response_documents, responseDocuments) && same(result.evidence_refs, evidenceRefs));
  }
  verify(projectId: string, actionId: string, priorEtag: string, key: string, evidenceRefs: readonly string[], reason: string) {
    if (!validIds(evidenceRefs, 1, 500)) return Promise.reject(new HandoverActionWriteError("HANDOVER_ACTION_INVALID_INPUT"));
    return this.#transition<HandoverActionVerifyResult>(projectId, actionId, priorEtag, key, "verify", { evidence_refs: evidenceRefs, reason },
      result => result.action_state === "VERIFIED" && id(result.verified_by) && instant(result.verified_at)
        && validIds(result.evidence_refs, 1, 500) && same(result.evidence_refs, evidenceRefs));
  }
  close(projectId: string, actionId: string, priorEtag: string, key: string, resolutionTraceRef: string, reason: string) {
    if (!id(resolutionTraceRef)) return Promise.reject(new HandoverActionWriteError("HANDOVER_ACTION_INVALID_INPUT"));
    return this.#transition<HandoverActionCloseResult>(projectId, actionId, priorEtag, key, "close", { resolution_trace_ref: resolutionTraceRef, reason },
      result => result.action_state === "CLOSED" && result.resolution_trace_ref === resolutionTraceRef && instant(result.closed_at));
  }
  cancel(projectId: string, actionId: string, priorEtag: string, key: string, reason: string) {
    return this.#transition<HandoverActionCancelResult>(projectId, actionId, priorEtag, key, "cancel", { reason }, result => result.action_state === "CANCELLED"
      && ["OPEN", "IN_PROGRESS", "SUBMITTED", "VERIFIED"].includes(String(result.previous_state)) && result.reason === reason && instant(result.occurred_at));
  }

  async #transition<T>(projectId: string, actionId: string, priorEtag: string, key: string, operation: Exclude<Operation, "create" | "patch">,
    body: Record<string, unknown>, validate: (result: Record<string, unknown>) => boolean): Promise<HandoverActionFirstReceipt<T>> {
    if (!id(projectId) || !id(actionId) || version(priorEtag) === null || !keyPattern.test(key) || !text(body.reason, 2000))
      throw new HandoverActionWriteError("HANDOVER_ACTION_INVALID_INPUT");
    const response = await this.#transport(() => this.session.postProjectHandoverActionTransition(projectId, actionId, operation, priorEtag, key, JSON.stringify(body)));
    const result = await this.#result(response, operation, projectId, actionId, priorEtag);
    if (!validate(result)) throw new HandoverActionWriteError("HANDOVER_ACTION_UNCERTAIN");
    const copy = { ...result } as Record<string, unknown>;
    if (Array.isArray(copy.response_documents)) copy.response_documents = Object.freeze(copy.response_documents.map(item => Object.freeze({ ...(item as object) })));
    if (Array.isArray(copy.evidence_refs)) copy.evidence_refs = Object.freeze([...copy.evidence_refs]);
    return this.#receipt(copy as T);
  }

  async #transport(action: () => Promise<Response>): Promise<Response> { try { return await action(); } catch (failure) {
    if (failure instanceof SessionClientError && ["AUTH_RELOGIN_REQUIRED", "AUTH_CLIENT_BUSY"].includes(failure.code))
      throw new HandoverActionWriteError(failure.code as "AUTH_RELOGIN_REQUIRED" | "AUTH_CLIENT_BUSY");
    throw new HandoverActionWriteError("HANDOVER_ACTION_UNCERTAIN"); } }

  async #result(response: Response, operation: Operation, projectId: string, actionId: string | null, priorEtag: string | null): Promise<Record<string, unknown>> {
    try { if (response.headers.get("content-type")?.split(";")[0].trim().toLowerCase() !== "application/json") throw new Error();
      const payload: unknown = await response.json(); if (!record(payload) || !id(payload.trace_id)) throw new Error();
      const expectedStatus = operation === "create" ? 201 : 200;
      if (response.status !== expectedStatus) { const code = record(payload.error) ? payload.error.code : null;
        const known: Record<string, number> = { AUTH_SESSION_EXPIRED: 401, AUTH_CSRF_INVALID: 403, LICENSE_OPERATION_DENIED: 403,
          RESOURCE_NOT_FOUND: 404, PROJECT_ARCHIVED: 409, CONFLICT_VERSION: 409, CONFLICT_IDEMPOTENCY: 409,
          HANDOVER_ACTION_STATE_INVALID: 409, HANDOVER_SOURCE_REQUIRED: 422, HANDOVER_ACTION_EVIDENCE_REQUIRED: 422,
          HANDOVER_ACTION_RESOLUTION_REQUIRED: 422, REQUEST_MALFORMED: 400, VALIDATION_FAILED: 422, CONFLICT_VERSION_REQUIRED: 428 };
        if (typeof code === "string" && known[code] === response.status) throw new HandoverActionWriteError(
          ["REQUEST_MALFORMED", "VALIDATION_FAILED", "CONFLICT_VERSION_REQUIRED"].includes(code) ? "HANDOVER_ACTION_INVALID_INPUT" : code as HandoverActionWriteErrorCode);
        throw new Error(); }
      if (!record(payload.data) || !exact(payload.data, resultKeys[operation]) || payload.data.project_id !== projectId
        || !id(payload.data.action_item_id) || actionId !== null && payload.data.action_item_id !== actionId
        || operation === "create" && !id(payload.data.initial_event_id)
        || !["create", "patch"].includes(operation) && !id(payload.data.action_state_event_id)
        || version(payload.data.etag) === null || response.headers.get("etag") !== payload.data.etag) throw new Error();
      if (priorEtag !== null && version(payload.data.etag) !== (version(priorEtag) as number) + 1) throw new Error();
      if (!id(payload.data.owner_ref ?? payload.data.action_item_id) || !instant(payload.data.created_at ?? payload.data.updated_at ?? payload.data.occurred_at
        ?? payload.data.submitted_at ?? payload.data.verified_at ?? payload.data.closed_at)) throw new Error();
      if (operation === "create" && (!fields(payload.data.requested_input_spec) || !id(payload.data.created_by))) throw new Error();
      if (operation === "patch" && (!fields(payload.data.requested_input_spec) || !id(payload.data.owner_ref) || !text(payload.data.title, 255)
        || !instant(payload.data.due_at) || !priorities.has(payload.data.priority as HandoverActionPriority))) throw new Error();
      return payload.data;
    } catch (failure) { if (failure instanceof HandoverActionWriteError) throw failure; throw new HandoverActionWriteError("HANDOVER_ACTION_UNCERTAIN"); }
  }

  #receipt<T>(result: T): HandoverActionFirstReceipt<T> { return Object.freeze({ first_result: Object.freeze(result), is_current_state_proof: false as const }); }
}
