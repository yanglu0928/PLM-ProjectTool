import { flushPromises, mount } from "@vue/test-utils";
import { createMemoryHistory } from "vue-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import { createAppRouter } from "@/app/router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { EvidenceViewerClient, EvidenceViewerClientError } from "@/modules/evidence/api/evidenceViewerClient";
import { HandoverReadClient, type HandoverAnalysisItemView, type HandoverAnalysisVersionView,
  type HandoverAnalysisView } from "@/modules/handover/api/handoverReadClient";
import ProjectHandoverDetailView from "./ProjectHandoverDetailView.vue";

const project = "01234567-89ab-4cde-8123-456789abcdef"; const analysisId = "11234567-89ab-4cde-8123-456789abcdef";
const versionId = "21234567-89ab-4cde-8123-456789abcdef"; const actor = "31234567-89ab-4cde-8123-456789abcdef";
const document = "41234567-89ab-4cde-8123-456789abcdef"; const documentVersion = "51234567-89ab-4cde-8123-456789abcdef";
const evidenceId = "61234567-89ab-4cde-8123-456789abcdef"; const trace = "71234567-89ab-4cde-8123-456789abcdef";
const now = "2026-10-05T12:00:00Z";
const analysis: HandoverAnalysisView = { handover_analysis_id: analysisId, project_id: project, analysis_purpose: "项目交接分析",
  source_set_ref: `sha256:${"a".repeat(64)}`, state: "ACTIVE", current_approved_version_ref: null,
  created_by: actor, created_at: now, updated_at: now, etag: '"v0"' };
const summary: HandoverAnalysisVersionView = { handover_analysis_version_id: versionId, handover_analysis_id: analysisId,
  project_id: project, version_no: 1, state: "DRAFT", source_set_ref: `sha256:${"a".repeat(64)}`,
  capability_baseline_id: actor, capability_baseline_version_ref: trace, content_fingerprint: "b".repeat(64),
  declared_source_count: 1, declared_item_count: 1, declared_evidence_count: 1, declared_capability_ref_count: 0,
  declared_ai_task_count: 0, supersedes_version_ref: null, review_ref: null, review_round_ref: null,
  created_by: actor, created_at: now, source_documents: [], ai_tasks: [] };
const detail: HandoverAnalysisVersionView = { ...summary,
  source_documents: [{ document_id: document, document_version_id: documentVersion, ordinal: 0 }] };
const issue: HandoverAnalysisItemView = { analysis_item_id: actor, handover_analysis_version_id: versionId,
  handover_analysis_id: analysisId, project_id: project, ordinal: 0, item_type: "NEED_CONFIRM", title: "确认部署范围",
  statement: "客户实际范围尚待确认", impact: "影响工作量与计划", severity: "HIGH", priority: "URGENT",
  recommendation: "按实际范围维护", confirmation_question: "实际部署范围是什么？",
  required_input_spec: { fields: [{ name: "部署范围", format: "文本", example: "总部与华东工厂", required: true }] },
  source_missing: false, state: "CANDIDATE", evidence_refs: [evidenceId], capability_refs: [],
  options: [{ option_code: "A", label: "仅总部", description: null, ordinal: 0 },
    { option_code: "B", label: "总部和工厂", description: "覆盖两类组织", ordinal: 1 }] };
function response(data: unknown) { return new Response(JSON.stringify({ data, trace_id: trace }),
  { headers: { "Content-Type": "application/json" } }); }
async function session(restricted = false) { const api = new SessionClient(vi.fn().mockResolvedValue(response({
  user: { user_id: actor, username_display: "合成用户" }, deployment_role: "NONE", password_change_required: restricted,
  authorized_projects: restricted ? [] : [{ project_id: project, name: "合成项目", role: "PROJECT_MANAGER" }],
  absolute_expires_at: "2030-01-01T12:00:00Z", idle_expires_at: "2030-01-01T11:00:00Z", csrf_token: "a".repeat(64),
})) as typeof fetch); await api.login("user", "synthetic-only"); return api; }
function clients() { const handover = new HandoverReadClient(vi.fn() as typeof fetch); const evidence = new EvidenceViewerClient(vi.fn() as typeof fetch);
  vi.spyOn(handover, "getAnalysis").mockResolvedValue(analysis); vi.spyOn(handover, "listVersions").mockResolvedValue({
    items: [summary], next_cursor: null, has_more: false }); vi.spyOn(handover, "getVersion").mockResolvedValue(detail);
  vi.spyOn(handover, "listItems").mockResolvedValue({ items: [issue], next_cursor: null, has_more: false });
  vi.spyOn(evidence, "get").mockResolvedValue({ evidence_id: evidenceId, document_id: document,
    document_version_id: documentVersion, document_version_no: 3, detected_mime: "application/pdf", size_bytes: 100,
    locator: Object.freeze({ locator_type: "DOCUMENT" }), precision: "DOCUMENT", display_label: "整个固定文档版本",
    short_preview: "部署范围", content_url: `/api/v1/projects/${project}/documents/${document}/versions/${documentVersion}/content` });
  return { handover, evidence }; }
async function view(auth: SessionClient, supplied = clients()) { const router = createAppRouter(createMemoryHistory());
  await router.push(`/projects/${project}/handover/${analysisId}`); await router.isReady();
  const wrapper = mount(ProjectHandoverDetailView, { props: { session: auth, ...supplied }, global: { plugins: [router] } });
  await flushPromises(); return { wrapper, router, ...supplied }; }

describe("ProjectHandoverDetailView", () => {
  afterEach(() => vi.restoreAllMocks());
  it("does not read without identity or while password change is required", async () => { const supplied = clients();
    const absent = await view(new SessionClient(vi.fn() as typeof fetch), supplied); expect(absent.wrapper.text()).toContain("尚未读取当前身份");
    expect(supplied.handover.getAnalysis).not.toHaveBeenCalled(); absent.wrapper.unmount();
    const restricted = await view(await session(true), supplied); expect(restricted.wrapper.text()).toContain("须先修改密码");
    expect(supplied.handover.getAnalysis).not.toHaveBeenCalled(); restricted.wrapper.unmount(); });
  it("renders fixed Version problems, maintenance prompts, then locates Evidence on demand", async () => {
    const result = await view(await session()); expect(result.wrapper.text()).toContain("项目交接分析");
    expect(result.wrapper.text()).toContain("版本 1"); expect(result.evidence.get).not.toHaveBeenCalled();
    await result.wrapper.findAll("button").find(button => button.text().includes("版本 1 的问题"))!.trigger("click"); await flushPromises();
    expect(result.wrapper.text()).toContain("实际部署范围是什么"); expect(result.wrapper.text()).toContain("部署范围 · 必填 · 格式：文本");
    expect(result.wrapper.text()).toContain("示例仅说明格式，不是客户事实"); expect(result.wrapper.find("form").exists()).toBe(false);
    await result.wrapper.findAll("button").find(button => button.text().includes("定位原文"))!.trigger("click"); await flushPromises();
    expect(result.evidence.get).toHaveBeenCalledWith({ kind: "PROJECT", projectId: project }, evidenceId);
    expect(result.wrapper.text()).toContain("已核验的原文位置"); expect(result.wrapper.text()).toContain("整个固定文档版本");
    expect(result.wrapper.get(`a[href="/api/v1/projects/${project}/documents/${document}/versions/${documentVersion}/content"]`)
      .attributes("rel")).toBe("noopener noreferrer"); result.wrapper.unmount(); });
  it("clears a prior location when the next Evidence lookup fails", async () => { const supplied = clients();
    vi.mocked(supplied.evidence.get).mockResolvedValueOnce({ evidence_id: evidenceId, document_id: document,
      document_version_id: documentVersion, document_version_no: 3, detected_mime: "application/pdf", size_bytes: 100,
      locator: Object.freeze({ locator_type: "DOCUMENT" }), precision: "DOCUMENT", display_label: "整个固定文档版本",
      short_preview: null, content_url: `/api/v1/projects/${project}/documents/${document}/versions/${documentVersion}/content` })
      .mockRejectedValueOnce(new EvidenceViewerClientError("RESOURCE_NOT_FOUND"));
    const { wrapper } = await view(await session(), supplied); await wrapper.findAll("button").find(button => button.text().includes("版本 1 的问题"))!.trigger("click");
    await flushPromises(); const locate = () => wrapper.findAll("button").find(button => button.text().includes("定位原文"))!;
    await locate().trigger("click"); await flushPromises(); expect(wrapper.text()).toContain("已核验的原文位置");
    await locate().trigger("click"); await flushPromises(); expect(wrapper.text()).not.toContain("已核验的原文位置");
    expect(wrapper.get("[role=alert]").text()).toContain("无权查看"); wrapper.unmount(); });
});
