import type { SurveySourceKind } from "./surveyReadClient";

export type SurveySourceResolutionState = "LOCATABLE" | "PARTIALLY_LOCATABLE" | "UNAVAILABLE";
export type SurveySourceUnavailableReason = "MANUAL_SOURCE_NOT_FIXED" | "NO_AUTHORIZED_LOCATION" | "SOURCE_TARGET_UNAVAILABLE";
export type SurveySourceRecordRef =
  | Readonly<{ record_kind: "HANDOVER_ITEM"; handover_analysis_id: string;
      handover_analysis_version_id: string; analysis_item_id: string }>
  | Readonly<{ record_kind: "CAPABILITY_ITEM"; baseline_id: string;
      baseline_version_id: string; capability_item_id: string }>
  | Readonly<{ record_kind: "TEMPLATE_DOCUMENT_VERSION"; document_id: string;
      document_version_id: string }>;
export type SurveySourceLocation =
  | Readonly<{ location_kind: "BUSINESS_RECORD"; scope: "PROJECT"; project_id: string;
      handover_analysis_id: string; handover_analysis_version_id: string; analysis_item_id: string }>
  | Readonly<{ location_kind: "EVIDENCE"; scope: "PROJECT"; project_id: string; evidence_id: string }>
  | Readonly<{ location_kind: "DOCUMENT_VERSION"; scope: "PROJECT"; project_id: string;
      document_id: string; document_version_id: string }>;
export interface SurveySourceLocationView {
  readonly source_kind: SurveySourceKind;
  readonly source_ordinal: number;
  readonly resolution_state: SurveySourceResolutionState;
  readonly current_eligibility: boolean;
  readonly record_ref: SurveySourceRecordRef | null;
  readonly locations: readonly SurveySourceLocation[];
  readonly unavailable_reason: SurveySourceUnavailableReason | null;
}

const messages = {
  SURVEY_SOURCE_LOCATION_INVALID_INPUT: "来源定位参数无效。",
  AUTH_SESSION_EXPIRED: "会话已失效，请重新登录。",
  LICENSE_OPERATION_DENIED: "当前许可不允许定位调研来源。",
  RESOURCE_NOT_FOUND: "固定来源不存在，或当前账户无权查看。",
  PROJECT_ARCHIVED: "项目已归档，当前来源不可读取。",
  SURVEY_SOURCE_LOCATION_UNAVAILABLE: "暂时无法定位该来源，请稍后重试。",
} as const;
export type SurveySourceLocationErrorCode = keyof typeof messages;
export class SurveySourceLocationClientError extends Error {
  constructor(readonly code: SurveySourceLocationErrorCode) {
    super(messages[code]); this.name = "SurveySourceLocationClientError";
  }
}

const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const sourceKinds = new Set<SurveySourceKind>(["HANDOVER_ITEM", "CAPABILITY_ITEM", "TEMPLATE_DOCUMENT_VERSION", "MANUAL"]);
const states = new Set<SurveySourceResolutionState>(["LOCATABLE", "PARTIALLY_LOCATABLE", "UNAVAILABLE"]);
const reasons = new Set<SurveySourceUnavailableReason>(["MANUAL_SOURCE_NOT_FIXED", "NO_AUTHORIZED_LOCATION", "SOURCE_TARGET_UNAVAILABLE"]);
function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
function exact(value: Record<string, unknown>, fields: readonly string[]): boolean {
  return Object.keys(value).length === fields.length && fields.every(field => Object.hasOwn(value, field));
}
function id(value: unknown): value is string {
  return typeof value === "string" && uuid.test(value) && value !== "00000000-0000-0000-0000-000000000000";
}
function freeze<T extends object>(value: T): Readonly<T> { return Object.freeze(value); }

function parseRecord(value: unknown, kind: SurveySourceKind): SurveySourceRecordRef | null {
  if (value === null) return null;
  if (!record(value) || value.record_kind !== kind) throw new SurveySourceLocationClientError("SURVEY_SOURCE_LOCATION_UNAVAILABLE");
  if (kind === "HANDOVER_ITEM" && exact(value, ["record_kind", "handover_analysis_id", "handover_analysis_version_id", "analysis_item_id"])
      && id(value.handover_analysis_id) && id(value.handover_analysis_version_id) && id(value.analysis_item_id)) {
    return freeze({ record_kind: kind, handover_analysis_id: value.handover_analysis_id,
      handover_analysis_version_id: value.handover_analysis_version_id, analysis_item_id: value.analysis_item_id });
  }
  if (kind === "CAPABILITY_ITEM" && exact(value, ["record_kind", "baseline_id", "baseline_version_id", "capability_item_id"])
      && id(value.baseline_id) && id(value.baseline_version_id) && id(value.capability_item_id)) {
    return freeze({ record_kind: kind, baseline_id: value.baseline_id,
      baseline_version_id: value.baseline_version_id, capability_item_id: value.capability_item_id });
  }
  if (kind === "TEMPLATE_DOCUMENT_VERSION" && exact(value, ["record_kind", "document_id", "document_version_id"])
      && id(value.document_id) && id(value.document_version_id)) {
    return freeze({ record_kind: kind, document_id: value.document_id, document_version_id: value.document_version_id });
  }
  throw new SurveySourceLocationClientError("SURVEY_SOURCE_LOCATION_UNAVAILABLE");
}

function parseLocation(value: unknown, projectId: string, kind: SurveySourceKind): SurveySourceLocation {
  if (!record(value) || value.scope !== "PROJECT" || value.project_id !== projectId) {
    throw new SurveySourceLocationClientError("SURVEY_SOURCE_LOCATION_UNAVAILABLE");
  }
  if (kind === "HANDOVER_ITEM" && value.location_kind === "BUSINESS_RECORD"
      && exact(value, ["location_kind", "scope", "project_id", "handover_analysis_id", "handover_analysis_version_id", "analysis_item_id"])
      && id(value.handover_analysis_id) && id(value.handover_analysis_version_id) && id(value.analysis_item_id)) {
    return freeze({ location_kind: value.location_kind, scope: value.scope, project_id: projectId,
      handover_analysis_id: value.handover_analysis_id, handover_analysis_version_id: value.handover_analysis_version_id,
      analysis_item_id: value.analysis_item_id });
  }
  if (kind === "HANDOVER_ITEM" && value.location_kind === "EVIDENCE"
      && exact(value, ["location_kind", "scope", "project_id", "evidence_id"]) && id(value.evidence_id)) {
    return freeze({ location_kind: value.location_kind, scope: value.scope, project_id: projectId,
      evidence_id: value.evidence_id });
  }
  if (kind === "TEMPLATE_DOCUMENT_VERSION" && value.location_kind === "DOCUMENT_VERSION"
      && exact(value, ["location_kind", "scope", "project_id", "document_id", "document_version_id"])
      && id(value.document_id) && id(value.document_version_id)) {
    return freeze({ location_kind: value.location_kind, scope: value.scope, project_id: projectId,
      document_id: value.document_id, document_version_id: value.document_version_id });
  }
  throw new SurveySourceLocationClientError("SURVEY_SOURCE_LOCATION_UNAVAILABLE");
}

const fields = ["source_kind", "source_ordinal", "resolution_state", "current_eligibility",
  "record_ref", "locations", "unavailable_reason"] as const;
export function parseSurveySourceLocation(value: unknown, projectId: string,
                                          kind: SurveySourceKind, ordinal: number): SurveySourceLocationView {
  if (!record(value) || !exact(value, fields) || value.source_kind !== kind || !sourceKinds.has(kind)
      || value.source_ordinal !== ordinal || !states.has(value.resolution_state as SurveySourceResolutionState)
      || typeof value.current_eligibility !== "boolean" || !Array.isArray(value.locations) || value.locations.length > 100
      || value.unavailable_reason !== null && !reasons.has(value.unavailable_reason as SurveySourceUnavailableReason)) {
    throw new SurveySourceLocationClientError("SURVEY_SOURCE_LOCATION_UNAVAILABLE");
  }
  const state = value.resolution_state as SurveySourceResolutionState;
  const reason = value.unavailable_reason as SurveySourceUnavailableReason | null;
  const ref = parseRecord(value.record_ref, kind);
  const locations = value.locations.map(item => parseLocation(item, projectId, kind));
  if (state === "LOCATABLE" && (ref === null || locations.length < 1 || reason !== null)
      || state === "PARTIALLY_LOCATABLE" && (ref === null || locations.length !== 0 || reason !== "NO_AUTHORIZED_LOCATION")
      || state === "UNAVAILABLE" && (ref !== null || locations.length !== 0 || value.current_eligibility
        || reason !== "MANUAL_SOURCE_NOT_FIXED" && reason !== "SOURCE_TARGET_UNAVAILABLE")
      || kind === "MANUAL" && (state !== "UNAVAILABLE" || reason !== "MANUAL_SOURCE_NOT_FIXED")
      || kind === "CAPABILITY_ITEM" && locations.length !== 0) {
    throw new SurveySourceLocationClientError("SURVEY_SOURCE_LOCATION_UNAVAILABLE");
  }
  if (ref?.record_kind === "HANDOVER_ITEM" && locations.some(item => item.location_kind === "BUSINESS_RECORD"
      && (item.handover_analysis_id !== ref.handover_analysis_id
        || item.handover_analysis_version_id !== ref.handover_analysis_version_id
        || item.analysis_item_id !== ref.analysis_item_id))) {
    throw new SurveySourceLocationClientError("SURVEY_SOURCE_LOCATION_UNAVAILABLE");
  }
  if (ref?.record_kind === "TEMPLATE_DOCUMENT_VERSION" && locations.some(item => item.location_kind === "DOCUMENT_VERSION"
      && (item.document_id !== ref.document_id || item.document_version_id !== ref.document_version_id))) {
    throw new SurveySourceLocationClientError("SURVEY_SOURCE_LOCATION_UNAVAILABLE");
  }
  return freeze({ source_kind: kind, source_ordinal: ordinal, resolution_state: state,
    current_eligibility: value.current_eligibility, record_ref: ref,
    locations: Object.freeze(locations), unavailable_reason: reason });
}

export class SurveySourceLocationClient {
  constructor(private readonly fetcher: typeof fetch = fetch, private readonly timeoutMs = 10_000) {
    if (!Number.isSafeInteger(timeoutMs) || timeoutMs < 1 || timeoutMs > 30_000) {
      throw new SurveySourceLocationClientError("SURVEY_SOURCE_LOCATION_INVALID_INPUT");
    }
  }
  async get(projectId: string, surveyId: string, versionId: string, questionId: string,
            ordinal: number, kind: SurveySourceKind): Promise<SurveySourceLocationView> {
    if (![projectId, surveyId, versionId, questionId].every(id) || !Number.isSafeInteger(ordinal)
        || ordinal < 0 || ordinal > 99 || !sourceKinds.has(kind)) {
      throw new SurveySourceLocationClientError("SURVEY_SOURCE_LOCATION_INVALID_INPUT");
    }
    const controller = new AbortController(); const timer = window.setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      // Keep the platform fetch detached from this client instance. Native browser
      // implementations may reject an invocation whose receiver is not Window.
      const fetcher = this.fetcher;
      const response = await fetcher(
        `/api/v1/projects/${projectId}/surveys/${surveyId}/versions/${versionId}/questions/${questionId}/sources/${ordinal}/location`,
        { method: "GET", credentials: "same-origin", cache: "no-store", redirect: "error",
          headers: { Accept: "application/json" }, signal: controller.signal });
      if (controller.signal.aborted || response.headers.get("content-type")?.split(";")[0].trim().toLowerCase() !== "application/json") {
        throw new SurveySourceLocationClientError("SURVEY_SOURCE_LOCATION_UNAVAILABLE");
      }
      const payload: unknown = await response.json();
      if (!record(payload) || !id(payload.trace_id)) throw new SurveySourceLocationClientError("SURVEY_SOURCE_LOCATION_UNAVAILABLE");
      if (response.status !== 200) {
        const code = record(payload.error) ? payload.error.code : null;
        const expected: Readonly<Record<string, number>> = { AUTH_SESSION_EXPIRED: 401,
          LICENSE_OPERATION_DENIED: 403, RESOURCE_NOT_FOUND: 404, PROJECT_ARCHIVED: 409 };
        if (typeof code === "string" && expected[code] === response.status) {
          throw new SurveySourceLocationClientError(code as SurveySourceLocationErrorCode);
        }
        throw new SurveySourceLocationClientError("SURVEY_SOURCE_LOCATION_UNAVAILABLE");
      }
      if (!exact(payload, ["data", "trace_id"])) throw new SurveySourceLocationClientError("SURVEY_SOURCE_LOCATION_UNAVAILABLE");
      return parseSurveySourceLocation(payload.data, projectId, kind, ordinal);
    } catch (failure) {
      if (failure instanceof SurveySourceLocationClientError) throw failure;
      throw new SurveySourceLocationClientError("SURVEY_SOURCE_LOCATION_UNAVAILABLE");
    } finally { window.clearTimeout(timer); }
  }
}
