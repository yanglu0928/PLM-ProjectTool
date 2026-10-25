import { flushPromises, mount } from "@vue/test-utils";
import { createMemoryHistory } from "vue-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { createAppRouter } from "@/app/router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { ProjectDepartmentReadClient } from "@/modules/project/api/projectDepartmentReadClient";
import { SurveyReadClient, type SurveyView } from "@/modules/survey/api/surveyReadClient";
import { SurveyHandoverSourceClient } from "@/modules/survey/api/surveyHandoverSourceClient";
import { SurveyVersionCreateClient, SurveyVersionCreateError } from "@/modules/survey/api/surveyVersionCreateClient";
import ProjectSurveyVersionCreateView from "./ProjectSurveyVersionCreateView.vue";

const project = "01234567-89ab-4cde-8123-456789abcdef";
const survey = "11234567-89ab-4cde-8123-456789abcdef";
const actor = "21234567-89ab-4cde-8123-456789abcdef";
const department = "31234567-89ab-4cde-8123-456789abcdef";
const row = "41234567-89ab-4cde-8123-456789abcdef";
const analysis = "51234567-89ab-4cde-8123-456789abcdef";
const version = "61234567-89ab-4cde-8123-456789abcdef";
const publicItem = "71234567-89ab-4cde-8123-456789abcdef";
const createdVersion = "81234567-89ab-4cde-8123-456789abcdef";
const trace = "91234567-89ab-4cde-8123-456789abcdef";
const root: SurveyView = { survey_id: survey, project_id: project, name: "面对面业务调研",
  state: "ACTIVE", current_approved_version_ref: null, created_by: actor,
  created_at: "2026-10-25T12:00:00Z", updated_by: null,
  updated_at: "2026-10-25T12:00:00Z", etag: '"v0"' };
const candidate = { handover_item_row_id: row, handover_analysis_version_id: version,
  handover_analysis_id: analysis, analysis_item_id: publicItem, project_id: project,
  title: "确认当前审批范围", state: "CONFIRMED" as const };
function response(data: unknown) {
  return new Response(JSON.stringify({ data, trace_id: trace }),
    { headers: { "Content-Type": "application/json" } });
}
async function session(role = "PROJECT_MANAGER") {
  const auth = new SessionClient(vi.fn().mockImplementation(async () => response({
    user: { user_id: actor, username_display: "合成用户" }, deployment_role: "NONE",
    password_change_required: false, authorized_projects: [{ project_id: project,
      name: "合成项目", role }], absolute_expires_at: "2030-01-01T12:00:00Z",
    idle_expires_at: "2030-01-01T11:00:00Z", csrf_token: "a".repeat(64),
  })) as typeof fetch);
  await auth.login("user", "synthetic-only"); return auth;
}
async function mounted(auth: SessionClient, candidates = [candidate]) {
  const surveys = new SurveyReadClient(vi.fn() as typeof fetch);
  const handoverSources = new SurveyHandoverSourceClient(auth, vi.fn() as typeof fetch);
  const departments = new ProjectDepartmentReadClient(vi.fn() as typeof fetch);
  const creator = new SurveyVersionCreateClient(auth);
  vi.spyOn(surveys, "getSurvey").mockResolvedValue(root);
  vi.spyOn(handoverSources, "list").mockResolvedValue({ items: candidates,
    next_cursor: null, has_more: false });
  vi.spyOn(departments, "list").mockResolvedValue({ items: [{ department_id: department,
    code: "RD", name: "研发部", state: "ACTIVE", created_at: "2026-10-25T12:00:00Z",
    etag: '"v0"' }], next_cursor: null, has_more: false });
  const router = createAppRouter(createMemoryHistory());
  await router.push(`/projects/${project}/surveys/${survey}/versions/new`); await router.isReady();
  const wrapper = mount(ProjectSurveyVersionCreateView, { props: { session: auth, surveys,
    handoverSources, departments, creator }, global: { plugins: [router] } });
  await flushPromises();
  return { wrapper, surveys, handoverSources, departments, creator };
}
async function fill(wrapper: Awaited<ReturnType<typeof mounted>>["wrapper"], fixed: boolean) {
  await wrapper.find("fieldset input[type=checkbox]").setValue(true);
  await wrapper.find("input[placeholder='例如：当前物料审批流程']").setValue("当前物料审批流程");
  await wrapper.find("textarea[placeholder='写明确切的现场问题，不复制整篇资料']")
    .setValue("现场审批如何执行？");
  await wrapper.find("textarea[placeholder='说明为什么需要询问及待澄清的边界']")
    .setValue("核实实际流程");
  await wrapper.find("textarea[placeholder='例如：参与岗位、实际步骤、例外处理、待补证据']")
    .setValue("记录参与岗位和步骤");
  if (fixed) await wrapper.findAll("fieldset")[1]!.find("input[type=checkbox]").setValue(true);
  await wrapper.find("textarea[placeholder^='写明访谈日期']")
    .setValue("2026-10-25现场访谈，研发负责人参与；待客户核对。");
}
function button(wrapper: Awaited<ReturnType<typeof mounted>>["wrapper"], label: string) {
  const found = wrapper.findAll("button").find(item => item.text().includes(label));
  if (!found) throw new Error(`missing button: ${label}`); return found;
}

describe("ProjectSurveyVersionCreateView", () => {
  afterEach(() => { vi.restoreAllMocks(); sessionStorage.clear(); });

  it("blocks reads and writes without identity or project author role", async () => {
    const absent = await mounted(new SessionClient(vi.fn() as typeof fetch));
    expect(absent.wrapper.text()).toContain("尚未读取当前身份");
    expect(absent.surveys.getSurvey).not.toHaveBeenCalled(); absent.wrapper.unmount();
    const customer = await mounted(await session("CUSTOMER_MEMBER"));
    expect(customer.wrapper.text()).toContain("无权创建");
    expect(customer.handoverSources.list).not.toHaveBeenCalled(); customer.wrapper.unmount();
  });

  it("clears project content and disables saving when the live session loses write authority", async () => {
    const auth = await session(); const result = await mounted(auth);
    expect(result.wrapper.text()).toContain("面对面业务调研");
    await auth.current(); await flushPromises();
    expect(result.wrapper.text()).toContain("当前账户无权创建");
    expect(result.wrapper.text()).not.toContain("调研定义：面对面业务调研");
    expect(result.wrapper.find("button").exists()).toBe(false);
    result.wrapper.unmount();
  });

  it("creates DRAFT from fixed row IDs and actual interview note without treating it as confirmation", async () => {
    const result = await mounted(await session());
    const create = vi.spyOn(result.creator, "create").mockResolvedValue({ survey_version_id: createdVersion,
      survey_id: survey, project_id: project, version_no: 1, state: "DRAFT",
      content_fingerprint: "a".repeat(64), supersedes_version_ref: null,
      created_at: "2026-10-25T12:00:00Z", survey_etag: '"v1"' });
    expect(result.wrapper.text()).toContain("实际面对面调研记录优先");
    expect(result.wrapper.find("a[href*='fixedVersionId']").exists()).toBe(true);
    await fill(result.wrapper, true);
    await button(result.wrapper, "保存 DRAFT").trigger("click"); await flushPromises();
    expect(create).toHaveBeenCalledTimes(1);
    const [projectId, surveyId, etag, input, key] = create.mock.calls[0]!;
    expect([projectId, surveyId, etag]).toEqual([project, survey, '"v0"']);
    expect(input.questions[0]?.sources).toEqual([
      expect.objectContaining({ source_kind: "HANDOVER_ITEM", handover_item_row_id: row,
        handover_analysis_version_id: version, handover_analysis_id: analysis }),
      expect.objectContaining({ source_kind: "MANUAL", handover_item_row_id: null }),
    ]);
    expect(JSON.stringify(input)).not.toContain(publicItem);
    expect(input.target_department_ids).toEqual([department]);
    expect(key).toMatch(/^survey-version-[0-9a-f-]+$/);
    expect(result.wrapper.text()).toContain("不是客户确认事实");
    expect(sessionStorage.length).toBe(0); result.wrapper.unmount();
  });

  it("allows explicit MANUAL when no approved candidate but requires the note", async () => {
    const result = await mounted(await session(), []);
    const create = vi.spyOn(result.creator, "create").mockResolvedValue({ survey_version_id: createdVersion,
      survey_id: survey, project_id: project, version_no: 1, state: "DRAFT",
      content_fingerprint: "a".repeat(64), supersedes_version_ref: null,
      created_at: "2026-10-25T12:00:00Z", survey_etag: '"v1"' });
    await fill(result.wrapper, false);
    await button(result.wrapper, "保存 DRAFT").trigger("click"); await flushPromises();
    expect(create.mock.calls[0]?.[3].questions[0]?.sources).toEqual([
      expect.objectContaining({ source_kind: "MANUAL", handover_item_row_id: null }),
    ]);
    expect(result.wrapper.text()).toContain("不得称为已批准交接引用"); result.wrapper.unmount();
  });

  it("does not silently invent a fixed source or save a source-less question", async () => {
    const result = await mounted(await session(), []);
    const create = vi.spyOn(result.creator, "create");
    await fill(result.wrapper, false);
    await result.wrapper.find("textarea[placeholder^='写明访谈日期']").setValue("");
    await button(result.wrapper, "保存 DRAFT").trigger("click"); await flushPromises();
    expect(result.wrapper.text()).toContain("至少需要交接固定来源或明确的实际访谈记录说明");
    expect(create).not.toHaveBeenCalled(); expect(sessionStorage.length).toBe(0);
    result.wrapper.unmount();
  });

  it("retains original snapshot/key after uncertain result and retries only on explicit confirmation", async () => {
    const result = await mounted(await session());
    const create = vi.spyOn(result.creator, "create")
      .mockRejectedValueOnce(new SurveyVersionCreateError("UNCERTAIN"))
      .mockResolvedValueOnce({ survey_version_id: createdVersion, survey_id: survey,
        project_id: project, version_no: 1, state: "DRAFT",
        content_fingerprint: "a".repeat(64), supersedes_version_ref: null,
        created_at: "2026-10-25T12:00:00Z", survey_etag: '"v1"' });
    await fill(result.wrapper, true);
    await button(result.wrapper, "保存 DRAFT").trigger("click"); await flushPromises();
    expect(create).toHaveBeenCalledTimes(1);
    expect(sessionStorage.length).toBe(1);
    expect(button(result.wrapper, "按原操作号重试").attributes("disabled")).toBeDefined();
    // The last checkbox is the explicit retry confirmation.
    const confirmations = result.wrapper.findAll("label").filter(item => item.text().includes("已核对版本列表"));
    await confirmations[0]!.find("input").setValue(true);
    await button(result.wrapper, "按原操作号重试").trigger("click"); await flushPromises();
    expect(create).toHaveBeenCalledTimes(2);
    expect(create.mock.calls[1]).toEqual(create.mock.calls[0]);
    expect(sessionStorage.length).toBe(0); result.wrapper.unmount();
  });
});
