import { describe, expect, it, vi } from "vitest";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { SurveyConclusionError, SurveyConclusionReadClient, SurveyConclusionWriteClient,
  type SurveyConclusionCreateInput } from "./surveyConclusionClient";

const actor="01234567-89ab-4cde-8123-456789abcdef",project="11234567-89ab-4cde-8123-456789abcdef";
const survey="21234567-89ab-4cde-8123-456789abcdef",round="31234567-89ab-4cde-8123-456789abcdef";
const conclusion="41234567-89ab-4cde-8123-456789abcdef",series="51234567-89ab-4cde-8123-456789abcdef";
const department="61234567-89ab-4cde-8123-456789abcdef",responseId="71234567-89ab-4cde-8123-456789abcdef";
const evidence="81234567-89ab-4cde-8123-456789abcdef",documentId="91234567-89ab-4cde-8123-456789abcdef";
const documentVersion="a1234567-89ab-4cde-8123-456789abcdef",action="b1234567-89ab-4cde-8123-456789abcdef";
const trace="c1234567-89ab-4cde-8123-456789abcdef",now="2026-10-07T12:00:00Z";
function summary(){return{survey_conclusion_id:conclusion,conclusion_series_id:series,project_id:project,survey_id:survey,
  round_refs:[round],ai_task_refs:[],version_no:1,state:"DRAFT",content_fingerprint:"a".repeat(64),department_count:1,
  module_count:1,evidence_count:1,open_issue_count:1,supersedes_ref:null,review_id:null,review_round_id:null,
  created_by:actor,created_at:now}}
function detail(){return{...summary(),department_conclusions:[{department_id:department,title:"业务范围",statement:"以现场记录为准。",response_refs:[responseId],ordinal:0}],
  module_conclusions:[{module_key:"BOM",title:"BOM结论",statement:"采用标准能力。",response_refs:[responseId],ordinal:0}],
  evidence_refs:[{reference_role:"SUPPORT",document_id:documentId,document_version_id:documentVersion,evidence_id:evidence,
    observed_evidence_lock_version:0,content_fingerprint:"b".repeat(64),ordinal:0}],open_issue_refs:[{issue_owner_module:"handover",
    issue_object_type:"HND-03",issue_id:action,observed_issue_state:"OPEN",observed_lock_version:0,is_blocking:true,ordinal:0}]}}
function json(data:unknown,status=200,headers:Record<string,string>={}){return new Response(JSON.stringify({data,trace_id:trace}),{status,headers:{"Content-Type":"application/json",...headers}})}
function login(){return json({user:{user_id:actor,username_display:"项目经理"},deployment_role:"NONE",password_change_required:false,
  authorized_projects:[{project_id:project,name:"项目",role:"PROJECT_MANAGER"}],absolute_expires_at:"2030-01-01T12:00:00Z",
  idle_expires_at:"2030-01-01T11:00:00Z",csrf_token:"a".repeat(64)})}
const input:SurveyConclusionCreateInput={survey_id:survey,round_refs:[round],department_conclusions:[{department_id:department,
  title:"业务范围",statement:"以现场记录为准。",response_refs:[responseId]}],module_conclusions:[{module_key:"BOM",title:"BOM结论",
  statement:"采用标准能力。",response_refs:[responseId]}],evidence_refs:[{evidence_id:evidence,reference_role:"SUPPORT"}],
  open_issue_refs:[{action_item_id:action,is_blocking:true}],ai_task_refs:[],supersedes_ref:null};

describe("SurveyConclusion clients",()=>{
  it("strictly reads a bound keyset page and detail",async()=>{const fetcher=vi.fn().mockResolvedValueOnce(json({items:[summary()],next_cursor:null,has_more:false})).mockResolvedValueOnce(json(detail()));const api=new SurveyConclusionReadClient(fetcher as typeof fetch);await expect(api.list(project,50)).resolves.toMatchObject({has_more:false,items:[{survey_conclusion_id:conclusion}]});await expect(api.get(project,conclusion)).resolves.toMatchObject({module_conclusions:[{module_key:"BOM"}],open_issue_refs:[{issue_id:action}]});expect(fetcher.mock.calls[0]![0]).toBe(`/api/v1/projects/${project}/survey-conclusions?page_size=50`);expect(fetcher.mock.calls[1]![0]).toBe(`/api/v1/projects/${project}/survey-conclusions/${conclusion}`)});
  it("rejects an expanded or internally inconsistent response",async()=>{const expanded={...summary(),secret:"no"};const api=new SurveyConclusionReadClient(vi.fn().mockResolvedValue(json({items:[expanded],next_cursor:null,has_more:false})) as typeof fetch);await expect(api.list(project)).rejects.toMatchObject({code:"SURVEY_CONCLUSION_UNAVAILABLE"});const mismatch={...detail(),department_count:2};await expect(new SurveyConclusionReadClient(vi.fn().mockResolvedValue(json(mismatch)) as typeof fetch).get(project,conclusion)).rejects.toBeInstanceOf(SurveyConclusionError)});
  it("creates once with the exact frozen body, csrf and idempotency key",async()=>{const fetcher=vi.fn().mockResolvedValueOnce(login()).mockResolvedValueOnce(json(detail(),201,{Location:`/api/v1/projects/${project}/survey-conclusions/${conclusion}`}));const session=new SessionClient(fetcher as typeof fetch);await session.login("manager","synthetic");const api=new SurveyConclusionWriteClient(session);const key="survey-conclusion-create-0001";await expect(api.create(project,input,key)).resolves.toMatchObject({survey_conclusion_id:conclusion});const call=fetcher.mock.calls[1]!,init=call[1] as RequestInit;expect(call[0]).toBe(`/api/v1/projects/${project}/survey-conclusions`);expect(init.method).toBe("POST");expect(init.body).toBe(JSON.stringify(input));expect(init.headers).toMatchObject({"X-CSRF-Token":"a".repeat(64),"Idempotency-Key":key,"Content-Type":"application/json"})});
  it("validates with a genuinely empty request and parses coverage",async()=>{const report={audit_event_id:evidence,survey_conclusion_id:conclusion,conclusion_series_id:series,project_id:project,survey_id:survey,version_no:1,state:"DRAFT",valid:true,blocking_issues:[],warnings:[],coverage_summary:{department_count:1,module_count:1,evidence_count:1,open_issue_count:1,response_count:1,support_evidence_count:1,conflict_evidence_count:0,current_open_blocking_issue_count:0},checked_at:now};const fetcher=vi.fn().mockResolvedValueOnce(login()).mockResolvedValueOnce(json(report));const session=new SessionClient(fetcher as typeof fetch);await session.login("manager","synthetic");const api=new SurveyConclusionWriteClient(session);await expect(api.validate(project,conclusion,"survey-conclusion-validate-01")).resolves.toMatchObject({valid:true});const init=fetcher.mock.calls[1]![1] as RequestInit;expect(init).not.toHaveProperty("body");expect(init.headers).not.toHaveProperty("Content-Type")});
  it("parses the fixed all-members review receipt and response ETag",async()=>{const reviewer="d1234567-89ab-4cde-8123-456789abcdef",review="e1234567-89ab-4cde-8123-456789abcdef",reviewRound="f1234567-89ab-4cde-8123-456789abcdef";const receipt={review_id:review,review_round_id:reviewRound,subject_type:"SRV-05",project_id:project,conclusion_series_id:series,survey_conclusion_id:conclusion,policy_ref:"SURVEY_CONCLUSION_ALL_V1",reviewer_ids:[reviewer],state:"IN_REVIEW",round_no:1,review_etag:'"v1"',submitted_by:actor,submitted_at:now};const fetcher=vi.fn().mockResolvedValueOnce(login()).mockResolvedValueOnce(json(receipt,201,{ETag:'"v1"'}));const session=new SessionClient(fetcher as typeof fetch);await session.login("manager","synthetic");const api=new SurveyConclusionWriteClient(session);await expect(api.submitReview(project,conclusion,[reviewer],"survey-conclusion-review-001")).resolves.toMatchObject({subject_type:"SRV-05",review_etag:'"v1"'});expect(JSON.parse(String((fetcher.mock.calls[1]![1] as RequestInit).body))).toEqual({reviewer_ids:[reviewer],policy_ref:"SURVEY_CONCLUSION_ALL_V1",due_at:null,submission_note:null})});
});
