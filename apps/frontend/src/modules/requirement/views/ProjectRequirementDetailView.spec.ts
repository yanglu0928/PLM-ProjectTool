import { flushPromises, mount } from "@vue/test-utils";
import { createMemoryHistory } from "vue-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { createAppRouter } from "@/app/router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { EvidenceViewerClient } from "@/modules/evidence/api/evidenceViewerClient";
import { RequirementReadClient, RequirementReadError, type RequirementVersionView,
  type RequirementView } from "@/modules/requirement/api/requirementReadClient";
import ProjectRequirementDetailView from "./ProjectRequirementDetailView.vue";

const project = "01234567-89ab-4cde-8123-456789abcdef"; const requirementId = "11234567-89ab-4cde-8123-456789abcdef";
const versionId = "21234567-89ab-4cde-8123-456789abcdef"; const actor = "31234567-89ab-4cde-8123-456789abcdef";
const sourceId = "41234567-89ab-4cde-8123-456789abcdef"; const sourceVersion = "51234567-89ab-4cde-8123-456789abcdef";
const evidenceId = "61234567-89ab-4cde-8123-456789abcdef"; const document = "71234567-89ab-4cde-8123-456789abcdef";
const documentVersion = "81234567-89ab-4cde-8123-456789abcdef"; const baseline = "91234567-89ab-4cde-8123-456789abcdef";
const capability = "a1234567-89ab-4cde-8123-456789abcdef"; const task = "b1234567-89ab-4cde-8123-456789abcdef";
const trace = "c1234567-89ab-4cde-8123-456789abcdef"; const now = "2026-10-08T12:00:00Z";
const root: RequirementView = { requirement_id: requirementId, project_id: project, requirement_code: "REQ-001", state: "ACTIVE",
  current_approved_version_ref: null, created_by: actor, created_at: now, updated_by: null, updated_at: now, etag: '"v0"' };
const detail: RequirementVersionView = { requirement_version_id: versionId, requirement_id: requirementId, project_id: project,
  version_no: 1, state: "DRAFT", title: "图文档案审批", domain_name: "文档管理", priority: "HIGH", risk: "MEDIUM",
  classification: "PENDING_CONFIRMATION", content_fingerprint: "a".repeat(64), supersedes_version_ref: null, review_ref: null,
  review_round_ref: null, created_by: actor, created_at: now, statement: "系统应支持图文档案审批。", rationale: "来自已确认访谈。",
  declared_counts: { sources: 2, acceptance_criteria: 1, capability_assessments: 1, assumptions: 1, exclusions: 1, dependencies: 1, ai_tasks: 1 },
  sources: [{ ordinal: 0, source_type: "CONFIRMED_HANDOVER", source_object_id: sourceId, source_version_ref: sourceVersion,
    evidence_refs: [{ evidence_id: evidenceId, ordinal: 0 }] }, { ordinal: 1, source_type: "HUMAN_DECISION", source_object_id: actor,
    source_version_ref: null, evidence_refs: [{ evidence_id: evidenceId, ordinal: 0 }] }],
  acceptance_criteria: [{ ordinal: 0, acceptance_criterion_ref: null, observable_result: "形成批准记录", verification_method: "审批测试", required_data: "图文档案",
    required_environment: "Windows 11", evidence_requirement: "保留审计证据" }],
  capability_assessments: [{ ordinal: 0, baseline_version_id: baseline, capability_item_id: capability, match_type: "PARTIAL",
    fit_gap: "需扩展字段", constraints_text: "不破坏冻结 API", assessor_kind: "HUMAN", assessed_by: actor, assessed_at: now,
    confirmation_state: "CANDIDATE", evidence_refs: [{ evidence_id: evidenceId, evidence_role: "SOURCE", ordinal: 0 }] }],
  assumptions: [{ ordinal: 0, text: "客户提供测试数据" }], exclusions: [{ ordinal: 0, text: "不含移动端" }],
  dependencies: [{ ordinal: 0, text: "依赖文档服务" }], ai_tasks: [{ ai_task_id: task, ordinal: 0 }] };
function response(data: unknown) { return new Response(JSON.stringify({ data, trace_id: trace }), { headers: { "Content-Type": "application/json" } }); }
async function session(restricted = false) { const api = new SessionClient(vi.fn().mockResolvedValue(response({
  user: { user_id: actor, username_display: "合成用户" }, deployment_role: "NONE", password_change_required: restricted,
  authorized_projects: restricted ? [] : [{ project_id: project, name: "合成项目", role: "PROJECT_MANAGER" }],
  absolute_expires_at: "2030-01-01T12:00:00Z", idle_expires_at: "2030-01-01T11:00:00Z", csrf_token: "a".repeat(64),
})) as typeof fetch); await api.login("user", "synthetic-only"); return api; }
function clients() { const requirements = new RequirementReadClient(vi.fn() as typeof fetch);
  vi.spyOn(requirements, "getRequirement").mockResolvedValue(root); vi.spyOn(requirements, "listVersions").mockResolvedValue({ items: [detail], next_cursor: null, has_more: false });
  vi.spyOn(requirements, "getVersion").mockResolvedValue(detail); const evidence = new EvidenceViewerClient(vi.fn() as typeof fetch);
  vi.spyOn(evidence, "get").mockResolvedValue({ evidence_id: evidenceId, document_id: document, document_version_id: documentVersion,
    document_version_no: 2, detected_mime: "application/pdf", size_bytes: 100, locator: { locator_type: "PAGE", page_no: 3 },
    precision: "PARSED_NODE", display_label: "第 3 页 · 审批结论", short_preview: "客户确认审批记录",
    content_url: `/api/v1/projects/${project}/documents/${document}/versions/${documentVersion}/content` }); return { requirements, evidence }; }
async function view(auth: SessionClient, bundle = clients()) { const router = createAppRouter(createMemoryHistory());
  await router.push(`/projects/${project}/requirements/${requirementId}`); await router.isReady();
  const wrapper = mount(ProjectRequirementDetailView, { props: { session: auth, ...bundle }, global: { plugins: [router] } });
  await flushPromises(); return { wrapper, router, ...bundle }; }

describe("ProjectRequirementDetailView", () => {
  afterEach(() => vi.restoreAllMocks());
  it("does not read without identity or before password change", async () => { const bundle = clients();
    const absent = await view(new SessionClient(vi.fn() as typeof fetch), bundle); expect(absent.wrapper.text()).toContain("尚未读取当前身份"); expect(bundle.requirements.getRequirement).not.toHaveBeenCalled(); absent.wrapper.unmount();
    const restricted = await view(await session(true), bundle); expect(restricted.wrapper.text()).toContain("须先修改密码"); expect(bundle.requirements.getRequirement).not.toHaveBeenCalled(); restricted.wrapper.unmount(); });
  it("layers version reads and explains every field that needs maintenance", async () => { const result = await view(await session());
    expect(result.requirements.getVersion).not.toHaveBeenCalled(); await result.wrapper.findAll("button").find(button => button.text().includes("详情与原文入口"))!.trigger("click"); await flushPromises();
    const text = result.wrapper.text(); expect(text).toContain("确认完成前不得作为正式业务事实"); expect(text).toContain("可观察结果");
    expect(text).toContain("验证方法"); expect(text).toContain("所需数据"); expect(text).toContain("所需环境"); expect(text).toContain("证据要求");
    expect(text).toContain("需要人工确认"); expect(text).toContain("假设"); expect(text).toContain("排除项"); expect(text).toContain("依赖");
    expect(text).toContain("AI 建议任务"); expect(result.wrapper.find("form").exists()).toBe(false); result.wrapper.unmount(); });
  it("locates evidence only after explicit click and links to the business record", async () => { const result = await view(await session());
    await result.wrapper.findAll("button").find(button => button.text().includes("详情与原文入口"))!.trigger("click"); await flushPromises();
    expect(result.evidence.get).not.toHaveBeenCalled(); expect(result.wrapper.get(`a[href^="/projects/${project}/handover/${sourceId}"]`).text()).toContain("业务记录");
    await result.wrapper.findAll("button").find(button => button.text().includes("定位该来源"))!.trigger("click"); await flushPromises();
    expect(result.evidence.get).toHaveBeenCalledWith({ kind: "PROJECT", projectId: project }, evidenceId);
    expect(result.wrapper.text()).toContain("第 3 页 · 审批结论"); expect(result.wrapper.text()).toContain("不是权威正文");
    expect(result.wrapper.get(`a[href="/api/v1/projects/${project}/documents/${document}/versions/${documentVersion}/content"]`).text()).toContain("固定版本原文"); result.wrapper.unmount(); });
  it("clears selected detail after a later denied read", async () => { const bundle = clients(); vi.mocked(bundle.requirements.getVersion)
    .mockResolvedValueOnce(detail).mockRejectedValueOnce(new RequirementReadError("RESOURCE_NOT_FOUND")); const { wrapper } = await view(await session(), bundle);
    const choose = () => wrapper.findAll("button").find(button => button.text().includes("详情与原文入口"))!;
    await choose().trigger("click"); await flushPromises(); expect(wrapper.text()).toContain("系统应支持图文档案审批");
    await choose().trigger("click"); await flushPromises(); expect(wrapper.text()).not.toContain("系统应支持图文档案审批"); expect(wrapper.get("[role=alert]").text()).toContain("无权查看"); wrapper.unmount(); });
});
