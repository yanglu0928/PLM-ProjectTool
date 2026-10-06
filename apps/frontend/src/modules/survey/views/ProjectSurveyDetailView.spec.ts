import { flushPromises, mount } from "@vue/test-utils";
import { createMemoryHistory } from "vue-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { createAppRouter } from "@/app/router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { SurveyReadClient, SurveyReadError, type SurveySourceView,
  type SurveyVersionView, type SurveyView } from "@/modules/survey/api/surveyReadClient";
import ProjectSurveyDetailView from "./ProjectSurveyDetailView.vue";

const project = "01234567-89ab-4cde-8123-456789abcdef"; const surveyId = "11234567-89ab-4cde-8123-456789abcdef";
const versionId = "21234567-89ab-4cde-8123-456789abcdef"; const actor = "31234567-89ab-4cde-8123-456789abcdef";
const questionOne = "41234567-89ab-4cde-8123-456789abcdef"; const questionTwo = "51234567-89ab-4cde-8123-456789abcdef";
const department = "61234567-89ab-4cde-8123-456789abcdef"; const document = "71234567-89ab-4cde-8123-456789abcdef";
const internalRow = "81234567-89ab-4cde-8123-456789abcdef"; const fixedVersion = "91234567-89ab-4cde-8123-456789abcdef";
const trace = "a1234567-89ab-4cde-8123-456789abcdef"; const now = "2026-10-06T12:00:00Z";
const root: SurveyView = { survey_id: surveyId, project_id: project, name: "客户现状调研", state: "ACTIVE",
  current_approved_version_ref: null, created_by: actor, created_at: now, updated_by: null, updated_at: now, etag: '"v0"' };
const empty = { handover_item_row_id: null, handover_analysis_version_id: null, handover_analysis_id: null,
  capability_item_row_id: null, capability_baseline_version_id: null, capability_baseline_id: null,
  template_document_version_id: null, template_document_id: null, manual_source_note: null };
const manual: SurveySourceView = { ...empty, source_kind: "MANUAL", manual_source_note: "2026-10-06客户现场访谈记录第3项", ordinal: 0 };
const template: SurveySourceView = { ...empty, source_kind: "TEMPLATE_DOCUMENT_VERSION",
  template_document_version_id: fixedVersion, template_document_id: document, ordinal: 0 };
const handover: SurveySourceView = { ...empty, source_kind: "HANDOVER_ITEM", handover_item_row_id: internalRow,
  handover_analysis_version_id: fixedVersion, handover_analysis_id: actor, ordinal: 1 };
const detail: SurveyVersionView = { survey_version_id: versionId, survey_id: surveyId, project_id: project,
  version_no: 1, state: "DRAFT", content_fingerprint: "b".repeat(64), declared_question_count: 2,
  declared_option_count: 2, declared_source_count: 3, declared_target_department_count: 1,
  supersedes_version_ref: null, review_ref: null, review_round_ref: null, created_by: actor, created_at: now,
  questions: [{ question_id: questionOne, sequence_no: 0, topic: "当前流程", question_text: "请描述当前审批流程。",
    objective: "以实际访谈确认现状", answer_type: "TEXT", validation_rule: { min_length: 1, max_length: 2000 },
    required: true, condition_rule: null, expected_output: "已确认的现状流程", evidence_required: true,
    options: [], sources: [manual] },
  { question_id: questionTwo, sequence_no: 1, topic: "系统方式", question_text: "当前采用哪种审批方式？",
    objective: "确认系统边界", answer_type: "SINGLE_CHOICE", validation_rule: {}, required: false,
    condition_rule: { all: [{ question_ref: questionOne, operator: "ANSWERED" }] }, expected_output: "审批方式",
    evidence_required: false, options: [{ option_code: "MANUAL", label: "人工", description: null, ordinal: 0 },
      { option_code: "SYSTEM", label: "系统", description: "由系统执行", ordinal: 1 }], sources: [template, handover] }],
  target_departments: [{ department_id: department, ordinal: 0 }] };
function response(data: unknown) { return new Response(JSON.stringify({ data, trace_id: trace }),
  { headers: { "Content-Type": "application/json" } }); }
async function session(restricted = false) { const api = new SessionClient(vi.fn().mockResolvedValue(response({
  user: { user_id: actor, username_display: "合成用户" }, deployment_role: "NONE", password_change_required: restricted,
  authorized_projects: restricted ? [] : [{ project_id: project, name: "合成项目", role: "PROJECT_MANAGER" }],
  absolute_expires_at: "2030-01-01T12:00:00Z", idle_expires_at: "2030-01-01T11:00:00Z", csrf_token: "a".repeat(64),
})) as typeof fetch); await api.login("user", "synthetic-only"); return api; }
function clients() { const surveys = new SurveyReadClient(vi.fn() as typeof fetch);
  vi.spyOn(surveys, "getSurvey").mockResolvedValue(root); vi.spyOn(surveys, "listVersions").mockResolvedValue({
    items: [detail], next_cursor: null, has_more: false }); vi.spyOn(surveys, "getVersion").mockResolvedValue(detail);
  return surveys; }
async function view(auth: SessionClient, surveys = clients()) { const router = createAppRouter(createMemoryHistory());
  await router.push(`/projects/${project}/surveys/${surveyId}`); await router.isReady();
  const wrapper = mount(ProjectSurveyDetailView, { props: { session: auth, surveys }, global: { plugins: [router] } });
  await flushPromises(); return { wrapper, router, surveys }; }

describe("ProjectSurveyDetailView", () => {
  afterEach(() => vi.restoreAllMocks());
  it("does not read without identity or while password change is required", async () => { const surveys = clients();
    const absent = await view(new SessionClient(vi.fn() as typeof fetch), surveys);
    expect(absent.wrapper.text()).toContain("尚未读取当前身份"); expect(surveys.getSurvey).not.toHaveBeenCalled(); absent.wrapper.unmount();
    const restricted = await view(await session(true), surveys);
    expect(restricted.wrapper.text()).toContain("须先修改密码"); expect(surveys.getSurvey).not.toHaveBeenCalled(); restricted.wrapper.unmount(); });

  it("layers root/version reads and renders explicit maintenance guidance", async () => { const result = await view(await session());
    expect(result.wrapper.text()).toContain("实际调研记录优先"); expect(result.wrapper.text()).toContain("版本 1");
    expect(result.surveys.getVersion).not.toHaveBeenCalled();
    await result.wrapper.findAll("button").find(button => button.text().includes("版本 1 的问题卡片"))!.trigger("click");
    await flushPromises(); expect(result.surveys.getVersion).toHaveBeenCalledWith(project, surveyId, versionId);
    expect(result.wrapper.text()).toContain("需要维护"); expect(result.wrapper.text()).toContain("必填的文本回答");
    expect(result.wrapper.text()).toContain("回答时需提供证据"); expect(result.wrapper.text()).toContain("预期输出");
    expect(result.wrapper.find("form").exists()).toBe(false); result.wrapper.unmount(); });

  it("labels actual/manual, template and Handover sources without leaking internal row IDs", async () => {
    const { wrapper } = await view(await session()); await wrapper.findAll("button").find(button => button.text().includes("问题卡片"))!.trigger("click");
    await flushPromises(); expect(wrapper.text()).toContain("面对面调研或人工来源说明");
    expect(wrapper.text()).toContain("2026-10-06客户现场访谈记录第3项");
    expect(wrapper.text()).toContain("模板仅供问题结构参考，不是客户事实");
    expect(wrapper.text()).toContain("已批准的项目交接事实"); expect(wrapper.text()).toContain("不会猜测内部标识");
    expect(wrapper.text()).not.toContain(internalRow);
    expect(wrapper.get(`a[href="/projects/${project}/documents/${document}"]`).text()).toContain("核对固定模板版本");
    wrapper.unmount(); });

  it("clears a selected Version after a later detail failure", async () => { const surveys = clients();
    vi.mocked(surveys.getVersion).mockResolvedValueOnce(detail).mockRejectedValueOnce(new SurveyReadError("RESOURCE_NOT_FOUND"));
    const { wrapper } = await view(await session(), surveys); const choose = () => wrapper.findAll("button")
      .find(button => button.text().includes("问题卡片"))!;
    await choose().trigger("click"); await flushPromises(); expect(wrapper.text()).toContain("请描述当前审批流程");
    await choose().trigger("click"); await flushPromises(); expect(wrapper.text()).not.toContain("请描述当前审批流程");
    expect(wrapper.get("[role=alert]").text()).toContain("无权查看"); wrapper.unmount(); });

  it("clears stale data when a root/version refresh is rejected", async () => { const surveys = clients();
    vi.mocked(surveys.getSurvey).mockResolvedValueOnce(root).mockRejectedValueOnce(new SurveyReadError("RESOURCE_NOT_FOUND"));
    const { wrapper } = await view(await session(), surveys); expect(wrapper.text()).toContain("客户现状调研");
    await wrapper.findAll("button")[0]!.trigger("click"); await flushPromises();
    expect(wrapper.text()).not.toContain("客户现状调研"); expect(wrapper.get("[role=alert]").text()).toContain("无权查看");
    wrapper.unmount(); });
});
