import { SessionClient, SessionClientError } from "@/modules/auth/api/sessionClient";

export type SurveyRoundState = "PLANNED" | "OPEN" | "CLOSED" | "CANCELLED";
export type SurveyRoundCursor = string & { readonly __family: "survey-rounds" };
export interface SurveyRoundSourceView { readonly round_source_record_ref_id: string; readonly question_id: string | null;
  readonly document_id: string; readonly document_version_id: string; readonly evidence_id: string;
  readonly observed_evidence_lock_version: number; readonly content_fingerprint: string; readonly recorded_by: string;
  readonly recorded_at: string; readonly ordinal: number; }
export interface SurveyRoundView { readonly survey_round_id: string; readonly survey_id: string; readonly survey_version_id: string;
  readonly project_id: string; readonly round_no: number; readonly state: SurveyRoundState;
  readonly scheduled_start_at: string | null; readonly scheduled_end_at: string | null; readonly location_note: string | null;
  readonly opened_by: string | null; readonly opened_at: string | null; readonly closed_by: string | null;
  readonly closed_at: string | null; readonly close_report_fingerprint: string | null; readonly cancelled_by: string | null;
  readonly cancelled_at: string | null; readonly cancellation_reason: string | null; readonly created_by: string;
  readonly created_at: string; readonly updated_by: string | null; readonly updated_at: string; readonly etag: string;
  readonly source_record_count: number; readonly source_records?: readonly SurveyRoundSourceView[]; }
export interface SurveyRoundPage { readonly items: readonly SurveyRoundView[]; readonly next_cursor: SurveyRoundCursor | null; readonly has_more: boolean; }
export interface SurveyRoundScheduleInput { readonly scheduled_start_at: string | null; readonly scheduled_end_at: string | null; readonly location_note: string | null; }
export interface SurveyRoundCreateInput extends SurveyRoundScheduleInput { readonly survey_id: string; readonly survey_version_id: string; }

const messages = { SURVEY_ROUND_INVALID_INPUT: "轮次、计划时间或操作参数无效。", AUTH_RELOGIN_REQUIRED: "修改调研轮次前请重新登录。",
  AUTH_CLIENT_BUSY: "正在处理会话操作，请稍候。", AUTH_SESSION_EXPIRED: "会话已失效，请重新登录。",
  AUTH_CSRF_INVALID: "登录状态已变化，请重新登录。", LICENSE_OPERATION_DENIED: "当前许可不允许操作调研轮次。",
  RESOURCE_NOT_FOUND: "调研轮次不存在，或当前账户无权访问。", PROJECT_ARCHIVED: "项目已归档，不能再操作调研轮次。",
  CONFLICT_VERSION: "调研轮次已被其他操作更新，请重新读取。", CONFLICT_IDEMPOTENCY: "原操作号与本次输入不一致，已停止提交。",
  CONFLICT_STATE: "当前调研轮次状态不允许此操作。", SURVEY_ROUND_INCOMPLETE: "轮次尚未满足关闭条件；请补齐有效响应与当前证据后重试。",
  SURVEY_ROUND_UNAVAILABLE: "暂时无法确认调研轮次结果；请重新读取并核对审计。" } as const;
export type SurveyRoundErrorCode = keyof typeof messages;
export class SurveyRoundError extends Error { readonly uncertain: boolean; constructor(readonly code: SurveyRoundErrorCode) {
  super(messages[code]); this.name = "SurveyRoundError"; this.uncertain = code === "SURVEY_ROUND_UNAVAILABLE"; } }

const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const cursorPattern = /^[A-Za-z0-9_-]{1,1024}\.[A-Za-z0-9_-]{43}$/; const etagPattern = /^"v(0|[1-9][0-9]*)"$/;
const digest = /^[0-9a-f]{64}$/; const states = new Set<SurveyRoundState>(["PLANNED", "OPEN", "CLOSED", "CANCELLED"]);
function record(v: unknown): v is Record<string, unknown> { return typeof v === "object" && v !== null && !Array.isArray(v); }
function exact(v: Record<string, unknown>, keys: readonly string[]) { return Object.keys(v).length === keys.length && keys.every(k => Object.hasOwn(v, k)); }
function id(v: unknown): v is string { return typeof v === "string" && uuid.test(v) && v !== "00000000-0000-0000-0000-000000000000"; }
function optionalId(v: unknown): v is string | null { return v === null || id(v); }
function instant(v: unknown): v is string { return typeof v === "string" && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$/.test(v) && Number.isFinite(Date.parse(v)); }
function optionalInstant(v: unknown): v is string | null { return v === null || instant(v); }
function integer(v: unknown, min = 0): v is number { return typeof v === "number" && Number.isSafeInteger(v) && v >= min; }
function optionalText(v: unknown, max: number): v is string | null { return v === null || typeof v === "string" && v.length > 0 && v.length <= max && v.trim() === v && !/\p{C}/u.test(v); }
const common = ["survey_round_id","survey_id","survey_version_id","project_id","round_no","state","scheduled_start_at","scheduled_end_at","location_note","opened_by","opened_at","closed_by","closed_at","close_report_fingerprint","cancelled_by","cancelled_at","cancellation_reason","created_by","created_at","updated_by","updated_at","etag","source_record_count"] as const;
const sourceKeys = ["round_source_record_ref_id","question_id","document_id","document_version_id","evidence_id","observed_evidence_lock_version","content_fingerprint","recorded_by","recorded_at","ordinal"] as const;
function parseSource(v: unknown, ordinal: number): SurveyRoundSourceView { if (!record(v) || !exact(v, sourceKeys) || !id(v.round_source_record_ref_id)
  || !optionalId(v.question_id) || !id(v.document_id) || !id(v.document_version_id) || !id(v.evidence_id)
  || !integer(v.observed_evidence_lock_version) || typeof v.content_fingerprint !== "string" || !digest.test(v.content_fingerprint)
  || !id(v.recorded_by) || !instant(v.recorded_at) || v.ordinal !== ordinal) throw new SurveyRoundError("SURVEY_ROUND_UNAVAILABLE");
  return Object.freeze({ ...v }) as unknown as SurveyRoundSourceView; }
export function parseSurveyRound(v: unknown, projectId: string, expectedId?: string, detail = false): SurveyRoundView {
  const keys = detail ? [...common, "source_records"] : common;
  if (!record(v) || !exact(v, keys) || !id(v.survey_round_id) || expectedId !== undefined && v.survey_round_id !== expectedId
    || v.project_id !== projectId || !id(v.survey_id) || !id(v.survey_version_id) || !integer(v.round_no, 1)
    || !states.has(v.state as SurveyRoundState) || !optionalInstant(v.scheduled_start_at) || !optionalInstant(v.scheduled_end_at)
    || (v.scheduled_start_at === null) !== (v.scheduled_end_at === null) || v.scheduled_start_at !== null && v.scheduled_end_at !== null && v.scheduled_end_at <= v.scheduled_start_at
    || !optionalText(v.location_note, 1000) || !optionalId(v.opened_by) || !optionalInstant(v.opened_at) || !optionalId(v.closed_by)
    || !optionalInstant(v.closed_at) || v.close_report_fingerprint !== null && (typeof v.close_report_fingerprint !== "string" || !digest.test(v.close_report_fingerprint))
    || !optionalId(v.cancelled_by) || !optionalInstant(v.cancelled_at) || !optionalText(v.cancellation_reason, 2000)
    || !id(v.created_by) || !instant(v.created_at) || !optionalId(v.updated_by) || !instant(v.updated_at) || typeof v.etag !== "string" || !etagPattern.test(v.etag)
    || !integer(v.source_record_count) || detail && !Array.isArray(v.source_records)) throw new SurveyRoundError("SURVEY_ROUND_UNAVAILABLE");
  const state = v.state as SurveyRoundState; const opened = v.opened_by !== null && v.opened_at !== null;
  const closed = v.closed_by !== null && v.closed_at !== null && v.close_report_fingerprint !== null;
  const cancelled = v.cancelled_by !== null && v.cancelled_at !== null && v.cancellation_reason !== null;
  if ((state === "PLANNED" && (opened || closed || cancelled)) || (state === "OPEN" && (!opened || closed || cancelled))
    || (state === "CLOSED" && (!opened || !closed || cancelled)) || (state === "CANCELLED" && (opened || closed || !cancelled))
    || Date.parse(v.updated_at as string) < Date.parse(v.created_at as string)) throw new SurveyRoundError("SURVEY_ROUND_UNAVAILABLE");
  const sources = detail ? (v.source_records as unknown[]).map(parseSource) : undefined;
  if (sources && sources.length !== v.source_record_count) throw new SurveyRoundError("SURVEY_ROUND_UNAVAILABLE");
  return Object.freeze({ ...v, ...(sources ? { source_records: Object.freeze(sources) } : {}) }) as unknown as SurveyRoundView;
}
function parseEnvelope(v: unknown): { data: unknown; trace_id: string } { if (!record(v) || !exact(v, ["data","trace_id"]) || !id(v.trace_id)) throw new SurveyRoundError("SURVEY_ROUND_UNAVAILABLE"); return v as { data: unknown; trace_id: string }; }
async function payload(response: Response): Promise<unknown> { const type = response.headers.get("Content-Type")?.split(";",1)[0].trim().toLowerCase(); if (type !== "application/json") throw new SurveyRoundError("SURVEY_ROUND_UNAVAILABLE"); try { return await response.json(); } catch { throw new SurveyRoundError("SURVEY_ROUND_UNAVAILABLE"); } }
function readFailure(status: number, v: unknown): never { let code = ""; if (record(v) && record(v.error) && typeof v.error.code === "string") code = v.error.code;
  const known: Record<string, SurveyRoundErrorCode> = { AUTH_SESSION_EXPIRED:"AUTH_SESSION_EXPIRED", LICENSE_OPERATION_DENIED:"LICENSE_OPERATION_DENIED", RESOURCE_NOT_FOUND:"RESOURCE_NOT_FOUND", PROJECT_ARCHIVED:"PROJECT_ARCHIVED" };
  throw new SurveyRoundError(known[code] ?? (status === 400 || status === 422 ? "SURVEY_ROUND_INVALID_INPUT" : "SURVEY_ROUND_UNAVAILABLE")); }
function validProject(v: string) { if (!id(v)) throw new SurveyRoundError("SURVEY_ROUND_INVALID_INPUT"); }
export class SurveyRoundReadClient { constructor(private readonly fetcher: typeof fetch = globalThis.fetch.bind(globalThis)) {}
  async #get(path: string) { let response: Response; try { response = await this.fetcher(path, { method:"GET", credentials:"same-origin", cache:"no-store", redirect:"error", headers:{ Accept:"application/json" } }); } catch { throw new SurveyRoundError("SURVEY_ROUND_UNAVAILABLE"); }
    const value = await payload(response); if (!response.ok) readFailure(response.status, value); return { response, envelope: parseEnvelope(value) }; }
  async list(projectId: string, pageSize = 50, next: SurveyRoundCursor | null = null): Promise<SurveyRoundPage> { validProject(projectId); if (!Number.isSafeInteger(pageSize) || pageSize < 1 || pageSize > 100 || next !== null && !cursorPattern.test(next)) throw new SurveyRoundError("SURVEY_ROUND_INVALID_INPUT");
    const q = new URLSearchParams({ page_size:String(pageSize) }); if (next) q.set("next_cursor", next); const { envelope } = await this.#get(`/api/v1/projects/${projectId}/survey-rounds?${q}`); const d = envelope.data;
    if (!record(d) || !exact(d,["items","next_cursor","has_more"]) || !Array.isArray(d.items) || typeof d.has_more !== "boolean" || d.next_cursor !== null && (typeof d.next_cursor !== "string" || !cursorPattern.test(d.next_cursor)) || d.has_more !== (d.next_cursor !== null)) throw new SurveyRoundError("SURVEY_ROUND_UNAVAILABLE");
    const items = d.items.map(x => parseSurveyRound(x, projectId)); if (new Set(items.map(x => x.survey_round_id)).size !== items.length
      || items.some((item,index)=>index>0 && (item.created_at>items[index-1]!.created_at || item.created_at===items[index-1]!.created_at && item.survey_round_id>=items[index-1]!.survey_round_id))) throw new SurveyRoundError("SURVEY_ROUND_UNAVAILABLE");
    return Object.freeze({ items:Object.freeze(items), next_cursor:d.next_cursor as SurveyRoundCursor|null, has_more:d.has_more }); }
  async get(projectId: string, roundId: string) { validProject(projectId); if (!id(roundId)) throw new SurveyRoundError("SURVEY_ROUND_INVALID_INPUT"); const { response, envelope } = await this.#get(`/api/v1/projects/${projectId}/survey-rounds/${roundId}`); const item = parseSurveyRound(envelope.data, projectId, roundId, true); if (response.headers.get("ETag") !== item.etag) throw new SurveyRoundError("SURVEY_ROUND_UNAVAILABLE"); return item; }
}

function schedule(v: SurveyRoundScheduleInput) { if (!record(v) || !["scheduled_start_at","scheduled_end_at","location_note"].every(k=>Object.hasOwn(v,k)) || !optionalInstant(v.scheduled_start_at) || !optionalInstant(v.scheduled_end_at)
  || (v.scheduled_start_at === null) !== (v.scheduled_end_at === null) || v.scheduled_start_at !== null && v.scheduled_end_at !== null && v.scheduled_end_at <= v.scheduled_start_at || !optionalText(v.location_note,1000)) throw new SurveyRoundError("SURVEY_ROUND_INVALID_INPUT"); }
export class SurveyRoundWriteClient { constructor(private readonly session: SessionClient) { if (!(session instanceof SessionClient)) throw new SurveyRoundError("SURVEY_ROUND_INVALID_INPUT"); }
  async #send(projectId:string, roundId:string|null, operation:"create"|"patch"|"open"|"close"|"cancel", body:unknown|null, etag:string|null, key:string|null) { validProject(projectId); if (roundId !== null && !id(roundId) || etag !== null && !etagPattern.test(etag) || key !== null && !/^[\x20-\x7e]{16,128}$/.test(key)) throw new SurveyRoundError("SURVEY_ROUND_INVALID_INPUT");
    let response:Response; try { response = await this.session.writeProjectSurveyRound(projectId,roundId,operation === "patch"?"PATCH":"POST",operation,body===null?null:JSON.stringify(body),etag,key); } catch (e) { if (e instanceof SessionClientError && (e.code === "AUTH_RELOGIN_REQUIRED" || e.code === "AUTH_CLIENT_BUSY")) throw new SurveyRoundError(e.code); throw new SurveyRoundError("SURVEY_ROUND_UNAVAILABLE"); }
    const value = await payload(response); if (!response.ok) { let code=""; if (record(value)&&record(value.error)&&typeof value.error.code==="string") code=value.error.code; const known:Record<string,SurveyRoundErrorCode>={ AUTH_SESSION_EXPIRED:"AUTH_SESSION_EXPIRED",AUTH_CSRF_INVALID:"AUTH_CSRF_INVALID",LICENSE_OPERATION_DENIED:"LICENSE_OPERATION_DENIED",RESOURCE_NOT_FOUND:"RESOURCE_NOT_FOUND",PROJECT_ARCHIVED:"PROJECT_ARCHIVED",CONFLICT_VERSION:"CONFLICT_VERSION",CONFLICT_IDEMPOTENCY:"CONFLICT_IDEMPOTENCY",CONFLICT_STATE:"CONFLICT_STATE"}; if (code==="VALIDATION_FAILED") throw new SurveyRoundError(operation==="close"?"SURVEY_ROUND_INCOMPLETE":"SURVEY_ROUND_INVALID_INPUT"); throw new SurveyRoundError(known[code]??"SURVEY_ROUND_UNAVAILABLE"); }
    if (response.status !== (operation === "create" ? 201 : 200)) throw new SurveyRoundError("SURVEY_ROUND_UNAVAILABLE"); const item=parseSurveyRound(parseEnvelope(value).data,projectId,undefined,true); if (response.headers.get("ETag")!==item.etag || operation==="create" && response.headers.get("Location")!==`/api/v1/projects/${projectId}/survey-rounds/${item.survey_round_id}`) throw new SurveyRoundError("SURVEY_ROUND_UNAVAILABLE"); return item; }
  async create(projectId:string,input:SurveyRoundCreateInput,key:string){ if(!record(input)||!exact(input,["survey_id","survey_version_id","scheduled_start_at","scheduled_end_at","location_note"])||!id(input.survey_id)||!id(input.survey_version_id)) throw new SurveyRoundError("SURVEY_ROUND_INVALID_INPUT"); schedule(input); return await this.#send(projectId,null,"create",input,null,key); }
  async patch(projectId:string,roundId:string,etag:string,input:SurveyRoundScheduleInput){ schedule(input); return await this.#send(projectId,roundId,"patch",input,etag,null); }
  open(projectId:string,roundId:string,etag:string,key:string){ return this.#send(projectId,roundId,"open",null,etag,key); }
  close(projectId:string,roundId:string,etag:string,key:string){ return this.#send(projectId,roundId,"close",null,etag,key); }
  async cancel(projectId:string,roundId:string,etag:string,key:string,reason:string){ if(typeof reason!=="string"||reason.length<1||reason.length>2000||reason.trim()!==reason||/\p{C}/u.test(reason)) throw new SurveyRoundError("SURVEY_ROUND_INVALID_INPUT"); return await this.#send(projectId,roundId,"cancel",{reason},etag,key); }
}
