export type PrototypePackageCursor = string & { readonly __family: "prototype-packages" };
export type PrototypeCursor = string & { readonly __family: "prototypes" };
export type PrototypeTemplateCursor = string & { readonly __family: "prototype-templates" };
export type PrototypeVersionCursor = string & { readonly __family: "prototype-versions" };
export type PrototypeLinkCursor = string & { readonly __family: "prototype-links" };

export interface PrototypePage<T, C extends string> {
  readonly items: readonly T[]; readonly next_cursor: C | null; readonly has_more: boolean;
}
export interface PrototypePackageView {
  readonly prototype_package_id: string; readonly project_id: string; readonly name: string;
  readonly state: "ACTIVE" | "ARCHIVED" | "RESTRICTED"; readonly created_by: string;
  readonly created_at: string; readonly updated_by: string | null; readonly updated_at: string;
  readonly etag: string; readonly prototype_ids?: readonly string[];
}
export interface PrototypeView {
  readonly prototype_id: string; readonly project_id: string; readonly name: string;
  readonly state: "ACTIVE" | "NOT_REQUIRED" | "ARCHIVED";
  readonly current_approved_version_ref: string | null; readonly created_by: string;
  readonly created_at: string; readonly updated_by: string | null; readonly updated_at: string;
  readonly etag: string;
}
export interface PrototypeArtifactRef {
  readonly artifact_kind: "DOCUMENT_VERSION" | "OUTPUT_ARTIFACT";
  readonly target_id: string; readonly document_id: string | null;
}
export interface PrototypeTemplateView {
  readonly prototype_template_id: string; readonly prototype_template_version_id: string;
  readonly scope: "PROJECT" | "GLOBAL"; readonly project_id: string | null;
  readonly name: string; readonly state: "ACTIVE" | "ARCHIVED" | "RESTRICTED";
  readonly version_no: number; readonly version_state: "PUBLISHED";
  readonly layout_contract: Readonly<Record<string, unknown>>;
  readonly component_contract: Readonly<Record<string, unknown>>;
  readonly applicable_terminals: readonly string[]; readonly artifact_refs: readonly PrototypeArtifactRef[];
  readonly content_fingerprint: string; readonly etag: string; readonly supersedes_version_id: string | null;
  readonly is_current: boolean; readonly updated_at: string; readonly created_at: string;
}
export interface PrototypeRequirementRef {
  readonly requirement_id: string; readonly requirement_version_id: string;
}
export interface PrototypeVersionView {
  readonly prototype_version_id: string; readonly prototype_id: string; readonly project_id: string;
  readonly version_no: number;
  readonly state: "DRAFT" | "IN_REVIEW" | "APPROVED" | "RETURNED" | "SUPERSEDED" | "RESTRICTED";
  readonly supersedes_version_id: string | null; readonly template_id: string; readonly template_version_id: string;
  readonly artifact_refs: readonly PrototypeArtifactRef[]; readonly requirement_refs: readonly PrototypeRequirementRef[];
  readonly interaction_spec: Readonly<Record<string, unknown>>;
  readonly coverage_summary: Readonly<Record<string, unknown>>;
  readonly content_fingerprint: string; readonly created_at: string;
}
export interface PrototypeCoverageGap { readonly acceptance_criterion_ref: string; readonly reason: string; }
export interface PrototypeLinkView {
  readonly requirement_prototype_link_id: string; readonly project_id: string;
  readonly requirement_id: string; readonly requirement_version_id: string;
  readonly prototype_id: string; readonly prototype_version_id: string;
  readonly purpose: "ILLUSTRATES" | "VALIDATES" | "ACCEPTANCE_REFERENCE";
  readonly coverage: { readonly covered_acceptance_criterion_refs: readonly string[];
    readonly uncovered_acceptance_criteria: readonly PrototypeCoverageGap[] };
  readonly state: "ACTIVE" | "REVOKED" | "SUPERSEDED"; readonly created_by: string;
  readonly created_at: string; readonly superseded_by_ref: string | null; readonly etag: string;
}

const messages = {
  PROTOTYPE_READ_INVALID_INPUT: "项目、原型或翻页参数无效。",
  AUTH_SESSION_EXPIRED: "会话已失效，请重新登录。",
  LICENSE_OPERATION_DENIED: "当前许可不允许读取原型。",
  RESOURCE_NOT_FOUND: "资源不存在，或当前账户无权查看。",
  PROJECT_ARCHIVED: "项目已归档，当前原型不可读取。",
  PROTOTYPE_READ_UNAVAILABLE: "暂时无法读取原型，请稍后重试。",
} as const;
export type PrototypeReadErrorCode = keyof typeof messages;
export class PrototypeReadError extends Error {
  constructor(readonly code: PrototypeReadErrorCode) { super(messages[code]); this.name = "PrototypeReadError"; }
}

const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const opaqueCursor = /^[A-Za-z0-9_-]{1,1024}\.[A-Za-z0-9_-]{43}$/;
const etag = /^"v(0|[1-9][0-9]*)"$/; const digest = /^[0-9a-f]{64}$/;
const terminal = /^[A-Z][A-Z0-9_]{0,63}$/; const key = /^[A-Za-z][A-Za-z0-9_.-]{0,63}$/;
const forbiddenKeys = new Set(["script", "scripts", "command", "commands", "exec", "execute", "executable",
  "code", "url", "uri", "href", "src", "event_handler"]);
const eventHandler = /^on(?:abort|animationend|animationiteration|animationstart|beforeinput|blur|change|click|contextmenu|dblclick|drag|dragend|dragenter|dragleave|dragover|dragstart|drop|error|focus|input|keydown|keypress|keyup|load|mousedown|mouseenter|mouseleave|mousemove|mouseout|mouseover|mouseup|pointerdown|pointerenter|pointerleave|pointermove|pointerout|pointerover|pointerup|reset|resize|scroll|submit|touchcancel|touchend|touchmove|touchstart|transitionend|wheel)$/i;
const forbiddenText = ["javascript:", "data:text/html", "<script", "cmd.exe", "powershell", "file://"];
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
function integer(value: unknown, minimum = 0, maximum = Number.MAX_SAFE_INTEGER): value is number {
  return typeof value === "number" && Number.isSafeInteger(value) && value >= minimum && value <= maximum;
}
function instant(value: unknown): value is string {
  return typeof value === "string" && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$/.test(value)
    && Number.isFinite(Date.parse(value));
}
function normalizedText(value: unknown, maximum: number): value is string {
  return typeof value === "string" && value.length >= 1 && value.length <= maximum && value.trim() === value
    && value.normalize("NFKC") === value && !/\p{C}/u.test(value);
}
function normalizedReason(value: unknown): value is string {
  return typeof value === "string" && value.length >= 1 && value.length <= 1000 && value.trim() === value
    && value.normalize("NFKC") === value && !/[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]/.test(value);
}
function frozen<T extends object>(value: T): Readonly<T> { return Object.freeze(value); }
function strictlyIncreasing(values: readonly string[]): boolean {
  return values.every((value, index) => index === 0 || values[index - 1]! < value);
}
function strictlyDecreasing(values: readonly string[]): boolean {
  return values.every((value, index) => index === 0 || values[index - 1]! > value);
}

function safeJsonObject(value: unknown): Readonly<Record<string, unknown>> {
  if (!record(value)) throw new PrototypeReadError("PROTOTYPE_READ_UNAVAILABLE");
  let nodes = 0;
  const visit = (item: unknown, depth: number): unknown => {
    nodes += 1;
    if (depth > 8 || nodes > 2000) throw new PrototypeReadError("PROTOTYPE_READ_UNAVAILABLE");
    if (item === null || typeof item === "boolean") return item;
    if (typeof item === "number") {
      if (!Number.isFinite(item) || Number.isInteger(item) && !Number.isSafeInteger(item)) {
        throw new PrototypeReadError("PROTOTYPE_READ_UNAVAILABLE");
      }
      return item;
    }
    if (typeof item === "string") {
      const folded = item.toLocaleLowerCase("en-US");
      if (item.length > 4096 || /\p{C}/u.test(item) || forbiddenText.some(marker => folded.includes(marker))) {
        throw new PrototypeReadError("PROTOTYPE_READ_UNAVAILABLE");
      }
      return item;
    }
    if (Array.isArray(item)) {
      if (item.length > 500) throw new PrototypeReadError("PROTOTYPE_READ_UNAVAILABLE");
      return Object.freeze(item.map(child => visit(child, depth + 1)));
    }
    if (record(item)) {
      const entries = Object.entries(item);
      if (entries.length > 500 || entries.some(([name]) => !key.test(name)
        || forbiddenKeys.has(name.toLocaleLowerCase("en-US")) || eventHandler.test(name))) {
        throw new PrototypeReadError("PROTOTYPE_READ_UNAVAILABLE");
      }
      return frozen(Object.fromEntries(entries.map(([name, child]) => [name, visit(child, depth + 1)])));
    }
    throw new PrototypeReadError("PROTOTYPE_READ_UNAVAILABLE");
  };
  if (new TextEncoder().encode(JSON.stringify(value)).length > 65_536) {
    throw new PrototypeReadError("PROTOTYPE_READ_UNAVAILABLE");
  }
  return visit(value, 0) as Readonly<Record<string, unknown>>;
}

export function parsePrototypeContract(value: unknown): Readonly<Record<string, unknown>> {
  return safeJsonObject(value);
}

function parseArtifact(value: unknown): PrototypeArtifactRef {
  const legacy = ["artifact_kind", "target_id"] as const;
  const projected = ["artifact_kind", "target_id", "document_id"] as const;
  if (!record(value) || !(exact(value, legacy) || exact(value, projected))
    || (value.artifact_kind !== "DOCUMENT_VERSION" && value.artifact_kind !== "OUTPUT_ARTIFACT") || !id(value.target_id)
    || Object.hasOwn(value, "document_id") && (value.artifact_kind !== "DOCUMENT_VERSION" || !id(value.document_id))) {
    throw new PrototypeReadError("PROTOTYPE_READ_UNAVAILABLE");
  }
  return frozen({ artifact_kind: value.artifact_kind, target_id: value.target_id,
    document_id: Object.hasOwn(value, "document_id") ? value.document_id as string : null });
}
function parseArtifacts(value: unknown, minimum: number): readonly PrototypeArtifactRef[] {
  if (!Array.isArray(value) || value.length < minimum || value.length > 100) {
    throw new PrototypeReadError("PROTOTYPE_READ_UNAVAILABLE");
  }
  const result = value.map(parseArtifact);
  const positions = result.map(item => `${item.artifact_kind}:${item.target_id}`);
  if (!strictlyIncreasing(positions)) throw new PrototypeReadError("PROTOTYPE_READ_UNAVAILABLE");
  return Object.freeze(result);
}

const rootFields = ["created_by", "created_at", "updated_by", "updated_at", "etag"] as const;
function parseRoot(value: Record<string, unknown>): void {
  if (!id(value.created_by) || !instant(value.created_at) || !optionalId(value.updated_by)
    || !instant(value.updated_at) || Date.parse(value.updated_at) < Date.parse(value.created_at)
    || typeof value.etag !== "string" || !etag.test(value.etag)) {
    throw new PrototypeReadError("PROTOTYPE_READ_UNAVAILABLE");
  }
}
const packageFields = ["prototype_package_id", "project_id", "name", "state", ...rootFields] as const;
export function parsePrototypePackage(value: unknown, projectId: string, packageId?: string,
                                      detail = false): PrototypePackageView {
  const fields = detail ? [...packageFields, "prototype_ids"] : packageFields;
  if (!record(value) || !exact(value, fields) || !id(value.prototype_package_id)
    || packageId !== undefined && value.prototype_package_id !== packageId || value.project_id !== projectId
    || !normalizedText(value.name, 255) || !new Set(["ACTIVE", "ARCHIVED", "RESTRICTED"]).has(value.state as string)) {
    throw new PrototypeReadError("PROTOTYPE_READ_UNAVAILABLE");
  }
  parseRoot(value);
  let members: readonly string[] | undefined;
  if (detail) {
    if (!Array.isArray(value.prototype_ids) || value.prototype_ids.length > 200
      || !value.prototype_ids.every(id) || !strictlyIncreasing(value.prototype_ids as string[])) {
      throw new PrototypeReadError("PROTOTYPE_READ_UNAVAILABLE");
    }
    members = Object.freeze([...(value.prototype_ids as string[])]);
  }
  return frozen({ prototype_package_id: value.prototype_package_id, project_id: projectId, name: value.name,
    state: value.state as PrototypePackageView["state"], created_by: value.created_by as string,
    created_at: value.created_at as string, updated_by: value.updated_by as string | null,
    updated_at: value.updated_at as string, etag: value.etag as string, ...(members ? { prototype_ids: members } : {}) });
}

const prototypeFields = ["prototype_id", "project_id", "name", "state", "current_approved_version_ref", ...rootFields] as const;
export function parsePrototype(value: unknown, projectId: string, prototypeId?: string): PrototypeView {
  if (!record(value) || !exact(value, prototypeFields) || !id(value.prototype_id)
    || prototypeId !== undefined && value.prototype_id !== prototypeId || value.project_id !== projectId
    || !normalizedText(value.name, 255) || !new Set(["ACTIVE", "NOT_REQUIRED", "ARCHIVED"]).has(value.state as string)
    || !optionalId(value.current_approved_version_ref)) throw new PrototypeReadError("PROTOTYPE_READ_UNAVAILABLE");
  parseRoot(value);
  return frozen({ prototype_id: value.prototype_id, project_id: projectId, name: value.name,
    state: value.state as PrototypeView["state"], current_approved_version_ref: value.current_approved_version_ref,
    created_by: value.created_by as string, created_at: value.created_at as string,
    updated_by: value.updated_by as string | null, updated_at: value.updated_at as string, etag: value.etag as string });
}

const templateFields = ["prototype_template_id", "prototype_template_version_id", "scope", "project_id", "name",
  "state", "version_no", "version_state", "layout_contract", "component_contract", "applicable_terminals",
  "artifact_refs", "content_fingerprint", "etag", "supersedes_version_id", "is_current", "updated_at", "created_at"] as const;
export function parsePrototypeTemplate(value: unknown, scope: "PROJECT" | "GLOBAL", projectId: string | null): PrototypeTemplateView {
  if (!record(value) || !exact(value, templateFields) || !id(value.prototype_template_id)
    || !id(value.prototype_template_version_id) || value.scope !== scope || value.project_id !== projectId
    || !normalizedText(value.name, 255) || !new Set(["ACTIVE", "ARCHIVED", "RESTRICTED"]).has(value.state as string)
    || !integer(value.version_no, 1) || value.version_state !== "PUBLISHED" || !optionalId(value.supersedes_version_id)
    || (value.version_no === 1) !== (value.supersedes_version_id === null) || typeof value.is_current !== "boolean"
    || !instant(value.updated_at) || !instant(value.created_at) || typeof value.etag !== "string" || !etag.test(value.etag)
    || typeof value.content_fingerprint !== "string" || !digest.test(value.content_fingerprint)
    || !Array.isArray(value.applicable_terminals) || value.applicable_terminals.length < 1
    || value.applicable_terminals.length > 16 || !value.applicable_terminals.every(item => typeof item === "string" && terminal.test(item))
    || !strictlyIncreasing(value.applicable_terminals as string[])) throw new PrototypeReadError("PROTOTYPE_READ_UNAVAILABLE");
  const layout = safeJsonObject(value.layout_contract), components = safeJsonObject(value.component_contract);
  const artifacts = parseArtifacts(value.artifact_refs, 0);
  return frozen({ prototype_template_id: value.prototype_template_id,
    prototype_template_version_id: value.prototype_template_version_id, scope, project_id: projectId,
    name: value.name, state: value.state as PrototypeTemplateView["state"], version_no: value.version_no,
    version_state: "PUBLISHED", layout_contract: layout, component_contract: components,
    applicable_terminals: Object.freeze([...(value.applicable_terminals as string[])]), artifact_refs: artifacts,
    content_fingerprint: value.content_fingerprint, etag: value.etag, supersedes_version_id: value.supersedes_version_id,
    is_current: value.is_current, updated_at: value.updated_at, created_at: value.created_at });
}

function parseProjectVisibleTemplate(value: unknown, projectId: string): PrototypeTemplateView {
  if (!record(value) || (value.scope !== "PROJECT" && value.scope !== "GLOBAL")) {
    throw new PrototypeReadError("PROTOTYPE_READ_UNAVAILABLE");
  }
  return value.scope === "PROJECT"
    ? parsePrototypeTemplate(value, "PROJECT", projectId)
    : parsePrototypeTemplate(value, "GLOBAL", null);
}

const versionFields = ["prototype_version_id", "prototype_id", "project_id", "version_no", "state",
  "supersedes_version_id", "template_id", "template_version_id", "artifact_refs", "requirement_refs",
  "interaction_spec", "coverage_summary", "content_fingerprint", "created_at"] as const;
export function parsePrototypeVersion(value: unknown, projectId: string, prototypeId: string,
                                      versionId?: string): PrototypeVersionView {
  if (!record(value) || !exact(value, versionFields) || !id(value.prototype_version_id)
    || versionId !== undefined && value.prototype_version_id !== versionId || value.prototype_id !== prototypeId
    || value.project_id !== projectId || !integer(value.version_no, 1)
    || !new Set(["DRAFT", "IN_REVIEW", "APPROVED", "RETURNED", "SUPERSEDED", "RESTRICTED"]).has(value.state as string)
    || !optionalId(value.supersedes_version_id) || (value.version_no === 1) !== (value.supersedes_version_id === null)
    || !id(value.template_id) || !id(value.template_version_id) || !instant(value.created_at)
    || typeof value.content_fingerprint !== "string" || !digest.test(value.content_fingerprint)
    || !Array.isArray(value.requirement_refs) || value.requirement_refs.length < 1 || value.requirement_refs.length > 200) {
    throw new PrototypeReadError("PROTOTYPE_READ_UNAVAILABLE");
  }
  const artifacts = parseArtifacts(value.artifact_refs, 1);
  const requirements = value.requirement_refs.map(item => {
    if (!record(item) || !exact(item, ["requirement_id", "requirement_version_id"])
      || !id(item.requirement_id) || !id(item.requirement_version_id)) throw new PrototypeReadError("PROTOTYPE_READ_UNAVAILABLE");
    return frozen({ requirement_id: item.requirement_id, requirement_version_id: item.requirement_version_id });
  });
  if (!strictlyIncreasing(requirements.map(item => item.requirement_version_id))) {
    throw new PrototypeReadError("PROTOTYPE_READ_UNAVAILABLE");
  }
  return frozen({ prototype_version_id: value.prototype_version_id, prototype_id: prototypeId, project_id: projectId,
    version_no: value.version_no, state: value.state as PrototypeVersionView["state"],
    supersedes_version_id: value.supersedes_version_id, template_id: value.template_id,
    template_version_id: value.template_version_id, artifact_refs: artifacts, requirement_refs: Object.freeze(requirements),
    interaction_spec: safeJsonObject(value.interaction_spec), coverage_summary: safeJsonObject(value.coverage_summary),
    content_fingerprint: value.content_fingerprint, created_at: value.created_at });
}

const linkFields = ["requirement_prototype_link_id", "project_id", "requirement_id", "requirement_version_id",
  "prototype_id", "prototype_version_id", "purpose", "coverage", "state", "created_by", "created_at",
  "superseded_by_ref", "etag"] as const;
export function parsePrototypeLink(value: unknown, projectId: string): PrototypeLinkView {
  if (!record(value) || !exact(value, linkFields) || !id(value.requirement_prototype_link_id)
    || value.project_id !== projectId || !id(value.requirement_id) || !id(value.requirement_version_id)
    || !id(value.prototype_id) || !id(value.prototype_version_id)
    || !new Set(["ILLUSTRATES", "VALIDATES", "ACCEPTANCE_REFERENCE"]).has(value.purpose as string)
    || !new Set(["ACTIVE", "REVOKED", "SUPERSEDED"]).has(value.state as string) || !id(value.created_by)
    || !instant(value.created_at) || !optionalId(value.superseded_by_ref) || typeof value.etag !== "string" || !etag.test(value.etag)
    || value.state === "ACTIVE" && (value.etag !== '"v0"' || value.superseded_by_ref !== null)
    || value.state === "REVOKED" && (value.etag !== '"v1"' || value.superseded_by_ref !== null)
    || value.state === "SUPERSEDED" && (value.etag !== '"v1"' || !id(value.superseded_by_ref))
    || !record(value.coverage) || !exact(value.coverage, ["covered_acceptance_criterion_refs", "uncovered_acceptance_criteria"])) {
    throw new PrototypeReadError("PROTOTYPE_READ_UNAVAILABLE");
  }
  const covered = value.coverage.covered_acceptance_criterion_refs;
  const gaps = value.coverage.uncovered_acceptance_criteria;
  if (!Array.isArray(covered) || covered.length < 1 || covered.length > 500 || !covered.every(id)
    || !strictlyIncreasing(covered as string[]) || !Array.isArray(gaps) || gaps.length > 499) {
    throw new PrototypeReadError("PROTOTYPE_READ_UNAVAILABLE");
  }
  const parsedGaps = gaps.map(item => {
    if (!record(item) || !exact(item, ["acceptance_criterion_ref", "reason"])
      || !id(item.acceptance_criterion_ref) || !normalizedReason(item.reason)) {
      throw new PrototypeReadError("PROTOTYPE_READ_UNAVAILABLE");
    }
    return frozen({ acceptance_criterion_ref: item.acceptance_criterion_ref, reason: item.reason });
  });
  if (!strictlyIncreasing(parsedGaps.map(item => item.acceptance_criterion_ref))
    || new Set([...(covered as string[]), ...parsedGaps.map(item => item.acceptance_criterion_ref)]).size
      !== covered.length + parsedGaps.length) throw new PrototypeReadError("PROTOTYPE_READ_UNAVAILABLE");
  return frozen({ requirement_prototype_link_id: value.requirement_prototype_link_id, project_id: projectId,
    requirement_id: value.requirement_id, requirement_version_id: value.requirement_version_id,
    prototype_id: value.prototype_id, prototype_version_id: value.prototype_version_id,
    purpose: value.purpose as PrototypeLinkView["purpose"], coverage: frozen({
      covered_acceptance_criterion_refs: Object.freeze([...(covered as string[])]),
      uncovered_acceptance_criteria: Object.freeze(parsedGaps),
    }), state: value.state as PrototypeLinkView["state"], created_by: value.created_by, created_at: value.created_at,
    superseded_by_ref: value.superseded_by_ref, etag: value.etag });
}

type PageOrder<T> = (previous: T, current: T) => boolean;
class PrototypeReadTransport {
  constructor(private readonly fetcher: typeof fetch, private readonly timeoutMs: number) {
    if (!integer(timeoutMs, 1, 30_000)) throw new PrototypeReadError("PROTOTYPE_READ_INVALID_INPUT");
  }
  ids(...values: string[]): void {
    if (values.some(value => !id(value))) throw new PrototypeReadError("PROTOTYPE_READ_INVALID_INPUT");
  }
  listInput(values: string[], pageSize: number, next: string | null, maximum = 200): void {
    this.ids(...values);
    if (!integer(pageSize, 1, maximum) || next !== null && (typeof next !== "string" || !opaqueCursor.test(next))) {
      throw new PrototypeReadError("PROTOTYPE_READ_INVALID_INPUT");
    }
  }
  query(pageSize: number, next: string | null): string {
    const query = new URLSearchParams({ page_size: String(pageSize) });
    if (next !== null) query.set("cursor", next); return `?${query}`;
  }
  async page<T, C extends string>(path: string, size: number, previousCursor: string | null,
                                  parse: (value: unknown) => T, identity: (value: T) => string,
                                  order: PageOrder<T>): Promise<PrototypePage<T, C>> {
    const data = await this.get(path);
    if (!record(data) || !exact(data, ["items", "next_cursor", "has_more"]) || !Array.isArray(data.items)
      || data.items.length > size || typeof data.has_more !== "boolean"
      || data.has_more && (data.items.length === 0 || typeof data.next_cursor !== "string"
        || !opaqueCursor.test(data.next_cursor) || data.next_cursor === previousCursor)
      || !data.has_more && data.next_cursor !== null) throw new PrototypeReadError("PROTOTYPE_READ_UNAVAILABLE");
    const items = data.items.map(parse);
    if (new Set(items.map(identity)).size !== items.length
      || items.some((item, index) => index > 0 && !order(items[index - 1]!, item))) {
      throw new PrototypeReadError("PROTOTYPE_READ_UNAVAILABLE");
    }
    return frozen({ items: Object.freeze(items), next_cursor: data.next_cursor as C | null, has_more: data.has_more });
  }
  async get(path: string, requireEtag = false): Promise<unknown> {
    const controller = new AbortController(); const timer = window.setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      const fetcher = this.fetcher;
      const response = await fetcher(path, { method: "GET", credentials: "same-origin", cache: "no-store",
        redirect: "error", headers: { Accept: "application/json" }, signal: controller.signal });
      if (controller.signal.aborted || response.headers.get("content-type")?.split(";")[0].trim().toLowerCase() !== "application/json") {
        throw new PrototypeReadError("PROTOTYPE_READ_UNAVAILABLE");
      }
      const payload: unknown = await response.json();
      if (!record(payload) || !id(payload.trace_id)) throw new PrototypeReadError("PROTOTYPE_READ_UNAVAILABLE");
      if (response.status !== 200) {
        const code = record(payload.error) ? payload.error.code : null;
        const expected: Readonly<Record<string, number>> = { AUTH_SESSION_EXPIRED: 401, LICENSE_OPERATION_DENIED: 403,
          RESOURCE_NOT_FOUND: 404, PROJECT_ARCHIVED: 409 };
        if (typeof code === "string" && expected[code] === response.status) throw new PrototypeReadError(code as PrototypeReadErrorCode);
        throw new PrototypeReadError("PROTOTYPE_READ_UNAVAILABLE");
      }
      if (!exact(payload, ["data", "trace_id"])) throw new PrototypeReadError("PROTOTYPE_READ_UNAVAILABLE");
      const header = response.headers.get("etag");
      if (requireEtag && (typeof header !== "string" || !etag.test(header))) {
        throw new PrototypeReadError("PROTOTYPE_READ_UNAVAILABLE");
      }
      return requireEtag ? frozen({ data: payload.data, etag: header }) : payload.data;
    } catch (failure) {
      if (failure instanceof PrototypeReadError) throw failure;
      throw new PrototypeReadError("PROTOTYPE_READ_UNAVAILABLE");
    } finally { window.clearTimeout(timer); }
  }
}

function rootOrder<T extends { updated_at: string }>(idOf: (value: T) => string): PageOrder<T> {
  return (previous, current) => previous.updated_at > current.updated_at
    || previous.updated_at === current.updated_at && idOf(previous) > idOf(current);
}
function byDescendingId<T>(idOf: (value: T) => string): PageOrder<T> {
  return (previous, current) => idOf(previous) > idOf(current);
}

export class PrototypePackageReadClient {
  readonly #transport: PrototypeReadTransport;
  constructor(fetcher: typeof fetch = fetch, timeoutMs = 10_000) { this.#transport = new PrototypeReadTransport(fetcher, timeoutMs); }
  async list(projectId: string, pageSize = 50, next: PrototypePackageCursor | null = null):
      Promise<PrototypePage<PrototypePackageView, PrototypePackageCursor>> {
    this.#transport.listInput([projectId], pageSize, next);
    return await this.#transport.page(`/api/v1/projects/${projectId}/prototype-packages${this.#transport.query(pageSize, next)}`,
      pageSize, next, value => parsePrototypePackage(value, projectId), value => value.prototype_package_id,
      rootOrder(value => value.prototype_package_id));
  }
  async get(projectId: string, packageId: string): Promise<PrototypePackageView> {
    this.#transport.ids(projectId, packageId);
    const result = await this.#transport.get(`/api/v1/projects/${projectId}/prototype-packages/${packageId}`, true) as { data: unknown; etag: string };
    const value = parsePrototypePackage(result.data, projectId, packageId, true);
    if (result.etag !== value.etag) throw new PrototypeReadError("PROTOTYPE_READ_UNAVAILABLE"); return value;
  }
}

export class PrototypeIdentityReadClient {
  readonly #transport: PrototypeReadTransport;
  constructor(fetcher: typeof fetch = fetch, timeoutMs = 10_000) { this.#transport = new PrototypeReadTransport(fetcher, timeoutMs); }
  async list(projectId: string, pageSize = 50, next: PrototypeCursor | null = null): Promise<PrototypePage<PrototypeView, PrototypeCursor>> {
    this.#transport.listInput([projectId], pageSize, next);
    return await this.#transport.page(`/api/v1/projects/${projectId}/prototypes${this.#transport.query(pageSize, next)}`,
      pageSize, next, value => parsePrototype(value, projectId), value => value.prototype_id,
      rootOrder(value => value.prototype_id));
  }
  async get(projectId: string, prototypeId: string): Promise<PrototypeView> {
    this.#transport.ids(projectId, prototypeId);
    const result = await this.#transport.get(`/api/v1/projects/${projectId}/prototypes/${prototypeId}`, true) as { data: unknown; etag: string };
    const value = parsePrototype(result.data, projectId, prototypeId);
    if (result.etag !== value.etag) throw new PrototypeReadError("PROTOTYPE_READ_UNAVAILABLE"); return value;
  }
}

export class PrototypeTemplateReadClient {
  readonly #transport: PrototypeReadTransport;
  constructor(fetcher: typeof fetch = fetch, timeoutMs = 10_000) { this.#transport = new PrototypeReadTransport(fetcher, timeoutMs); }
  async listProject(projectId: string, pageSize = 50, next: PrototypeTemplateCursor | null = null):
      Promise<PrototypePage<PrototypeTemplateView, PrototypeTemplateCursor>> {
    this.#transport.listInput([projectId], pageSize, next);
    return await this.#transport.page(`/api/v1/projects/${projectId}/prototype-templates${this.#transport.query(pageSize, next)}`,
      pageSize, next, value => parseProjectVisibleTemplate(value, projectId), value => value.prototype_template_id,
      rootOrder(value => value.prototype_template_id));
  }
  async listGlobal(pageSize = 50, next: PrototypeTemplateCursor | null = null):
      Promise<PrototypePage<PrototypeTemplateView, PrototypeTemplateCursor>> {
    this.#transport.listInput([], pageSize, next);
    return await this.#transport.page(`/api/v1/global/prototype-templates${this.#transport.query(pageSize, next)}`,
      pageSize, next, value => parsePrototypeTemplate(value, "GLOBAL", null), value => value.prototype_template_id,
      rootOrder(value => value.prototype_template_id));
  }
}

export class PrototypeVersionReadClient {
  readonly #transport: PrototypeReadTransport;
  constructor(fetcher: typeof fetch = fetch, timeoutMs = 10_000) { this.#transport = new PrototypeReadTransport(fetcher, timeoutMs); }
  async list(projectId: string, prototypeId: string, pageSize = 50, next: PrototypeVersionCursor | null = null):
      Promise<PrototypePage<PrototypeVersionView, PrototypeVersionCursor>> {
    this.#transport.listInput([projectId, prototypeId], pageSize, next, 100);
    return await this.#transport.page(`/api/v1/projects/${projectId}/prototypes/${prototypeId}/versions${this.#transport.query(pageSize, next)}`,
      pageSize, next, value => parsePrototypeVersion(value, projectId, prototypeId), value => value.prototype_version_id,
      (previous, current) => previous.version_no > current.version_no);
  }
  async get(projectId: string, prototypeId: string, versionId: string): Promise<PrototypeVersionView> {
    this.#transport.ids(projectId, prototypeId, versionId);
    return parsePrototypeVersion(await this.#transport.get(
      `/api/v1/projects/${projectId}/prototypes/${prototypeId}/versions/${versionId}`), projectId, prototypeId, versionId);
  }
}

export class PrototypeLinkReadClient {
  readonly #transport: PrototypeReadTransport;
  constructor(fetcher: typeof fetch = fetch, timeoutMs = 10_000) { this.#transport = new PrototypeReadTransport(fetcher, timeoutMs); }
  async list(projectId: string, pageSize = 50, next: PrototypeLinkCursor | null = null):
      Promise<PrototypePage<PrototypeLinkView, PrototypeLinkCursor>> {
    this.#transport.listInput([projectId], pageSize, next);
    return await this.#transport.page(`/api/v1/projects/${projectId}/prototype-requirement-links${this.#transport.query(pageSize, next)}`,
      pageSize, next, value => parsePrototypeLink(value, projectId), value => value.requirement_prototype_link_id,
      byDescendingId(value => value.requirement_prototype_link_id));
  }
}
