import { SessionClient, SessionClientError } from "@/modules/auth/api/sessionClient";

export type SurveyConclusionState = "DRAFT" | "IN_REVIEW" | "APPROVED" | "RETURNED" | "SUPERSEDED" | "RESTRICTED";
export type SurveyConclusionCursor = string & { readonly __family: "survey-conclusions" };
export interface DepartmentConclusion { readonly department_id: string; readonly title: string; readonly statement: string;
  readonly response_refs: readonly string[]; readonly ordinal: number; }
export interface ModuleConclusion { readonly module_key: string; readonly title: string; readonly statement: string;
  readonly response_refs: readonly string[]; readonly ordinal: number; }
export interface ConclusionEvidence { readonly reference_role: "SUPPORT" | "CONFLICT"; readonly document_id: string;
  readonly document_version_id: string; readonly evidence_id: string; readonly observed_evidence_lock_version: number;
  readonly content_fingerprint: string; readonly ordinal: number; }
export interface ConclusionOpenIssue { readonly issue_owner_module: "handover"; readonly issue_object_type: "HND-03";
  readonly issue_id: string; readonly observed_issue_state: string; readonly observed_lock_version: number;
  readonly is_blocking: boolean; readonly ordinal: number; }
export interface SurveyConclusionSummary { readonly survey_conclusion_id: string; readonly conclusion_series_id: string;
  readonly project_id: string; readonly survey_id: string; readonly round_refs: readonly string[];
  readonly ai_task_refs: readonly string[]; readonly version_no: number; readonly state: SurveyConclusionState;
  readonly content_fingerprint: string; readonly department_count: number; readonly module_count: number;
  readonly evidence_count: number; readonly open_issue_count: number; readonly supersedes_ref: string | null;
  readonly review_id: string | null; readonly review_round_id: string | null; readonly created_by: string;
  readonly created_at: string; }
export interface SurveyConclusionView extends SurveyConclusionSummary { readonly department_conclusions: readonly DepartmentConclusion[];
  readonly module_conclusions: readonly ModuleConclusion[]; readonly evidence_refs: readonly ConclusionEvidence[];
  readonly open_issue_refs: readonly ConclusionOpenIssue[]; }
export interface SurveyConclusionPage { readonly items: readonly SurveyConclusionSummary[];
  readonly next_cursor: SurveyConclusionCursor | null; readonly has_more: boolean; }
export interface DepartmentConclusionInput { readonly department_id: string; readonly title: string; readonly statement: string;
  readonly response_refs: readonly string[]; }
export interface ModuleConclusionInput { readonly module_key: string; readonly title: string; readonly statement: string;
  readonly response_refs: readonly string[]; }
export interface SurveyConclusionCreateInput { readonly survey_id: string; readonly round_refs: readonly string[];
  readonly department_conclusions: readonly DepartmentConclusionInput[]; readonly module_conclusions: readonly ModuleConclusionInput[];
  readonly evidence_refs: readonly { readonly evidence_id: string; readonly reference_role: "SUPPORT" | "CONFLICT" }[];
  readonly open_issue_refs: readonly { readonly action_item_id: string; readonly is_blocking: boolean }[];
  readonly ai_task_refs: readonly string[]; readonly supersedes_ref: string | null; }
export interface SurveyConclusionValidation { readonly audit_event_id: string; readonly survey_conclusion_id: string;
  readonly conclusion_series_id: string; readonly project_id: string; readonly survey_id: string; readonly version_no: number;
  readonly state: SurveyConclusionState; readonly valid: boolean; readonly blocking_issues: readonly string[];
  readonly warnings: readonly string[]; readonly coverage_summary: Readonly<{ department_count: number; module_count: number;
    evidence_count: number; open_issue_count: number; response_count: number; support_evidence_count: number;
    conflict_evidence_count: number; current_open_blocking_issue_count: number }>; readonly checked_at: string; }
export interface SurveyConclusionReviewReceipt { readonly review_id: string; readonly review_round_id: string;
  readonly subject_type: "SRV-05"; readonly project_id: string; readonly conclusion_series_id: string;
  readonly survey_conclusion_id: string; readonly policy_ref: "SURVEY_CONCLUSION_ALL_V1";
  readonly reviewer_ids: readonly string[]; readonly state: "IN_REVIEW"; readonly round_no: number;
  readonly review_etag: string; readonly submitted_by: string; readonly submitted_at: string; }

const messages = { SURVEY_CONCLUSION_INVALID_INPUT: "结论、来源、评审人或操作参数无效。",
  AUTH_RELOGIN_REQUIRED: "提交调研结论前请重新登录。", AUTH_CLIENT_BUSY: "正在处理会话操作，请稍候。",
  AUTH_SESSION_EXPIRED: "会话已失效，请重新登录。", AUTH_CSRF_INVALID: "登录状态已变化，请重新登录。",
  LICENSE_OPERATION_DENIED: "当前许可不允许操作调研结论。", RESOURCE_NOT_FOUND: "调研结论不存在，或当前账户无权访问。",
  PROJECT_ARCHIVED: "项目已归档，不能再操作调研结论。", CONFLICT_IDEMPOTENCY: "原操作号与本次输入不一致，已停止提交。",
  CONFLICT_STATE: "当前结论状态不允许此操作。", CONFLICT_VERSION: "结论已被其他操作更新，请重新读取。",
  SURVEY_CONCLUSION_SOURCE_INVALID: "结论来源已经变化或不满足固定要求，请重新选择当前事实。",
  SURVEY_CONCLUSION_INCOMPLETE: "结论尚未满足验证或送审条件，请按问题清单补齐来源与人工结论。",
  REVIEW_REVIEWER_INELIGIBLE: "所选评审人不满足当前项目评审资格。", REVIEW_SUBJECT_LOCKED: "该结论已有进行中的评审。",
  SURVEY_CONCLUSION_UNAVAILABLE: "暂时无法确认调研结论结果；请重新读取并核对审计。" } as const;
export type SurveyConclusionErrorCode = keyof typeof messages;
export class SurveyConclusionError extends Error { readonly uncertain: boolean;
  constructor(readonly code: SurveyConclusionErrorCode) { super(messages[code]); this.name = "SurveyConclusionError";
    this.uncertain = code === "SURVEY_CONCLUSION_UNAVAILABLE"; } }

const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const cursor = /^[A-Za-z0-9_-]{1,1024}\.[A-Za-z0-9_-]{43}$/; const digest = /^[0-9a-f]{64}$/;
const etag = /^"v(0|[1-9][0-9]*)"$/; const states = new Set<SurveyConclusionState>(["DRAFT","IN_REVIEW","APPROVED","RETURNED","SUPERSEDED","RESTRICTED"]);
function record(v: unknown): v is Record<string, unknown> { return typeof v === "object" && v !== null && !Array.isArray(v); }
function exact(v: Record<string, unknown>, keys: readonly string[]) { return Object.keys(v).length === keys.length && keys.every(k => Object.hasOwn(v,k)); }
function id(v: unknown): v is string { return typeof v === "string" && uuid.test(v) && v !== "00000000-0000-0000-0000-000000000000"; }
function optionalId(v: unknown): v is string|null { return v === null || id(v); }
function instant(v: unknown): v is string { return typeof v === "string" && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$/.test(v) && Number.isFinite(Date.parse(v)); }
function integer(v: unknown, min=0): v is number { return typeof v === "number" && Number.isSafeInteger(v) && v >= min; }
function text(v: unknown, max: number): v is string { return typeof v === "string" && v.length > 0 && v.length <= max && v.trim() === v && !/\p{C}/u.test(v); }
function ids(v: unknown): v is string[] { return Array.isArray(v) && v.every(id) && new Set(v).size === v.length; }
const summaryFields = ["survey_conclusion_id","conclusion_series_id","project_id","survey_id","round_refs","ai_task_refs","version_no","state","content_fingerprint","department_count","module_count","evidence_count","open_issue_count","supersedes_ref","review_id","review_round_id","created_by","created_at"] as const;
function parseSummary(v: unknown, projectId: string, expectedId?: string): SurveyConclusionSummary { if (!record(v) || !exact(v,summaryFields)
  || !id(v.survey_conclusion_id) || expectedId !== undefined && v.survey_conclusion_id !== expectedId || !id(v.conclusion_series_id)
  || v.project_id !== projectId || !id(v.survey_id) || !ids(v.round_refs) || v.round_refs.length < 1 || !ids(v.ai_task_refs)
  || !integer(v.version_no,1) || !states.has(v.state as SurveyConclusionState) || typeof v.content_fingerprint !== "string" || !digest.test(v.content_fingerprint)
  || !integer(v.department_count) || !integer(v.module_count) || !integer(v.evidence_count) || !integer(v.open_issue_count)
  || !optionalId(v.supersedes_ref) || !optionalId(v.review_id) || !optionalId(v.review_round_id) || (v.review_id === null) !== (v.review_round_id === null)
  || !id(v.created_by) || !instant(v.created_at)) throw new SurveyConclusionError("SURVEY_CONCLUSION_UNAVAILABLE");
  return Object.freeze({...v,round_refs:Object.freeze(v.round_refs),ai_task_refs:Object.freeze(v.ai_task_refs)}) as unknown as SurveyConclusionSummary; }
function ordered<T>(values: unknown, parser: (value: unknown, ordinal: number)=>T): readonly T[] { if (!Array.isArray(values)) throw new SurveyConclusionError("SURVEY_CONCLUSION_UNAVAILABLE"); return Object.freeze(values.map(parser)); }
function parseDepartment(v: unknown, ordinal: number): DepartmentConclusion { const f=["department_id","title","statement","response_refs","ordinal"];
  if(!record(v)||!exact(v,f)||!id(v.department_id)||!text(v.title,255)||!text(v.statement,20000)||!ids(v.response_refs)||v.ordinal!==ordinal) throw new SurveyConclusionError("SURVEY_CONCLUSION_UNAVAILABLE"); return Object.freeze({...v,response_refs:Object.freeze(v.response_refs)}) as unknown as DepartmentConclusion; }
function parseModule(v: unknown, ordinal: number): ModuleConclusion { const f=["module_key","title","statement","response_refs","ordinal"];
  if(!record(v)||!exact(v,f)||!text(v.module_key,128)||!text(v.title,255)||!text(v.statement,20000)||!ids(v.response_refs)||v.ordinal!==ordinal) throw new SurveyConclusionError("SURVEY_CONCLUSION_UNAVAILABLE"); return Object.freeze({...v,response_refs:Object.freeze(v.response_refs)}) as unknown as ModuleConclusion; }
function parseEvidence(v: unknown, ordinal: number): ConclusionEvidence { const f=["reference_role","document_id","document_version_id","evidence_id","observed_evidence_lock_version","content_fingerprint","ordinal"];
  if(!record(v)||!exact(v,f)||(v.reference_role!=="SUPPORT"&&v.reference_role!=="CONFLICT")||!id(v.document_id)||!id(v.document_version_id)||!id(v.evidence_id)||!integer(v.observed_evidence_lock_version)||typeof v.content_fingerprint!=="string"||!digest.test(v.content_fingerprint)||v.ordinal!==ordinal) throw new SurveyConclusionError("SURVEY_CONCLUSION_UNAVAILABLE"); return Object.freeze({...v}) as unknown as ConclusionEvidence; }
function parseIssue(v: unknown, ordinal: number): ConclusionOpenIssue { const f=["issue_owner_module","issue_object_type","issue_id","observed_issue_state","observed_lock_version","is_blocking","ordinal"];
  if(!record(v)||!exact(v,f)||v.issue_owner_module!=="handover"||v.issue_object_type!=="HND-03"||!id(v.issue_id)||!text(v.observed_issue_state,64)||!integer(v.observed_lock_version)||typeof v.is_blocking!=="boolean"||v.ordinal!==ordinal) throw new SurveyConclusionError("SURVEY_CONCLUSION_UNAVAILABLE"); return Object.freeze({...v}) as unknown as ConclusionOpenIssue; }
export function parseSurveyConclusion(v: unknown, projectId: string, expectedId?: string): SurveyConclusionView { if(!record(v)) throw new SurveyConclusionError("SURVEY_CONCLUSION_UNAVAILABLE");
  const detailFields=[...summaryFields,"department_conclusions","module_conclusions","evidence_refs","open_issue_refs"]; if(!exact(v,detailFields)) throw new SurveyConclusionError("SURVEY_CONCLUSION_UNAVAILABLE");
  const summary=parseSummary(Object.fromEntries(summaryFields.map(k=>[k,v[k]])),projectId,expectedId); const departments=ordered(v.department_conclusions,parseDepartment);
  const modules=ordered(v.module_conclusions,parseModule); const evidence=ordered(v.evidence_refs,parseEvidence); const issues=ordered(v.open_issue_refs,parseIssue);
  if(departments.length!==summary.department_count||modules.length!==summary.module_count||evidence.length!==summary.evidence_count||issues.length!==summary.open_issue_count) throw new SurveyConclusionError("SURVEY_CONCLUSION_UNAVAILABLE");
  return Object.freeze({...summary,department_conclusions:departments,module_conclusions:modules,evidence_refs:evidence,open_issue_refs:issues}); }
function envelope(v: unknown) { if(!record(v)||!exact(v,["data","trace_id"])||!id(v.trace_id)) throw new SurveyConclusionError("SURVEY_CONCLUSION_UNAVAILABLE"); return v as {data:unknown;trace_id:string}; }
async function payload(r:Response){if(r.headers.get("Content-Type")?.split(";",1)[0].trim().toLowerCase()!=="application/json")throw new SurveyConclusionError("SURVEY_CONCLUSION_UNAVAILABLE");try{return await r.json()}catch{throw new SurveyConclusionError("SURVEY_CONCLUSION_UNAVAILABLE")}}
function failure(status:number,v:unknown):never{let code="";if(record(v)&&record(v.error)&&typeof v.error.code==="string")code=v.error.code;const known:Record<string,SurveyConclusionErrorCode>={AUTH_SESSION_EXPIRED:"AUTH_SESSION_EXPIRED",AUTH_CSRF_INVALID:"AUTH_CSRF_INVALID",LICENSE_OPERATION_DENIED:"LICENSE_OPERATION_DENIED",RESOURCE_NOT_FOUND:"RESOURCE_NOT_FOUND",PROJECT_ARCHIVED:"PROJECT_ARCHIVED",CONFLICT_IDEMPOTENCY:"CONFLICT_IDEMPOTENCY",CONFLICT_STATE:"CONFLICT_STATE",CONFLICT_VERSION:"CONFLICT_VERSION",SURVEY_CONCLUSION_SOURCE_INVALID:"SURVEY_CONCLUSION_SOURCE_INVALID",REVIEW_REVIEWER_INELIGIBLE:"REVIEW_REVIEWER_INELIGIBLE",REVIEW_SUBJECT_LOCKED:"REVIEW_SUBJECT_LOCKED"};if(code==="VALIDATION_FAILED"||code==="BUSINESS_REVIEW_NOT_ELIGIBLE")throw new SurveyConclusionError("SURVEY_CONCLUSION_INCOMPLETE");throw new SurveyConclusionError(known[code]??(status===400||status===422?"SURVEY_CONCLUSION_INVALID_INPUT":"SURVEY_CONCLUSION_UNAVAILABLE"))}
function project(v:string){if(!id(v))throw new SurveyConclusionError("SURVEY_CONCLUSION_INVALID_INPUT")}

export class SurveyConclusionReadClient { constructor(private readonly fetcher:typeof fetch=globalThis.fetch.bind(globalThis)){}
  async #get(path:string){let r:Response;try{r=await this.fetcher(path,{method:"GET",credentials:"same-origin",cache:"no-store",redirect:"error",headers:{Accept:"application/json"}})}catch{throw new SurveyConclusionError("SURVEY_CONCLUSION_UNAVAILABLE")}const v=await payload(r);if(!r.ok)failure(r.status,v);return envelope(v)}
  async list(projectId:string,pageSize=50,next:SurveyConclusionCursor|null=null):Promise<SurveyConclusionPage>{project(projectId);if(!integer(pageSize,1)||pageSize>100||next!==null&&!cursor.test(next))throw new SurveyConclusionError("SURVEY_CONCLUSION_INVALID_INPUT");const q=new URLSearchParams({page_size:String(pageSize)});if(next)q.set("next_cursor",next);const d=(await this.#get(`/api/v1/projects/${projectId}/survey-conclusions?${q}`)).data;if(!record(d)||!exact(d,["items","next_cursor","has_more"])||!Array.isArray(d.items)||d.items.length>pageSize||typeof d.has_more!=="boolean"||d.has_more!==(d.next_cursor!==null)||d.next_cursor!==null&&(typeof d.next_cursor!=="string"||!cursor.test(d.next_cursor)))throw new SurveyConclusionError("SURVEY_CONCLUSION_UNAVAILABLE");const items=d.items.map(x=>parseSummary(x,projectId));if(new Set(items.map(x=>x.survey_conclusion_id)).size!==items.length||items.some((x,i)=>i>0&&(x.created_at>items[i-1]!.created_at||x.created_at===items[i-1]!.created_at&&x.survey_conclusion_id>=items[i-1]!.survey_conclusion_id)))throw new SurveyConclusionError("SURVEY_CONCLUSION_UNAVAILABLE");return Object.freeze({items:Object.freeze(items),next_cursor:d.next_cursor as SurveyConclusionCursor|null,has_more:d.has_more})}
  async get(projectId:string,conclusionId:string){project(projectId);if(!id(conclusionId))throw new SurveyConclusionError("SURVEY_CONCLUSION_INVALID_INPUT");return parseSurveyConclusion((await this.#get(`/api/v1/projects/${projectId}/survey-conclusions/${conclusionId}`)).data,projectId,conclusionId)} }

function validInput(input:SurveyConclusionCreateInput){if(!record(input)||!exact(input,["survey_id","round_refs","department_conclusions","module_conclusions","evidence_refs","open_issue_refs","ai_task_refs","supersedes_ref"])||!id(input.survey_id)||!ids(input.round_refs)||input.round_refs.length<1||!ids(input.ai_task_refs)||!optionalId(input.supersedes_ref)||!Array.isArray(input.department_conclusions)||!Array.isArray(input.module_conclusions)||!Array.isArray(input.evidence_refs)||!Array.isArray(input.open_issue_refs))return false;const group=(x:DepartmentConclusionInput)=>record(x)&&exact(x,["department_id","title","statement","response_refs"])&&id(x.department_id)&&text(x.title,255)&&text(x.statement,20000)&&ids(x.response_refs);const module=(x:ModuleConclusionInput)=>record(x)&&exact(x,["module_key","title","statement","response_refs"])&&text(x.module_key,128)&&text(x.title,255)&&text(x.statement,20000)&&ids(x.response_refs);return input.department_conclusions.every(group)&&input.module_conclusions.every(module)&&input.evidence_refs.every(x=>record(x)&&exact(x,["evidence_id","reference_role"])&&id(x.evidence_id)&&(x.reference_role==="SUPPORT"||x.reference_role==="CONFLICT"))&&input.open_issue_refs.every(x=>record(x)&&exact(x,["action_item_id","is_blocking"])&&id(x.action_item_id)&&typeof x.is_blocking==="boolean")}
export class SurveyConclusionWriteClient { constructor(private readonly session:SessionClient){if(!(session instanceof SessionClient))throw new SurveyConclusionError("SURVEY_CONCLUSION_INVALID_INPUT")}
  async #send(projectId:string,conclusionId:string|null,operation:"create"|"validate"|"submit-review",body:unknown|null,key:string){project(projectId);if(conclusionId!==null&&!id(conclusionId)||!/^[\x20-\x7e]{16,128}$/.test(key))throw new SurveyConclusionError("SURVEY_CONCLUSION_INVALID_INPUT");let r:Response;try{r=await this.session.writeProjectSurveyConclusion(projectId,conclusionId,operation,body===null?null:JSON.stringify(body),key)}catch(e){if(e instanceof SessionClientError&&(e.code==="AUTH_RELOGIN_REQUIRED"||e.code==="AUTH_CLIENT_BUSY"))throw new SurveyConclusionError(e.code);throw new SurveyConclusionError("SURVEY_CONCLUSION_UNAVAILABLE")}const v=await payload(r);if(!r.ok)failure(r.status,v);return{r,data:envelope(v).data}}
  async create(projectId:string,input:SurveyConclusionCreateInput,key:string){if(!validInput(input))throw new SurveyConclusionError("SURVEY_CONCLUSION_INVALID_INPUT");const{r,data}=await this.#send(projectId,null,"create",input,key);const item=parseSurveyConclusion(data,projectId);if(r.status!==201||r.headers.get("Location")!==`/api/v1/projects/${projectId}/survey-conclusions/${item.survey_conclusion_id}`)throw new SurveyConclusionError("SURVEY_CONCLUSION_UNAVAILABLE");return item}
  async validate(projectId:string,conclusionId:string,key:string):Promise<SurveyConclusionValidation>{const{r,data}=await this.#send(projectId,conclusionId,"validate",null,key);const fields=["audit_event_id","survey_conclusion_id","conclusion_series_id","project_id","survey_id","version_no","state","valid","blocking_issues","warnings","coverage_summary","checked_at"] as const;const coverageFields=["department_count","module_count","evidence_count","open_issue_count","response_count","support_evidence_count","conflict_evidence_count","current_open_blocking_issue_count"] as const;if(r.status!==200||!record(data)||!exact(data,fields)||!id(data.audit_event_id)||data.survey_conclusion_id!==conclusionId||!id(data.conclusion_series_id)||data.project_id!==projectId||!id(data.survey_id)||!integer(data.version_no,1)||!states.has(data.state as SurveyConclusionState)||typeof data.valid!=="boolean"||!Array.isArray(data.blocking_issues)||data.blocking_issues.some(x=>!text(x,128))||!Array.isArray(data.warnings)||data.warnings.some(x=>!text(x,500))||!record(data.coverage_summary)||!instant(data.checked_at))throw new SurveyConclusionError("SURVEY_CONCLUSION_UNAVAILABLE");const coverage=data.coverage_summary;if(!exact(coverage,coverageFields)||coverageFields.some(x=>!integer(coverage[x])))throw new SurveyConclusionError("SURVEY_CONCLUSION_UNAVAILABLE");return Object.freeze({...data,blocking_issues:Object.freeze(data.blocking_issues),warnings:Object.freeze(data.warnings),coverage_summary:Object.freeze(coverage)}) as unknown as SurveyConclusionValidation}
  async submitReview(projectId:string,conclusionId:string,reviewerIds:readonly string[],key:string):Promise<SurveyConclusionReviewReceipt>{if(!ids(reviewerIds)||reviewerIds.length<1)throw new SurveyConclusionError("SURVEY_CONCLUSION_INVALID_INPUT");const body={reviewer_ids:[...reviewerIds],policy_ref:"SURVEY_CONCLUSION_ALL_V1",due_at:null,submission_note:null};const{r,data}=await this.#send(projectId,conclusionId,"submit-review",body,key);const fields=["review_id","review_round_id","subject_type","project_id","conclusion_series_id","survey_conclusion_id","policy_ref","reviewer_ids","state","round_no","review_etag","submitted_by","submitted_at"] as const;if(r.status!==201||!record(data)||!exact(data,fields)||!id(data.review_id)||!id(data.review_round_id)||data.subject_type!=="SRV-05"||data.project_id!==projectId||!id(data.conclusion_series_id)||data.survey_conclusion_id!==conclusionId||data.policy_ref!=="SURVEY_CONCLUSION_ALL_V1"||!ids(data.reviewer_ids)||data.reviewer_ids.length<1||data.state!=="IN_REVIEW"||!integer(data.round_no,1)||typeof data.review_etag!=="string"||!etag.test(data.review_etag)||r.headers.get("ETag")!==data.review_etag||!id(data.submitted_by)||!instant(data.submitted_at))throw new SurveyConclusionError("SURVEY_CONCLUSION_UNAVAILABLE");return Object.freeze({...data,reviewer_ids:Object.freeze(data.reviewer_ids)}) as unknown as SurveyConclusionReviewReceipt} }
