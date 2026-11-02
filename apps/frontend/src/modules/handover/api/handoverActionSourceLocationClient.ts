export type HandoverActionSourceKind = "ANALYSIS_ITEM" | "HUMAN";
export interface HandoverActionSourceTarget { readonly project_id: string; readonly handover_analysis_id: string; readonly handover_analysis_version_id: string; readonly analysis_item_id: string; }
export interface HandoverActionSourceLocation { readonly source_kind: HandoverActionSourceKind; readonly resolution_state: "LOCATABLE" | "UNAVAILABLE"; readonly target: HandoverActionSourceTarget | null; readonly unavailable_reason: "MANUAL_SOURCE_NOT_FIXED" | null; }
const uuid=/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const messages={AUTH_SESSION_EXPIRED:"会话已失效，请重新登录。",LICENSE_OPERATION_DENIED:"当前许可不允许定位交接来源。",RESOURCE_NOT_FOUND:"来源不存在，或当前账户无权查看。",HANDOVER_ACTION_SOURCE_UNAVAILABLE:"暂时无法定位待办来源，请稍后重试。"} as const;
export type HandoverActionSourceLocationErrorCode=keyof typeof messages;
export class HandoverActionSourceLocationError extends Error { constructor(readonly code:HandoverActionSourceLocationErrorCode){super(messages[code]);this.name="HandoverActionSourceLocationError";} }
function record(value:unknown):value is Record<string,unknown>{return typeof value==="object"&&value!==null&&!Array.isArray(value)}
function exact(value:Record<string,unknown>,keys:readonly string[]):boolean{return Object.keys(value).length===keys.length&&keys.every(key=>Object.hasOwn(value,key))}
function id(value:unknown):value is string{return typeof value==="string"&&uuid.test(value)&&value!=="00000000-0000-0000-0000-000000000000"}
export function parseHandoverActionSourceLocation(value:unknown,projectId:string):HandoverActionSourceLocation{
 if(!id(projectId)||!record(value)||!exact(value,["source_kind","resolution_state","target","unavailable_reason"]))throw new HandoverActionSourceLocationError("HANDOVER_ACTION_SOURCE_UNAVAILABLE");
 if(value.source_kind==="HUMAN"&&value.resolution_state==="UNAVAILABLE"&&value.target===null&&value.unavailable_reason==="MANUAL_SOURCE_NOT_FIXED")return Object.freeze({source_kind:"HUMAN",resolution_state:"UNAVAILABLE",target:null,unavailable_reason:"MANUAL_SOURCE_NOT_FIXED"});
 if(value.source_kind!=="ANALYSIS_ITEM"||value.resolution_state!=="LOCATABLE"||value.unavailable_reason!==null||!record(value.target)||!exact(value.target,["project_id","handover_analysis_id","handover_analysis_version_id","analysis_item_id"])||value.target.project_id!==projectId||!id(value.target.handover_analysis_id)||!id(value.target.handover_analysis_version_id)||!id(value.target.analysis_item_id))throw new HandoverActionSourceLocationError("HANDOVER_ACTION_SOURCE_UNAVAILABLE");
 return Object.freeze({source_kind:"ANALYSIS_ITEM",resolution_state:"LOCATABLE",target:Object.freeze({project_id:projectId,handover_analysis_id:value.target.handover_analysis_id,handover_analysis_version_id:value.target.handover_analysis_version_id,analysis_item_id:value.target.analysis_item_id}),unavailable_reason:null});
}
export class HandoverActionSourceLocationClient{
 constructor(private readonly fetcher:typeof fetch=fetch,private readonly timeoutMs=10_000){if(!Number.isInteger(timeoutMs)||timeoutMs<1||timeoutMs>30_000)throw new HandoverActionSourceLocationError("HANDOVER_ACTION_SOURCE_UNAVAILABLE")}
 async get(projectId:string,actionItemId:string):Promise<HandoverActionSourceLocation>{
  if(!id(projectId)||!id(actionItemId))throw new HandoverActionSourceLocationError("HANDOVER_ACTION_SOURCE_UNAVAILABLE");
  const controller=new AbortController(),timer=window.setTimeout(()=>controller.abort(),this.timeoutMs);
  try{const fetcher=this.fetcher;const response=await fetcher(`/api/v1/projects/${projectId}/handover-action-items/${actionItemId}/source-location`,{method:"GET",credentials:"same-origin",cache:"no-store",redirect:"error",headers:{Accept:"application/json"},signal:controller.signal});
   if(controller.signal.aborted||response.headers.get("content-type")?.split(";")[0].trim().toLowerCase()!=="application/json")throw new HandoverActionSourceLocationError("HANDOVER_ACTION_SOURCE_UNAVAILABLE");
   const payload:unknown=await response.json();if(!record(payload)||!id(payload.trace_id))throw new HandoverActionSourceLocationError("HANDOVER_ACTION_SOURCE_UNAVAILABLE");
   if(response.status!==200){const code=record(payload.error)?payload.error.code:null;const expected:Readonly<Record<string,number>>={AUTH_SESSION_EXPIRED:401,LICENSE_OPERATION_DENIED:403,RESOURCE_NOT_FOUND:404};if(typeof code==="string"&&expected[code]===response.status)throw new HandoverActionSourceLocationError(code as HandoverActionSourceLocationErrorCode);throw new HandoverActionSourceLocationError("HANDOVER_ACTION_SOURCE_UNAVAILABLE")}
   return parseHandoverActionSourceLocation(payload.data,projectId);
  }catch(failure){if(failure instanceof HandoverActionSourceLocationError)throw failure;throw new HandoverActionSourceLocationError("HANDOVER_ACTION_SOURCE_UNAVAILABLE")}finally{window.clearTimeout(timer)}
 }
}
