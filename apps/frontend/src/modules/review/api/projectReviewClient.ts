/** Frozen REVIEW_GET/DECIDE transport; client projections are not approval facts. */
import { SessionClient, SessionClientError } from "@/modules/auth/api/sessionClient";

export type ReviewState = "DRAFT" | "IN_REVIEW" | "APPROVED" | "RETURNED" | "WITHDRAWN";
export type ReviewDecisionKind = "APPROVE" | "RETURN";
export interface ReviewDecisionView { readonly decision_id: string; readonly decision: ReviewDecisionKind;
  readonly comment: string | null; readonly decided_at: string }
export interface ReviewAssignmentView { readonly assignment_id: string; readonly reviewer_id: string;
  readonly state: "PENDING" | "DECIDED"; readonly decision: ReviewDecisionView | null }
export interface ReviewRoundView { readonly review_round_id: string; readonly round_no: number;
  readonly subject_version_ref: string; readonly state: "IN_REVIEW"; readonly round_etag: string;
  readonly started_by: string; readonly started_at: string; readonly assignments: readonly ReviewAssignmentView[] }
export interface ProjectReviewView { readonly review_id: string; readonly project_id: string;
  readonly subject_ref: Readonly<{ resource_type: "SOL-06" | "SOL-05" | "SOL-03"; resource_id: string }>;
  readonly policy_code: "STRUCTURED_SPEC_ALL_V1" | "SOLUTION_SECTION_ALL_V1" | "SOLUTION_OUTLINE_ALL_V1"; readonly state: ReviewState;
  readonly active_round: ReviewRoundView | null; readonly etag: string }
export interface ReviewDecisionReceipt { readonly review_id: string; readonly review_round_id: string;
  readonly subject_version_ref: string; readonly actor_id: string; readonly state: ReviewState;
  readonly etag: string; readonly round_etag: string; readonly occurred_at: string;
  readonly event_id: string; readonly assignment_state: "DECIDED";
  readonly decision: ReviewDecisionKind; readonly decision_id: string }

const messages = {
  REVIEW_INVALID: "项目、评审或决定信息无效。", AUTH_SESSION_EXPIRED: "会话已失效，请重新登录。",
  AUTH_CSRF_INVALID: "登录状态已变化，请重新登录。", LICENSE_OPERATION_DENIED: "当前许可不允许读取或处理评审。",
  RESOURCE_NOT_FOUND: "评审不存在、已变化，或当前账户无权处理。", VALIDATION_FAILED: "评审请求不符合冻结合同。",
  REVIEW_COMMENT_REQUIRED: "退回时必须填写明确意见。", REVIEW_DECISION_EXISTS: "当前评审人已经完成决定。",
  CONFLICT_IDEMPOTENCY: "原操作号与本次决定不一致，已停止重试。", CONFLICT_STATE: "评审状态已变化，请刷新。",
  REVIEW_UNAVAILABLE: "暂时无法确认评审状态；请保留原决定和操作号。",
  AUTH_RELOGIN_REQUIRED: "请重新登录后再处理评审。", AUTH_CLIENT_BUSY: "账户正在处理其他操作，请稍候。",
} as const;
export type ProjectReviewErrorCode = keyof typeof messages;
export class ProjectReviewError extends Error {
  readonly uncertain: boolean;
  constructor(readonly code: ProjectReviewErrorCode) { super(messages[code]); this.name = "ProjectReviewError";
    this.uncertain = code === "REVIEW_UNAVAILABLE"; }
}

const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const etag = /^"v(0|[1-9]\d*)"$/; const stamp = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$/;
const reviewFields = ["review_id","project_id","subject_ref","policy_code","state","active_round","etag"];
const roundFields = ["review_round_id","round_no","subject_version_ref","state","round_etag","started_by","started_at","assignments"];
const assignmentFields = ["assignment_id","reviewer_id","state","decision"];
const decisionFields = ["decision_id","decision","comment","decided_at"];
const receiptFields = ["review_id","review_round_id","subject_version_ref","actor_id","state","etag","round_etag","occurred_at","event_id","assignment_state","decision","decision_id"];
function record(v:unknown):v is Record<string,unknown>{return typeof v==="object"&&v!==null&&!Array.isArray(v)}
function exact(v:Record<string,unknown>,f:readonly string[]){return Object.keys(v).length===f.length&&f.every(k=>Object.hasOwn(v,k))}
function id(v:unknown):v is string{return typeof v==="string"&&uuid.test(v)&&v!=="00000000-0000-0000-0000-000000000000"}
function instant(v:unknown):v is string{return typeof v==="string"&&stamp.test(v)&&Number.isFinite(Date.parse(v))}
function fail(code:ProjectReviewErrorCode="REVIEW_UNAVAILABLE"):never{throw new ProjectReviewError(code)}
function parseDecision(v:unknown):ReviewDecisionView|null{if(v===null)return null;if(!record(v)||!exact(v,decisionFields)||!id(v.decision_id)||!["APPROVE","RETURN"].includes(String(v.decision))||(v.comment!==null&&typeof v.comment!=="string")||v.decision==="RETURN"&&!(v.comment as string)?.trim()||!instant(v.decided_at))fail();return Object.freeze({...v}) as unknown as ReviewDecisionView}
function parseRound(v:unknown):ReviewRoundView|null{if(v===null)return null;if(!record(v)||!exact(v,roundFields)||!id(v.review_round_id)||!Number.isSafeInteger(v.round_no)||Number(v.round_no)<1||!id(v.subject_version_ref)||v.state!=="IN_REVIEW"||!etag.test(String(v.round_etag))||!id(v.started_by)||!instant(v.started_at)||!Array.isArray(v.assignments)||v.assignments.length<1||v.assignments.length>32)fail();const seen=new Set<string>();const assignments=v.assignments.map(item=>{if(!record(item)||!exact(item,assignmentFields)||!id(item.assignment_id)||!id(item.reviewer_id)||seen.has(item.reviewer_id)||!["PENDING","DECIDED"].includes(String(item.state)))fail();seen.add(item.reviewer_id);const decision=parseDecision(item.decision);if((item.state==="PENDING")!==(decision===null))fail();return Object.freeze({...item,decision}) as unknown as ReviewAssignmentView});return Object.freeze({...v,assignments:Object.freeze(assignments)}) as unknown as ReviewRoundView}
function parseReview(v:unknown,project:string,review:string):ProjectReviewView{if(!record(v)||!exact(v,reviewFields)||v.review_id!==review||v.project_id!==project||!record(v.subject_ref)||!exact(v.subject_ref,["resource_type","resource_id"])||!id(v.subject_ref.resource_id)||!((v.subject_ref.resource_type==="SOL-06"&&v.policy_code==="STRUCTURED_SPEC_ALL_V1")||(v.subject_ref.resource_type==="SOL-05"&&v.policy_code==="SOLUTION_SECTION_ALL_V1")||(v.subject_ref.resource_type==="SOL-03"&&v.policy_code==="SOLUTION_OUTLINE_ALL_V1"))||!["DRAFT","IN_REVIEW","APPROVED","RETURNED","WITHDRAWN"].includes(String(v.state))||!etag.test(String(v.etag)))fail();const active=parseRound(v.active_round);if((v.state==="IN_REVIEW")!==(active!==null))fail();return Object.freeze({...v,subject_ref:Object.freeze({...v.subject_ref}),active_round:active}) as unknown as ProjectReviewView}
async function body(response:Response):Promise<Record<string,unknown>>{if(response.headers.get("content-type")?.split(";")[0].trim().toLowerCase()!=="application/json"||response.headers.get("cache-control")!=="no-store")fail();const value:unknown=await response.json();if(!record(value)||!id(value.trace_id)||response.headers.get("x-trace-id")!==value.trace_id)fail();return value}

export class ProjectReviewClient {
  constructor(private readonly session:SessionClient,private readonly fetcher:typeof fetch=(input,init)=>fetch(input,init),private readonly timeoutMs=10_000){if(!(session instanceof SessionClient)||!Number.isInteger(timeoutMs)||timeoutMs<1||timeoutMs>30_000)fail("REVIEW_INVALID")}
  async read(project:string,review:string):Promise<ProjectReviewView>{if(!id(project)||!id(review))fail("REVIEW_INVALID");const controller=new AbortController();const timer=setTimeout(()=>controller.abort(),this.timeoutMs);try{const response=await this.fetcher(`/api/v1/projects/${project}/reviews/${review}`,{method:"GET",credentials:"same-origin",cache:"no-store",redirect:"error",headers:{Accept:"application/json"},signal:controller.signal});if(controller.signal.aborted)fail();const value=await body(response);if(response.status!==200){const code=record(value.error)?value.error.code:null;const statuses:Record<string,number>={AUTH_SESSION_EXPIRED:401,LICENSE_OPERATION_DENIED:403,RESOURCE_NOT_FOUND:404,VALIDATION_FAILED:422};if(typeof code==="string"&&statuses[code]===response.status)fail(code as ProjectReviewErrorCode);fail()}if(!exact(value,["data","trace_id"])||response.headers.get("etag")!==(record(value.data)?value.data.etag:null))fail();return parseReview(value.data,project,review)}catch(e){if(e instanceof ProjectReviewError)throw e;return fail()}finally{clearTimeout(timer)}}
  async decide(before:ProjectReviewView,kind:ReviewDecisionKind,comment:string|null,key:string):Promise<ReviewDecisionReceipt>{const view=this.session.view,round=before.active_round;if(!view||view.password_change_required||!this.session.canSubmit||before.state!=="IN_REVIEW"||!round||!round.assignments.some(a=>a.reviewer_id===view.user.user_id&&a.state==="PENDING")||!["APPROVE","RETURN"].includes(kind)||kind==="RETURN"&&(typeof comment!=="string"||!comment.trim())||kind==="APPROVE"&&comment!==null||typeof key!=="string"||!/^[\x20-\x7e]{16,128}$/.test(key))fail("REVIEW_INVALID");const normalized=kind==="RETURN"?comment!.trim():null;let response:Response;try{response=await this.session.postProjectReviewDecision(before.project_id,before.review_id,round.review_round_id,JSON.stringify({decision:kind,comment:normalized}),key)}catch(e){if(e instanceof SessionClientError&&(e.code==="AUTH_RELOGIN_REQUIRED"||e.code==="AUTH_CLIENT_BUSY"))throw new ProjectReviewError(e.code);return fail()}const value=await body(response);if(response.status!==200){const code=record(value.error)?value.error.code:null;const statuses:Record<string,number>={AUTH_SESSION_EXPIRED:401,AUTH_CSRF_INVALID:403,LICENSE_OPERATION_DENIED:403,RESOURCE_NOT_FOUND:404,VALIDATION_FAILED:422,REVIEW_COMMENT_REQUIRED:422,REVIEW_DECISION_EXISTS:409,CONFLICT_IDEMPOTENCY:409,CONFLICT_STATE:409,REVIEW_UNAVAILABLE:503};if(typeof code==="string"&&statuses[code]===response.status)fail(code as ProjectReviewErrorCode);fail()}if(!exact(value,["data","trace_id"])||!record(value.data)||!exact(value.data,receiptFields))fail();const d=value.data;if(d.review_id!==before.review_id||d.review_round_id!==round.review_round_id||d.subject_version_ref!==round.subject_version_ref||d.actor_id!==view.user.user_id||!["IN_REVIEW","APPROVED","RETURNED"].includes(String(d.state))||!etag.test(String(d.etag))||!etag.test(String(d.round_etag))||response.headers.get("etag")!==d.etag||!instant(d.occurred_at)||!id(d.event_id)||d.assignment_state!=="DECIDED"||d.decision!==kind||!id(d.decision_id))fail();return Object.freeze({...d}) as unknown as ReviewDecisionReceipt}
}
