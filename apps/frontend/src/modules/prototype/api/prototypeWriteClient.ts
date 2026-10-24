import { SessionClient, SessionClientError, type PrototypeWriteRoute } from "@/modules/auth/api/sessionClient";
import { parsePrototypeContract, parsePrototypeLink, parsePrototypeVersion,
  type PrototypeLinkView, type PrototypeVersionView } from "./prototypeReadClient";

export interface PrototypeArtifactInput { readonly artifact_kind: "DOCUMENT_VERSION" | "OUTPUT_ARTIFACT"; readonly target_id: string; }
export interface PrototypeTemplateContentInput {
  readonly layout_contract: Readonly<Record<string, unknown>>;
  readonly component_contract: Readonly<Record<string, unknown>>;
  readonly applicable_terminals: readonly string[]; readonly artifact_refs: readonly PrototypeArtifactInput[];
}
export interface PrototypeVersionCreateInput {
  readonly template_id: string; readonly template_version_id: string;
  readonly artifact_refs: readonly PrototypeArtifactInput[];
  readonly requirement_refs: readonly { readonly requirement_id: string; readonly requirement_version_id: string }[];
  readonly interaction_spec: Readonly<Record<string, unknown>>;
  readonly coverage_summary: Readonly<Record<string, unknown>>;
}
export interface PrototypeCoverageInput {
  readonly covered_acceptance_criterion_refs: readonly string[];
  readonly uncovered_acceptance_criteria: readonly { readonly acceptance_criterion_ref: string; readonly reason: string }[];
}
export interface PrototypeLinkInput {
  readonly requirement_id: string; readonly requirement_version_id: string;
  readonly prototype_id: string; readonly prototype_version_id: string;
  readonly purpose: "ILLUSTRATES" | "VALIDATES" | "ACCEPTANCE_REFERENCE";
  readonly coverage: PrototypeCoverageInput;
}
export interface PrototypeIdentityMutationView {
  readonly prototype_id: string; readonly project_id: string; readonly name: string;
  readonly state: "ACTIVE" | "ARCHIVED"; readonly current_approved_version_ref: string | null; readonly etag: string;
}
export interface PrototypePackageMutationView {
  readonly prototype_package_id: string; readonly project_id: string; readonly name: string;
  readonly state: "ACTIVE" | "ARCHIVED" | "RESTRICTED"; readonly prototype_ids: readonly string[]; readonly etag: string;
}
export interface PrototypeScopeDecisionView {
  readonly prototype_id: string; readonly project_id: string; readonly name: string; readonly state: "NOT_REQUIRED";
  readonly scope_decision_id: string; readonly reason: string; readonly impact: string; readonly confirmed_by: string;
  readonly review_id: string | null; readonly review_round_id: string | null;
  readonly affected_requirement_version_refs: readonly string[]; readonly decided_at: string; readonly etag: string;
}
export interface PrototypeVersionCreated extends PrototypeVersionView { readonly prototype_etag: string; }
export interface PrototypeValidationReport {
  readonly audit_event_id: string; readonly prototype_version_id: string;
  readonly state: PrototypeVersionView["state"]; readonly valid: boolean;
  readonly blocking_issues: readonly ("TEMPLATE_UNAVAILABLE" | "REQUIREMENT_UNAVAILABLE" | "ARTIFACT_UNAVAILABLE")[];
  readonly warnings: readonly string[]; readonly coverage_summary: Readonly<{ template_available: boolean;
    requirements_available: boolean; artifacts_available: boolean }>; readonly checked_at: string;
}
export interface PrototypeReviewSubmission {
  readonly review_id: string; readonly review_round_id: string; readonly subject_type: "PRT-03";
  readonly project_id: string; readonly prototype_id: string; readonly prototype_version_id: string;
  readonly policy_ref: "PROTOTYPE_ALL_V1"; readonly reviewer_ids: readonly string[];
  readonly state: "IN_REVIEW"; readonly round_no: number; readonly review_etag: string;
  readonly submitted_by: string; readonly submitted_at: string;
}
export interface PrototypeTemplateMutationView {
  readonly prototype_template_id: string; readonly prototype_template_version_id: string;
  readonly scope: "PROJECT" | "GLOBAL"; readonly project_id: string | null; readonly name: string;
  readonly state: "ACTIVE" | "ARCHIVED" | "RESTRICTED"; readonly version_no: number;
  readonly version_state: "PUBLISHED"; readonly layout_contract: Readonly<Record<string, unknown>>;
  readonly component_contract: Readonly<Record<string, unknown>>; readonly applicable_terminals: readonly string[];
  readonly artifact_refs: readonly PrototypeArtifactInput[]; readonly content_fingerprint: string;
  readonly etag: string; readonly created_at: string; readonly supersedes_version_id?: string;
}

const messages = {
  PROTOTYPE_WRITE_INVALID_INPUT: "原型输入不完整或格式无效。", AUTH_RELOGIN_REQUIRED: "写入原型前请重新登录。",
  AUTH_CLIENT_BUSY: "正在处理其他会话操作，请稍候。", AUTH_SESSION_EXPIRED: "会话已失效，请重新登录。",
  AUTH_CSRF_INVALID: "登录状态已变化，请重新登录。", LICENSE_OPERATION_DENIED: "当前许可不允许修改原型。",
  RESOURCE_NOT_FOUND: "原型资源不存在，或当前账户无权操作。", PROJECT_ARCHIVED: "项目已归档，不能修改原型。",
  CONFLICT_VERSION: "原型已被其他操作更新，请重新读取。", CONFLICT_IDEMPOTENCY: "原操作号与本次输入不一致，已停止提交。",
  CONFLICT_STATE: "当前原型状态不允许此操作。", CONFLICT_DUPLICATE: "存在重复的原型业务记录。",
  BUSINESS_REVIEW_NOT_ELIGIBLE: "原型版本尚未通过校验，不能送审。",
  REVIEW_REVIEWER_INELIGIBLE: "所选评审人不具备当前项目评审资格。",
  REVIEW_SUBJECT_LOCKED: "原型版本正在评审或已被锁定。",
  PROTOTYPE_WRITE_UNAVAILABLE: "暂时无法确认原型写入结果；请保留原操作参数并先重新读取。",
} as const;
export type PrototypeWriteErrorCode = keyof typeof messages;
export class PrototypeWriteError extends Error {
  readonly uncertain: boolean;
  constructor(readonly code: PrototypeWriteErrorCode) {
    super(messages[code]); this.name = "PrototypeWriteError"; this.uncertain = code === "PROTOTYPE_WRITE_UNAVAILABLE";
  }
}

const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const strongEtag = /^"v(0|[1-9][0-9]*)"$/; const digest = /^[0-9a-f]{64}$/;
const keyPattern = /^[\x20-\x7e]{16,128}$/; const terminal = /^[A-Z][A-Z0-9_]{0,63}$/;
function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
function exact(value: Record<string, unknown>, fields: readonly string[]): boolean {
  return Object.keys(value).length === fields.length && fields.every(field => Object.hasOwn(value, field));
}
function id(value: unknown): value is string {
  return typeof value === "string" && uuid.test(value) && value !== "00000000-0000-0000-0000-000000000000";
}
function optionalId(value: unknown): value is string | null { return value === null || id(value); }
function integer(value: unknown, minimum = 0): value is number {
  return typeof value === "number" && Number.isSafeInteger(value) && value >= minimum;
}
function instant(value: unknown): value is string {
  return typeof value === "string" && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$/.test(value)
    && Number.isFinite(Date.parse(value));
}
function text(value: unknown, maximum: number, multiline = false): value is string {
  const forbidden = multiline ? /[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]/ : /\p{C}/u;
  return typeof value === "string" && value.length >= 1 && value.length <= maximum && value.trim() === value
    && value.normalize("NFKC") === value && !forbidden.test(value);
}
function frozen<T extends object>(value: T): Readonly<T> { return Object.freeze(value); }
function ids(...values: string[]): void {
  if (values.some(value => !id(value))) throw new PrototypeWriteError("PROTOTYPE_WRITE_INVALID_INPUT");
}
function etag(value: string): void {
  if (!strongEtag.test(value) || Number(value.slice(2, -1)) >= Number.MAX_SAFE_INTEGER) {
    throw new PrototypeWriteError("PROTOTYPE_WRITE_INVALID_INPUT");
  }
}
function operationKey(value: string): void {
  if (!keyPattern.test(value)) throw new PrototypeWriteError("PROTOTYPE_WRITE_INVALID_INPUT");
}
function name(value: string): string {
  if (!text(value, 255)) throw new PrototypeWriteError("PROTOTYPE_WRITE_INVALID_INPUT"); return value;
}
function sortedIds(value: readonly string[], maximum: number, minimum = 0): readonly string[] {
  if (!Array.isArray(value) || value.length < minimum || value.length > maximum || !value.every(id)
    || value.some((item, index) => index > 0 && value[index - 1]! >= item)) {
    throw new PrototypeWriteError("PROTOTYPE_WRITE_INVALID_INPUT");
  }
  return Object.freeze([...value]);
}
function artifacts(value: readonly PrototypeArtifactInput[], minimum: number): readonly PrototypeArtifactInput[] {
  if (!Array.isArray(value) || value.length < minimum || value.length > 100) {
    throw new PrototypeWriteError("PROTOTYPE_WRITE_INVALID_INPUT");
  }
  const result = value.map(item => {
    if (!record(item) || !exact(item, ["artifact_kind", "target_id"])
      || !["DOCUMENT_VERSION", "OUTPUT_ARTIFACT"].includes(item.artifact_kind as string) || !id(item.target_id)) {
      throw new PrototypeWriteError("PROTOTYPE_WRITE_INVALID_INPUT");
    }
    return frozen({ artifact_kind: item.artifact_kind as PrototypeArtifactInput["artifact_kind"], target_id: item.target_id });
  });
  const positions = result.map(item => `${item.artifact_kind}:${item.target_id}`);
  if (positions.some((item, index) => index > 0 && positions[index - 1]! >= item)) {
    throw new PrototypeWriteError("PROTOTYPE_WRITE_INVALID_INPUT");
  }
  return Object.freeze(result);
}
function templateContent(value: PrototypeTemplateContentInput): PrototypeTemplateContentInput {
  if (!record(value) || !exact(value, ["layout_contract", "component_contract", "applicable_terminals", "artifact_refs"])
    || !Array.isArray(value.applicable_terminals) || value.applicable_terminals.length < 1
    || value.applicable_terminals.length > 16 || !value.applicable_terminals.every(item => typeof item === "string" && terminal.test(item))
    || value.applicable_terminals.some((item, index) => index > 0 && value.applicable_terminals[index - 1]! >= item)) {
    throw new PrototypeWriteError("PROTOTYPE_WRITE_INVALID_INPUT");
  }
  let layout: Readonly<Record<string, unknown>>, components: Readonly<Record<string, unknown>>;
  try { layout = parsePrototypeContract(value.layout_contract); components = parsePrototypeContract(value.component_contract); }
  catch { throw new PrototypeWriteError("PROTOTYPE_WRITE_INVALID_INPUT"); }
  return frozen({ layout_contract: layout, component_contract: components,
    applicable_terminals: Object.freeze([...value.applicable_terminals]), artifact_refs: artifacts(value.artifact_refs, 0) });
}
function linkInput(value: PrototypeLinkInput): PrototypeLinkInput {
  if (!record(value) || !exact(value, ["requirement_id", "requirement_version_id", "prototype_id", "prototype_version_id",
    "purpose", "coverage"]) || !id(value.requirement_id) || !id(value.requirement_version_id)
    || !id(value.prototype_id) || !id(value.prototype_version_id)
    || !["ILLUSTRATES", "VALIDATES", "ACCEPTANCE_REFERENCE"].includes(value.purpose as string)
    || !record(value.coverage) || !exact(value.coverage, ["covered_acceptance_criterion_refs", "uncovered_acceptance_criteria"])) {
    throw new PrototypeWriteError("PROTOTYPE_WRITE_INVALID_INPUT");
  }
  const covered = sortedIds(value.coverage.covered_acceptance_criterion_refs, 500, 1);
  if (!Array.isArray(value.coverage.uncovered_acceptance_criteria) || value.coverage.uncovered_acceptance_criteria.length > 499) {
    throw new PrototypeWriteError("PROTOTYPE_WRITE_INVALID_INPUT");
  }
  const gaps = value.coverage.uncovered_acceptance_criteria.map(item => {
    if (!record(item) || !exact(item, ["acceptance_criterion_ref", "reason"])
      || !id(item.acceptance_criterion_ref) || !text(item.reason, 1000, true)) {
      throw new PrototypeWriteError("PROTOTYPE_WRITE_INVALID_INPUT");
    }
    return frozen({ acceptance_criterion_ref: item.acceptance_criterion_ref, reason: item.reason });
  });
  if (gaps.some((item, index) => index > 0 && gaps[index - 1]!.acceptance_criterion_ref >= item.acceptance_criterion_ref)
    || new Set([...covered, ...gaps.map(item => item.acceptance_criterion_ref)]).size !== covered.length + gaps.length) {
    throw new PrototypeWriteError("PROTOTYPE_WRITE_INVALID_INPUT");
  }
  return frozen({ requirement_id: value.requirement_id, requirement_version_id: value.requirement_version_id,
    prototype_id: value.prototype_id, prototype_version_id: value.prototype_version_id,
    purpose: value.purpose, coverage: frozen({ covered_acceptance_criterion_refs: covered,
      uncovered_acceptance_criteria: Object.freeze(gaps) }) });
}
async function payload(response: Response): Promise<unknown> {
  if (response.headers.get("content-type")?.split(";", 1)[0].trim().toLowerCase() !== "application/json") {
    throw new PrototypeWriteError("PROTOTYPE_WRITE_UNAVAILABLE");
  }
  try { return await response.json() as unknown; }
  catch { throw new PrototypeWriteError("PROTOTYPE_WRITE_UNAVAILABLE"); }
}
function envelope(value: unknown): unknown {
  if (!record(value) || !exact(value, ["data", "trace_id"]) || !id(value.trace_id)) {
    throw new PrototypeWriteError("PROTOTYPE_WRITE_UNAVAILABLE");
  }
  return value.data;
}
function failure(status: number, value: unknown): never {
  const raw = record(value) && record(value.error) && typeof value.error.code === "string" ? value.error.code : "";
  if ((status === 400 || status === 422) && raw === "VALIDATION_FAILED") {
    throw new PrototypeWriteError("PROTOTYPE_WRITE_INVALID_INPUT");
  }
  const expected: Readonly<Record<string, readonly [number, PrototypeWriteErrorCode]>> = {
    AUTH_SESSION_EXPIRED: [401, "AUTH_SESSION_EXPIRED"], AUTH_CSRF_INVALID: [403, "AUTH_CSRF_INVALID"],
    LICENSE_OPERATION_DENIED: [403, "LICENSE_OPERATION_DENIED"], RESOURCE_NOT_FOUND: [404, "RESOURCE_NOT_FOUND"],
    PROJECT_ARCHIVED: [409, "PROJECT_ARCHIVED"], CONFLICT_VERSION: [409, "CONFLICT_VERSION"],
    CONFLICT_IDEMPOTENCY: [409, "CONFLICT_IDEMPOTENCY"], CONFLICT_STATE: [409, "CONFLICT_STATE"],
    CONFLICT_DUPLICATE: [409, "CONFLICT_DUPLICATE"], BUSINESS_REVIEW_NOT_ELIGIBLE: [409, "BUSINESS_REVIEW_NOT_ELIGIBLE"],
    REVIEW_REVIEWER_INELIGIBLE: [409, "REVIEW_REVIEWER_INELIGIBLE"], REVIEW_SUBJECT_LOCKED: [409, "REVIEW_SUBJECT_LOCKED"],
  };
  const match = expected[raw];
  throw new PrototypeWriteError(match !== undefined && match[0] === status ? match[1] : "PROTOTYPE_WRITE_UNAVAILABLE");
}

function responseEtag(response: Response, value: unknown): string {
  if (typeof value !== "string" || !strongEtag.test(value) || response.headers.get("etag") !== value) {
    throw new PrototypeWriteError("PROTOTYPE_WRITE_UNAVAILABLE");
  }
  return value;
}
function parsePackageMutation(value: unknown, project: string, packageId: string, response: Response): PrototypePackageMutationView {
  const fields = ["prototype_package_id", "project_id", "name", "state", "prototype_ids", "etag"] as const;
  if (!record(value) || !exact(value, fields) || value.prototype_package_id !== packageId || value.project_id !== project
    || !text(value.name, 255) || !["ACTIVE", "ARCHIVED", "RESTRICTED"].includes(value.state as string)
    || !Array.isArray(value.prototype_ids)) throw new PrototypeWriteError("PROTOTYPE_WRITE_UNAVAILABLE");
  const members = sortedIds(value.prototype_ids as string[], 200);
  responseEtag(response, value.etag);
  return frozen({ prototype_package_id: packageId, project_id: project, name: value.name,
    state: value.state as PrototypePackageMutationView["state"], prototype_ids: members, etag: value.etag as string });
}
function parsePrototypeMutation(value: unknown, project: string, prototypeId: string, expectedState: "ACTIVE" | "ARCHIVED",
                                response: Response): PrototypeIdentityMutationView {
  const fields = ["prototype_id", "project_id", "name", "state", "current_approved_version_ref", "etag"] as const;
  if (!record(value) || !exact(value, fields) || value.prototype_id !== prototypeId || value.project_id !== project
    || !text(value.name, 255) || value.state !== expectedState || !optionalId(value.current_approved_version_ref)) {
    throw new PrototypeWriteError("PROTOTYPE_WRITE_UNAVAILABLE");
  }
  responseEtag(response, value.etag);
  return frozen({ prototype_id: prototypeId, project_id: project, name: value.name, state: expectedState,
    current_approved_version_ref: value.current_approved_version_ref, etag: value.etag as string });
}
function parseDecision(value: unknown, project: string, prototypeId: string, response: Response): PrototypeScopeDecisionView {
  const fields = ["prototype_id", "project_id", "name", "state", "scope_decision_id", "reason", "impact", "confirmed_by",
    "review_id", "review_round_id", "affected_requirement_version_refs", "decided_at", "etag"] as const;
  if (!record(value) || !exact(value, fields) || value.prototype_id !== prototypeId || value.project_id !== project
    || !text(value.name, 255) || value.state !== "NOT_REQUIRED" || !id(value.scope_decision_id)
    || !text(value.reason, 2000) || !text(value.impact, 2000) || !id(value.confirmed_by)
    || !optionalId(value.review_id) || !optionalId(value.review_round_id) || (value.review_id === null) !== (value.review_round_id === null)
    || !Array.isArray(value.affected_requirement_version_refs) || !instant(value.decided_at)) {
    throw new PrototypeWriteError("PROTOTYPE_WRITE_UNAVAILABLE");
  }
  const affected = sortedIds(value.affected_requirement_version_refs as string[], 200, 1); responseEtag(response, value.etag);
  return frozen({ prototype_id: prototypeId, project_id: project, name: value.name, state: "NOT_REQUIRED",
    scope_decision_id: value.scope_decision_id, reason: value.reason, impact: value.impact, confirmed_by: value.confirmed_by,
    review_id: value.review_id, review_round_id: value.review_round_id, affected_requirement_version_refs: affected,
    decided_at: value.decided_at, etag: value.etag as string });
}
function parseValidation(value: unknown, versionId: string): PrototypeValidationReport {
  const fields = ["audit_event_id", "prototype_version_id", "state", "valid", "blocking_issues", "warnings",
    "coverage_summary", "checked_at"] as const;
  const order = ["TEMPLATE_UNAVAILABLE", "REQUIREMENT_UNAVAILABLE", "ARTIFACT_UNAVAILABLE"] as const;
  if (!record(value) || !exact(value, fields) || !id(value.audit_event_id) || value.prototype_version_id !== versionId
    || !["DRAFT", "IN_REVIEW", "APPROVED", "RETURNED", "SUPERSEDED", "RESTRICTED"].includes(value.state as string)
    || typeof value.valid !== "boolean" || !Array.isArray(value.blocking_issues)
    || !value.blocking_issues.every(item => order.includes(item as typeof order[number])) || !Array.isArray(value.warnings)
    || value.warnings.length !== 0 || !record(value.coverage_summary)
    || !exact(value.coverage_summary, ["template_available", "requirements_available", "artifacts_available"])
    || Object.values(value.coverage_summary).some(item => typeof item !== "boolean") || !instant(value.checked_at)) {
    throw new PrototypeWriteError("PROTOTYPE_WRITE_UNAVAILABLE");
  }
  const issues = value.blocking_issues as typeof order[number][];
  const expected = order.filter(item => issues.includes(item));
  if (issues.some((item, index) => item !== expected[index]) || value.valid !== (issues.length === 0)
    || value.coverage_summary.template_available !== !issues.includes("TEMPLATE_UNAVAILABLE")
    || value.coverage_summary.requirements_available !== !issues.includes("REQUIREMENT_UNAVAILABLE")
    || value.coverage_summary.artifacts_available !== !issues.includes("ARTIFACT_UNAVAILABLE")) {
    throw new PrototypeWriteError("PROTOTYPE_WRITE_UNAVAILABLE");
  }
  return frozen({ audit_event_id: value.audit_event_id, prototype_version_id: versionId,
    state: value.state as PrototypeValidationReport["state"], valid: value.valid,
    blocking_issues: Object.freeze([...issues]), warnings: Object.freeze([]), coverage_summary: frozen({
      template_available: value.coverage_summary.template_available as boolean,
      requirements_available: value.coverage_summary.requirements_available as boolean,
      artifacts_available: value.coverage_summary.artifacts_available as boolean,
    }), checked_at: value.checked_at });
}

export class PrototypeWriteClient {
  constructor(private readonly session: SessionClient) {
    if (!(session instanceof SessionClient)) throw new PrototypeWriteError("PROTOTYPE_WRITE_INVALID_INPUT");
  }
  async #send(route: PrototypeWriteRoute, body: object | null, currentEtag: string | null, key: string | null,
              expectedStatus: 200 | 201): Promise<{ response: Response; data: unknown }> {
    if (currentEtag !== null) etag(currentEtag); if (key !== null) operationKey(key);
    let response: Response;
    try { response = await this.session.writePrototype(route, body === null ? null : JSON.stringify(body), currentEtag, key); }
    catch (error) {
      if (error instanceof SessionClientError && (error.code === "AUTH_RELOGIN_REQUIRED" || error.code === "AUTH_CLIENT_BUSY")) {
        throw new PrototypeWriteError(error.code);
      }
      throw new PrototypeWriteError("PROTOTYPE_WRITE_UNAVAILABLE");
    }
    const raw = await payload(response); if (!response.ok) failure(response.status, raw);
    if (response.status !== expectedStatus) throw new PrototypeWriteError("PROTOTYPE_WRITE_UNAVAILABLE");
    return { response, data: envelope(raw) };
  }
  async createPackage(project: string, packageName: string, key: string): Promise<PrototypePackageMutationView> {
    ids(project); operationKey(key); const { response, data } = await this.#send({ operation: "package-create", projectId: project },
      { name: name(packageName) }, null, key, 201);
    const fields = ["prototype_package_id", "project_id", "name", "state", "created_at", "etag"] as const;
    if (!record(data) || !exact(data, fields) || !id(data.prototype_package_id) || data.project_id !== project
      || !text(data.name, 255) || data.state !== "ACTIVE" || !instant(data.created_at) || response.headers.get("location")
      !== `/api/v1/projects/${project}/prototype-packages/${data.prototype_package_id}`) throw new PrototypeWriteError("PROTOTYPE_WRITE_UNAVAILABLE");
    const expanded = { prototype_package_id: data.prototype_package_id, project_id: project, name: data.name,
      state: data.state, prototype_ids: [], etag: data.etag };
    return parsePackageMutation(expanded, project, data.prototype_package_id, response);
  }
  async patchPackage(project: string, packageId: string, currentEtag: string, packageName: string): Promise<PrototypePackageMutationView> {
    ids(project, packageId); const { response, data } = await this.#send({ operation: "package-patch", projectId: project, packageId },
      { name: name(packageName) }, currentEtag, null, 200); return parsePackageMutation(data, project, packageId, response);
  }
  async setPackageMembers(project: string, packageId: string, currentEtag: string, prototypeIds: readonly string[], key: string): Promise<PrototypePackageMutationView> {
    ids(project, packageId); const members = sortedIds(prototypeIds, 200); const { response, data } = await this.#send(
      { operation: "package-set-members", projectId: project, packageId }, { prototype_ids: members }, currentEtag, key, 200);
    return parsePackageMutation(data, project, packageId, response);
  }
  async createPrototype(project: string, prototypeName: string, key: string): Promise<PrototypeIdentityMutationView> {
    ids(project); const { response, data } = await this.#send({ operation: "prototype-create", projectId: project },
      { name: name(prototypeName) }, null, key, 201);
    const fields = ["prototype_id", "project_id", "name", "state", "current_approved_version_ref", "created_at", "etag"] as const;
    if (!record(data) || !exact(data, fields) || !id(data.prototype_id) || data.project_id !== project
      || !text(data.name, 255) || data.state !== "ACTIVE" || data.current_approved_version_ref !== null
      || !instant(data.created_at) || response.headers.get("location")
      !== `/api/v1/projects/${project}/prototypes/${data.prototype_id}`) throw new PrototypeWriteError("PROTOTYPE_WRITE_UNAVAILABLE");
    return parsePrototypeMutation({ prototype_id: data.prototype_id, project_id: project, name: data.name,
      state: data.state, current_approved_version_ref: null, etag: data.etag }, project, data.prototype_id, "ACTIVE", response);
  }
  async patchPrototype(project: string, prototypeId: string, currentEtag: string, prototypeName: string): Promise<PrototypeIdentityMutationView> {
    ids(project, prototypeId); const { response, data } = await this.#send({ operation: "prototype-patch", projectId: project, prototypeId },
      { name: name(prototypeName) }, currentEtag, null, 200); return parsePrototypeMutation(data, project, prototypeId, "ACTIVE", response);
  }
  async markNotRequired(project: string, prototypeId: string, currentEtag: string,
    input: { readonly affected_requirement_version_refs: readonly string[]; readonly reason: string; readonly impact: string;
      readonly review_id: string | null; readonly review_round_id: string | null }, key: string): Promise<PrototypeScopeDecisionView> {
    ids(project, prototypeId);
    if (!record(input) || !exact(input, ["affected_requirement_version_refs", "reason", "impact", "review_id", "review_round_id"])
      || !text(input.reason, 2000) || !text(input.impact, 2000) || !optionalId(input.review_id)
      || !optionalId(input.review_round_id) || (input.review_id === null) !== (input.review_round_id === null)) {
      throw new PrototypeWriteError("PROTOTYPE_WRITE_INVALID_INPUT");
    }
    const body = { affected_requirement_version_refs: sortedIds(input.affected_requirement_version_refs, 200, 1),
      reason: input.reason, impact: input.impact, ...(input.review_id === null ? {} : {
        review_id: input.review_id, review_round_id: input.review_round_id,
      }) };
    const { response, data } = await this.#send({ operation: "prototype-mark-not-required", projectId: project, prototypeId },
      body, currentEtag, key, 200); return parseDecision(data, project, prototypeId, response);
  }
  async archivePrototype(project: string, prototypeId: string, currentEtag: string, key: string): Promise<PrototypeIdentityMutationView> {
    ids(project, prototypeId); const { response, data } = await this.#send(
      { operation: "prototype-archive", projectId: project, prototypeId }, null, currentEtag, key, 200);
    return parsePrototypeMutation(data, project, prototypeId, "ARCHIVED", response);
  }
  async createVersion(project: string, prototypeId: string, currentEtag: string,
                      input: PrototypeVersionCreateInput, key: string): Promise<PrototypeVersionCreated> {
    ids(project, prototypeId);
    if (!record(input) || !exact(input, ["template_id", "template_version_id", "artifact_refs", "requirement_refs",
      "interaction_spec", "coverage_summary"]) || !id(input.template_id) || !id(input.template_version_id)
      || !Array.isArray(input.requirement_refs) || input.requirement_refs.length < 1 || input.requirement_refs.length > 200) {
      throw new PrototypeWriteError("PROTOTYPE_WRITE_INVALID_INPUT");
    }
    const requirements = input.requirement_refs.map(item => {
      if (!record(item) || !exact(item, ["requirement_id", "requirement_version_id"])
        || !id(item.requirement_id) || !id(item.requirement_version_id)) throw new PrototypeWriteError("PROTOTYPE_WRITE_INVALID_INPUT");
      return frozen({ requirement_id: item.requirement_id, requirement_version_id: item.requirement_version_id });
    });
    if (requirements.some((item, index) => index > 0 && requirements[index - 1]!.requirement_version_id >= item.requirement_version_id)) {
      throw new PrototypeWriteError("PROTOTYPE_WRITE_INVALID_INPUT");
    }
    let interaction: Readonly<Record<string, unknown>>, coverage: Readonly<Record<string, unknown>>;
    try { interaction = parsePrototypeContract(input.interaction_spec); coverage = parsePrototypeContract(input.coverage_summary); }
    catch { throw new PrototypeWriteError("PROTOTYPE_WRITE_INVALID_INPUT"); }
    const body = { template_id: input.template_id, template_version_id: input.template_version_id,
      artifact_refs: artifacts(input.artifact_refs, 1), requirement_refs: Object.freeze(requirements),
      interaction_spec: interaction, coverage_summary: coverage };
    const { response, data } = await this.#send({ operation: "version-create", projectId: project, prototypeId },
      body, currentEtag, key, 201);
    if (!record(data) || !id(data.prototype_version_id) || typeof data.prototype_etag !== "string") {
      throw new PrototypeWriteError("PROTOTYPE_WRITE_UNAVAILABLE");
    }
    responseEtag(response, data.prototype_etag);
    if (response.headers.get("location") !== `/api/v1/projects/${project}/prototypes/${prototypeId}/versions/${data.prototype_version_id}`) {
      throw new PrototypeWriteError("PROTOTYPE_WRITE_UNAVAILABLE");
    }
    const { prototype_etag: prototypeEtag, ...rawView } = data;
    let view: PrototypeVersionView;
    try { view = parsePrototypeVersion(rawView, project, prototypeId, data.prototype_version_id); }
    catch { throw new PrototypeWriteError("PROTOTYPE_WRITE_UNAVAILABLE"); }
    return frozen({ ...view, prototype_etag: prototypeEtag });
  }
  async validateVersion(project: string, prototypeId: string, versionId: string, key: string): Promise<PrototypeValidationReport> {
    ids(project, prototypeId, versionId); const { data } = await this.#send(
      { operation: "version-validate", projectId: project, prototypeId, versionId }, null, null, key, 200);
    return parseValidation(data, versionId);
  }
  async submitVersionReview(project: string, prototypeId: string, versionId: string,
                            reviewers: readonly string[], key: string): Promise<PrototypeReviewSubmission> {
    ids(project, prototypeId, versionId); const reviewerIds = sortedIds(reviewers, 32, 1);
    const { response, data } = await this.#send({ operation: "version-submit-review", projectId: project, prototypeId, versionId },
      { reviewer_ids: reviewerIds, policy_ref: "PROTOTYPE_ALL_V1", due_at: null, submission_note: null }, null, key, 201);
    const fields = ["review_id", "review_round_id", "subject_type", "project_id", "prototype_id", "prototype_version_id",
      "policy_ref", "reviewer_ids", "state", "round_no", "review_etag", "submitted_by", "submitted_at"] as const;
    if (!record(data) || !exact(data, fields) || !id(data.review_id) || !id(data.review_round_id) || data.subject_type !== "PRT-03"
      || data.project_id !== project || data.prototype_id !== prototypeId || data.prototype_version_id !== versionId
      || data.policy_ref !== "PROTOTYPE_ALL_V1" || !Array.isArray(data.reviewer_ids)
      || data.reviewer_ids.some((item, index) => item !== reviewerIds[index]) || data.reviewer_ids.length !== reviewerIds.length
      || data.state !== "IN_REVIEW" || !integer(data.round_no, 1) || !id(data.submitted_by) || !instant(data.submitted_at)) {
      throw new PrototypeWriteError("PROTOTYPE_WRITE_UNAVAILABLE");
    }
    responseEtag(response, data.review_etag);
    return frozen({ ...data, reviewer_ids: Object.freeze([...reviewerIds]) }) as unknown as PrototypeReviewSubmission;
  }
  async #template(route: PrototypeWriteRoute, scope: "PROJECT" | "GLOBAL", project: string | null, templateName: string | null,
                  content: PrototypeTemplateContentInput, currentEtag: string | null, key: string, expectedStatus: 201): Promise<PrototypeTemplateMutationView> {
    const body = { ...(templateName === null ? {} : { name: name(templateName) }), ...templateContent(content) };
    const { response, data } = await this.#send(route, body, currentEtag, key, expectedStatus);
    const base = ["prototype_template_id", "prototype_template_version_id", "scope", "project_id", "name", "state",
      "version_no", "version_state", "layout_contract", "component_contract", "applicable_terminals", "artifact_refs",
      "content_fingerprint", "etag", "created_at"] as const;
    const fields = currentEtag === null ? base : [...base, "supersedes_version_id"];
    if (!record(data) || !exact(data, fields) || !id(data.prototype_template_id) || !id(data.prototype_template_version_id)
      || data.scope !== scope || data.project_id !== project || !text(data.name, 255)
      || !["ACTIVE", "ARCHIVED", "RESTRICTED"].includes(data.state as string) || !integer(data.version_no, 1)
      || data.version_state !== "PUBLISHED" || typeof data.content_fingerprint !== "string" || !digest.test(data.content_fingerprint)
      || !instant(data.created_at) || currentEtag !== null && !id(data.supersedes_version_id)) {
      throw new PrototypeWriteError("PROTOTYPE_WRITE_UNAVAILABLE");
    }
    let normalized: PrototypeTemplateContentInput;
    try { normalized = templateContent({ layout_contract: data.layout_contract as Record<string, unknown>,
      component_contract: data.component_contract as Record<string, unknown>,
      applicable_terminals: data.applicable_terminals as string[], artifact_refs: data.artifact_refs as PrototypeArtifactInput[] }); }
    catch { throw new PrototypeWriteError("PROTOTYPE_WRITE_UNAVAILABLE"); }
    responseEtag(response, data.etag);
    return frozen({ prototype_template_id: data.prototype_template_id, prototype_template_version_id: data.prototype_template_version_id,
      scope, project_id: project, name: data.name, state: data.state as PrototypeTemplateMutationView["state"],
      version_no: data.version_no, version_state: "PUBLISHED", ...normalized, content_fingerprint: data.content_fingerprint,
      etag: data.etag as string, created_at: data.created_at,
      ...(currentEtag === null ? {} : { supersedes_version_id: data.supersedes_version_id as string }) });
  }
  async createProjectTemplate(project: string, templateName: string, content: PrototypeTemplateContentInput, key: string) {
    ids(project); return await this.#template({ operation: "template-project-create", projectId: project }, "PROJECT", project,
      templateName, content, null, key, 201);
  }
  async createGlobalTemplate(templateName: string, content: PrototypeTemplateContentInput, key: string) {
    return await this.#template({ operation: "template-global-create" }, "GLOBAL", null, templateName, content, null, key, 201);
  }
  async reviseProjectTemplate(project: string, templateId: string, currentEtag: string,
                              content: PrototypeTemplateContentInput, key: string) {
    ids(project, templateId); return await this.#template({ operation: "template-project-revise", projectId: project, templateId },
      "PROJECT", project, null, content, currentEtag, key, 201);
  }
  async reviseGlobalTemplate(templateId: string, currentEtag: string, content: PrototypeTemplateContentInput, key: string) {
    ids(templateId); return await this.#template({ operation: "template-global-revise", templateId },
      "GLOBAL", null, null, content, currentEtag, key, 201);
  }
  async createLink(project: string, input: PrototypeLinkInput, key: string): Promise<PrototypeLinkView> {
    ids(project); const normalized = linkInput(input); const { response, data } = await this.#send(
      { operation: "link-create", projectId: project }, normalized, null, key, 201);
    let view: PrototypeLinkView;
    try { view = parsePrototypeLink(data, project); } catch { throw new PrototypeWriteError("PROTOTYPE_WRITE_UNAVAILABLE"); }
    responseEtag(response, view.etag); return view;
  }
  async revokeLink(project: string, linkId: string, key: string): Promise<PrototypeLinkView> {
    ids(project, linkId); const { response, data } = await this.#send(
      { operation: "link-revoke", projectId: project, linkId }, null, null, key, 200);
    let view: PrototypeLinkView;
    try { view = parsePrototypeLink(data, project); } catch { throw new PrototypeWriteError("PROTOTYPE_WRITE_UNAVAILABLE"); }
    if (view.requirement_prototype_link_id !== linkId || view.state !== "REVOKED") {
      throw new PrototypeWriteError("PROTOTYPE_WRITE_UNAVAILABLE");
    }
    responseEtag(response, view.etag); return view;
  }
  async supersedeLink(project: string, linkId: string, input: PrototypeLinkInput, key: string): Promise<PrototypeLinkView> {
    ids(project, linkId); const normalized = linkInput(input); const { response, data } = await this.#send(
      { operation: "link-supersede", projectId: project, linkId }, normalized, null, key, 201);
    let view: PrototypeLinkView;
    try { view = parsePrototypeLink(data, project); } catch { throw new PrototypeWriteError("PROTOTYPE_WRITE_UNAVAILABLE"); }
    if (view.requirement_prototype_link_id === linkId || view.state !== "ACTIVE") {
      throw new PrototypeWriteError("PROTOTYPE_WRITE_UNAVAILABLE");
    }
    responseEtag(response, view.etag); return view;
  }
}
