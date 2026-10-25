import { flushPromises, mount } from "@vue/test-utils";
import { createMemoryHistory } from "vue-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { createAppRouter } from "@/app/router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { SurveyReadClient, SurveyReadError, type SurveyView } from "@/modules/survey/api/surveyReadClient";
import { SurveyCreateClient, SurveyCreateError, type SurveyCreateView } from "@/modules/survey/api/surveyCreateClient";
import ProjectSurveyListView from "./ProjectSurveyListView.vue";

const project = "01234567-89ab-4cde-8123-456789abcdef"; const other = "11234567-89ab-4cde-8123-456789abcdef";
const surveyId = "21234567-89ab-4cde-8123-456789abcdef"; const actor = "31234567-89ab-4cde-8123-456789abcdef";
const trace = "41234567-89ab-4cde-8123-456789abcdef"; const token = `${"A".repeat(24)}.${"B".repeat(43)}` as never;
const item: SurveyView = { survey_id: surveyId, project_id: project, name: "客户现状调研", state: "ACTIVE",
  current_approved_version_ref: null, created_by: actor, created_at: "2026-10-06T12:00:00Z", updated_by: null,
  updated_at: "2026-10-06T12:00:00Z", etag: '"v0"' };
const created: SurveyCreateView = { survey_id: surveyId, project_id: project, name: "面对面业务调研",
  state: "ACTIVE", current_approved_version_ref: null, created_at: "2026-10-25T12:00:00Z", etag: '"v0"' };
function response(data: unknown) { return new Response(JSON.stringify({ data, trace_id: trace }),
  { headers: { "Content-Type": "application/json" } }); }
async function session(restricted = false, role = "PROJECT_MANAGER") { const api = new SessionClient(vi.fn().mockResolvedValue(response({
  user: { user_id: actor, username_display: "合成用户" }, deployment_role: "NONE", password_change_required: restricted,
  authorized_projects: restricted ? [] : [{ project_id: project, name: "合成项目", role }],
  absolute_expires_at: "2030-01-01T12:00:00Z", idle_expires_at: "2030-01-01T11:00:00Z", csrf_token: "a".repeat(64),
})) as typeof fetch); await api.login("user", "synthetic-only"); return api; }
function reader() { return new SurveyReadClient(vi.fn() as typeof fetch); }
async function view(auth: SessionClient, surveys = reader(), creator = new SurveyCreateClient(auth)) { const router = createAppRouter(createMemoryHistory());
  await router.push(`/projects/${project}/surveys`); await router.isReady();
  const wrapper = mount(ProjectSurveyListView, { props: { session: auth, surveys, creator }, global: { plugins: [router] } });
  await flushPromises(); return { wrapper, router, surveys }; }

describe("ProjectSurveyListView", () => {
  afterEach(() => { vi.restoreAllMocks(); window.sessionStorage.clear(); });
  it("does not read without identity or before password change", async () => { const surveys = reader();
    const list = vi.spyOn(surveys, "listSurveys");
    const absent = await view(new SessionClient(vi.fn() as typeof fetch), surveys);
    expect(absent.wrapper.text()).toContain("尚未读取当前身份"); absent.wrapper.unmount();
    const restricted = await view(await session(true), surveys);
    expect(restricted.wrapper.text()).toContain("须先修改密码"); expect(list).not.toHaveBeenCalled(); restricted.wrapper.unmount(); });

  it("shows safe summaries, actual-record warning and detail navigation", async () => { const surveys = reader();
    vi.spyOn(surveys, "listSurveys").mockResolvedValue({ items: [item], next_cursor: null, has_more: false });
    const { wrapper } = await view(await session(), surveys);
    expect(wrapper.text()).toContain("实际面对面调研记录"); expect(wrapper.text()).toContain("模板和来源说明不等于客户事实");
    expect(wrapper.text()).toContain("客户现状调研"); expect(wrapper.text()).toContain("尚未形成");
    expect(wrapper.get("form").text()).toContain("创建调研定义");
    expect(wrapper.get(`a[href="/projects/${project}/surveys/${surveyId}"]`).text()).toContain("问题与来源说明"); wrapper.unmount(); });

  it("appends a distinct page and clears all items after a denied later page", async () => { const surveys = reader();
    const older = { ...item, survey_id: actor, name: "旧调研", updated_at: "2026-10-06T11:00:00Z" };
    vi.spyOn(surveys, "listSurveys").mockResolvedValueOnce({ items: [item], next_cursor: token, has_more: true })
      .mockResolvedValueOnce({ items: [older], next_cursor: null, has_more: false })
      .mockRejectedValueOnce(new SurveyReadError("RESOURCE_NOT_FOUND"));
    const { wrapper } = await view(await session(), surveys);
    await wrapper.findAll("button").at(-1)!.trigger("click"); await flushPromises(); expect(wrapper.text()).toContain("旧调研");
    await wrapper.findAll("button").find(button => button.text().includes("刷新调研定义"))!.trigger("click");
    await flushPromises(); expect(wrapper.text()).not.toContain("客户现状调研");
    expect(wrapper.get("[role=alert]").text()).toContain("无权查看"); wrapper.unmount(); });

  it("discards a late prior-project page", async () => { const surveys = reader(); let finish!: (value: never) => void;
    vi.spyOn(surveys, "listSurveys").mockReturnValueOnce(new Promise(resolve => { finish = resolve as typeof finish; }))
      .mockResolvedValueOnce({ items: [], next_cursor: null, has_more: false });
    const { wrapper, router } = await view(await session(), surveys);
    await router.push(`/projects/${other}/surveys`); await flushPromises();
    finish({ items: [item], next_cursor: null, has_more: false } as never); await flushPromises();
    expect(wrapper.text()).not.toContain("客户现状调研"); expect(surveys.listSurveys).toHaveBeenLastCalledWith(other, 50, null);
    wrapper.unmount(); });

  it("shows write form only for authorized implementation roles", async () => { const surveys = reader();
    vi.spyOn(surveys, "listSurveys").mockResolvedValue({ items: [], next_cursor: null, has_more: false });
    const allowed = await view(await session(false, "IMPLEMENTATION_MEMBER"), surveys);
    expect(allowed.wrapper.find("form").exists()).toBe(true); allowed.wrapper.unmount();
    const denied = await view(await session(false, "CUSTOMER_MEMBER"), surveys);
    expect(denied.wrapper.find("form").exists()).toBe(false); denied.wrapper.unmount(); });

  it("creates a definition and navigates to its detail without asserting customer facts", async () => {
    const auth = await session(); const surveys = reader();
    vi.spyOn(surveys, "listSurveys").mockResolvedValue({ items: [], next_cursor: null, has_more: false });
    const creator = new SurveyCreateClient(auth); const create = vi.spyOn(creator, "create").mockResolvedValue(created);
    const { wrapper, router } = await view(auth, surveys, creator);
    await wrapper.get("#survey-create-name").setValue(created.name);
    await wrapper.get("form").trigger("submit"); await flushPromises();
    expect(create).toHaveBeenCalledOnce(); expect(create.mock.calls[0]?.slice(0, 2)).toEqual([project, created.name]);
    expect(create.mock.calls[0]?.[2]).toMatch(/^survey-create-[0-9a-f-]+$/);
    expect(router.currentRoute.value.path).toBe(`/projects/${project}/surveys/${surveyId}`);
    expect(window.sessionStorage.getItem(`plm.survey.create.pending.${actor}.${project}`)).toBeNull();
    wrapper.unmount(); });

  it("keeps an unknown result and retries only after confirmation with the original key", async () => {
    const auth = await session(); const surveys = reader();
    vi.spyOn(surveys, "listSurveys").mockResolvedValue({ items: [], next_cursor: null, has_more: false });
    const creator = new SurveyCreateClient(auth); const create = vi.spyOn(creator, "create")
      .mockRejectedValueOnce(new SurveyCreateError("SURVEY_CREATE_UNCERTAIN"))
      .mockResolvedValueOnce(created);
    const { wrapper } = await view(auth, surveys, creator);
    await wrapper.get("#survey-create-name").setValue(created.name);
    await wrapper.get("form").trigger("submit"); await flushPromises();
    expect(wrapper.text()).toContain("原名称与操作号已保存在本浏览器会话");
    const saved = window.sessionStorage.getItem(`plm.survey.create.pending.${actor}.${project}`);
    expect(saved).toContain(created.name);
    await wrapper.get("form input[type=checkbox]").setValue(true);
    await wrapper.get("form").trigger("submit"); await flushPromises();
    expect(create).toHaveBeenCalledTimes(2);
    expect(create.mock.calls[0]?.[2]).toBe(create.mock.calls[1]?.[2]);
    expect(window.sessionStorage.getItem(`plm.survey.create.pending.${actor}.${project}`)).toBeNull();
    wrapper.unmount(); });

  it("locks corrupted pending data instead of changing the key or silently resending", async () => {
    window.sessionStorage.setItem(`plm.survey.create.pending.${actor}.${project}`, '{"name":"bad"}');
    const auth = await session(); const surveys = reader();
    vi.spyOn(surveys, "listSurveys").mockResolvedValue({ items: [], next_cursor: null, has_more: false });
    const creator = new SurveyCreateClient(auth); const create = vi.spyOn(creator, "create");
    const { wrapper } = await view(auth, surveys, creator);
    expect(wrapper.get("[role=alert]").text()).toContain("原创建记录无法安全读取");
    expect(wrapper.get("form button[type=submit]").attributes("disabled")).toBeDefined();
    await wrapper.get("form").trigger("submit"); await flushPromises(); expect(create).not.toHaveBeenCalled();
    wrapper.unmount(); });

  it("restores the exact original operation after remount and confirmation", async () => {
    const saved = { actor, project, name: created.name, key: "survey-original-key-001" };
    window.sessionStorage.setItem(`plm.survey.create.pending.${actor}.${project}`, JSON.stringify(saved));
    const auth = await session(); const surveys = reader();
    vi.spyOn(surveys, "listSurveys").mockResolvedValue({ items: [], next_cursor: null, has_more: false });
    const creator = new SurveyCreateClient(auth); const create = vi.spyOn(creator, "create").mockResolvedValue(created);
    const { wrapper } = await view(auth, surveys, creator);
    expect((wrapper.get("#survey-create-name").element as HTMLInputElement).value).toBe(created.name);
    expect(wrapper.get("#survey-create-name").attributes("disabled")).toBeDefined();
    await wrapper.get("form input[type=checkbox]").setValue(true);
    await wrapper.get("form").trigger("submit"); await flushPromises();
    expect(create).toHaveBeenCalledWith(project, created.name, saved.key);
    wrapper.unmount(); });

  it("does not navigate or clear an old project's pending result after route change", async () => {
    const auth = await session(); const surveys = reader();
    vi.spyOn(surveys, "listSurveys").mockResolvedValue({ items: [], next_cursor: null, has_more: false });
    let finish!: (value: SurveyCreateView) => void;
    const creator = new SurveyCreateClient(auth); vi.spyOn(creator, "create")
      .mockReturnValue(new Promise(resolve => { finish = resolve; }));
    const { wrapper, router } = await view(auth, surveys, creator);
    await wrapper.get("#survey-create-name").setValue(created.name);
    await wrapper.get("form").trigger("submit"); await flushPromises();
    const saved = window.sessionStorage.getItem(`plm.survey.create.pending.${actor}.${project}`);
    expect(saved).not.toBeNull();
    await router.push(`/projects/${other}/surveys`); await flushPromises();
    finish(created); await flushPromises();
    expect(router.currentRoute.value.path).toBe(`/projects/${other}/surveys`);
    expect(window.sessionStorage.getItem(`plm.survey.create.pending.${actor}.${project}`)).toBe(saved);
    wrapper.unmount(); });
});
