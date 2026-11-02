import { describe,expect,it,vi } from "vitest";
import { HandoverActionSourceLocationClient,HandoverActionSourceLocationError,parseHandoverActionSourceLocation } from "./handoverActionSourceLocationClient";
const project="01234567-89ab-4cde-8123-456789abcdef",action="11234567-89ab-4cde-8123-456789abcdef",analysis="21234567-89ab-4cde-8123-456789abcdef",version="31234567-89ab-4cde-8123-456789abcdef",item="41234567-89ab-4cde-8123-456789abcdef",trace="51234567-89ab-4cde-8123-456789abcdef";
const target={project_id:project,handover_analysis_id:analysis,handover_analysis_version_id:version,analysis_item_id:item};
function response(data:unknown,status=200){return new Response(JSON.stringify({data,trace_id:trace}),{status,headers:{"Content-Type":"application/json"}})}
describe("HandoverActionSourceLocationClient",()=>{
 it("accepts only a project-bound immutable target",()=>{expect(parseHandoverActionSourceLocation({source_kind:"ANALYSIS_ITEM",resolution_state:"LOCATABLE",target,unavailable_reason:null},project).target).toEqual(target);
 expect(()=>parseHandoverActionSourceLocation({source_kind:"ANALYSIS_ITEM",resolution_state:"LOCATABLE",target:{...target,project_id:action},unavailable_reason:null},project)).toThrow(HandoverActionSourceLocationError);
 expect(()=>parseHandoverActionSourceLocation({source_kind:"ANALYSIS_ITEM",resolution_state:"LOCATABLE",target:{...target,extra:"path"},unavailable_reason:null},project)).toThrow(HandoverActionSourceLocationError)});
 it("represents a human source without inventing a link",()=>expect(parseHandoverActionSourceLocation({source_kind:"HUMAN",resolution_state:"UNAVAILABLE",target:null,unavailable_reason:"MANUAL_SOURCE_NOT_FIXED"},project).target).toBeNull());
 it("requests the action-bound endpoint with no-store and same-origin credentials",async()=>{const fetcher=vi.fn().mockResolvedValue(response({source_kind:"ANALYSIS_ITEM",resolution_state:"LOCATABLE",target,unavailable_reason:null}));
 const client=new HandoverActionSourceLocationClient(fetcher as typeof fetch);await client.get(project,action);expect(fetcher).toHaveBeenCalledWith(`/api/v1/projects/${project}/handover-action-items/${action}/source-location`,expect.objectContaining({credentials:"same-origin",cache:"no-store",redirect:"error"}))});
 it("fails closed on malformed payload",async()=>{const c=new HandoverActionSourceLocationClient(vi.fn().mockResolvedValue(response({bad:true})) as typeof fetch);await expect(c.get(project,action)).rejects.toBeInstanceOf(HandoverActionSourceLocationError)});
});
