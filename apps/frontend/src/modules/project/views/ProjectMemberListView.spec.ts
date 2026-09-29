import { flushPromises, mount } from "@vue/test-utils";
import { createMemoryHistory } from "vue-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { createAppRouter } from "@/app/router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { ProjectMemberReadClient } from "@/modules/project/api/projectMemberReadClient";
import { ProjectMemberChoicesClient } from "@/modules/project/api/projectMemberChoicesClient";
import { ProjectMemberPatchClient, ProjectMemberPatchError } from "@/modules/project/api/projectMemberPatchClient";
import { ProjectMemberStateClient, ProjectMemberStateError } from "@/modules/project/api/projectMemberStateClient";
import ProjectMemberListView from "./ProjectMemberListView.vue";

const id = "01234567-89ab-4cde-8123-456789abcdef";
const otherId = "11234567-89ab-4cde-8123-456789abcdef";
const memberId = "21234567-89ab-4cde-8123-456789abcdef";
const cursor = `${"a".repeat(40)}.${"b".repeat(43)}`;
const entry = { member_id: memberId, user: { user_id: "31234567-89ab-4cde-8123-456789abcdef", display_name: "成员甲" },
  role: "PROJECT_MANAGER" as const, department: { department_id: "41234567-89ab-4cde-8123-456789abcdef", name: "研发部" },
  state: "ACTIVE" as const, effective_at: "2026-09-28T08:30:00Z", ended_at: null, etag: '"v0"' };
function response(data: unknown): Response {
  return new Response(JSON.stringify({ data, trace_id: id }), { status: 200,
    headers: { "Content-Type": "application/json" } });
}
function failure(status: number, code: string): Response {
  return new Response(JSON.stringify({ error: { code, message: "private details" }, trace_id: id }),
    { status, headers: { "Content-Type": "application/json" } });
}
async function session(restricted = false, manager = false): Promise<SessionClient> {
  const api = new SessionClient(vi.fn().mockResolvedValue(response({
    user: { user_id: id, username_display: "合成用户" }, deployment_role: "NONE",
    password_change_required: restricted, authorized_projects: manager
      ? [{ project_id: id, name: "项目", role: "PROJECT_MANAGER" }] : [],
    absolute_expires_at: "2030-01-01T12:00:00Z", idle_expires_at: "2030-01-01T11:00:00Z",
    csrf_token: "a".repeat(64),
  })) as typeof fetch);
  await api.login("user", "synthetic-only");
  return api;
}
async function view(auth: SessionClient, path: string, fetcher: typeof fetch,
  choices?: ProjectMemberChoicesClient, patcher?: ProjectMemberPatchClient,
  stateClient?: ProjectMemberStateClient) {
  const router = createAppRouter(createMemoryHistory());
  await router.push(path);
  await router.isReady();
  const wrapper = mount(ProjectMemberListView, {
    props: { session: auth, members: new ProjectMemberReadClient(fetcher), choices, patcher, stateClient },
    global: { plugins: [router] },
  });
  await flushPromises();
  return { wrapper, router };
}

describe("ProjectMemberListView", () => {
  afterEach(() => vi.restoreAllMocks());

  it("does not request members without current identity or with required password change", async () => {
    const fetcher = vi.fn();
    const absent = await view(new SessionClient(fetcher as typeof fetch), `/projects/${id}/members`, fetcher as typeof fetch);
    expect(absent.wrapper.text()).toContain("尚未读取当前身份");
    absent.wrapper.unmount();
    const restricted = await view(await session(true), `/projects/${id}/members`, fetcher as typeof fetch);
    expect(restricted.wrapper.text()).toContain("须先修改密码");
    expect(fetcher).not.toHaveBeenCalled();
    restricted.wrapper.unmount();
  });

  it("reads member history only through server even when Session summary has no projects", async () => {
    const fetcher = vi.fn().mockResolvedValue(response({ items: [{ ...entry,
      user: { ...entry.user, display_name: "<img src=x>" } }], next_cursor: null, has_more: false }));
    const { wrapper } = await view(await session(), `/projects/${id}/members`, fetcher as typeof fetch);
    expect(wrapper.text()).toContain("<img src=x>");
    expect(wrapper.find("img").exists()).toBe(false);
    expect(wrapper.text()).toContain("项目负责人");
    expect(fetcher.mock.calls[0]?.[0]).toBe(`/api/v1/projects/${id}/members?page_size=50`);
    wrapper.unmount();
  });

  it("shows empty authorized history without inventing members", async () => {
    const fetcher = vi.fn().mockResolvedValue(response({ items: [], next_cursor: null, has_more: false }));
    const { wrapper } = await view(await session(), `/projects/${id}/members`, fetcher as typeof fetch);
    expect(wrapper.text()).toContain("没有成员记录");
    expect(wrapper.find('ul[aria-label="项目成员历史"]').exists()).toBe(false);
    wrapper.unmount();
  });

  it("loads next page with opaque cursor and appends only server-projected items", async () => {
    const second = { ...entry, member_id: "51234567-89ab-4cde-8123-456789abcdef", user: { ...entry.user, display_name: "成员乙" } };
    const fetcher = vi.fn().mockResolvedValueOnce(response({ items: [entry], next_cursor: cursor, has_more: true }))
      .mockResolvedValueOnce(response({ items: [second], next_cursor: null, has_more: false }));
    const { wrapper } = await view(await session(), `/projects/${id}/members`, fetcher as typeof fetch);
    await wrapper.get("button:last-of-type").trigger("click");
    await flushPromises();
    expect(wrapper.text()).toContain("成员甲");
    expect(wrapper.text()).toContain("成员乙");
    expect(fetcher.mock.calls[1]?.[0]).toBe(`/api/v1/projects/${id}/members?page_size=50&cursor=${cursor}`);
    expect(wrapper.findAll('ul[aria-label="项目成员历史"] li')).toHaveLength(2);
    wrapper.unmount();
  });

  it("clears prior members and cursor when a later page is rejected", async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(response({ items: [entry], next_cursor: cursor, has_more: true }))
      .mockResolvedValueOnce(failure(404, "RESOURCE_NOT_FOUND"));
    const { wrapper } = await view(await session(), `/projects/${id}/members`, fetcher as typeof fetch);
    await wrapper.get("button:last-of-type").trigger("click");
    await flushPromises();
    expect(wrapper.get('[role="alert"]').text()).toContain("不存在或无权");
    expect(wrapper.text()).not.toContain("成员甲");
    expect(wrapper.html()).not.toContain("private details");
    expect(wrapper.find('ul[aria-label="项目成员历史"]').exists()).toBe(false);
    wrapper.unmount();
  });

  it("rejects an unsafe direct project path before network", async () => {
    const fetcher = vi.fn();
    const { wrapper } = await view(await session(), "/projects/bad/members", fetcher as typeof fetch);
    expect(wrapper.get('[role="alert"]').text()).toContain("项目标识无效");
    expect(fetcher).not.toHaveBeenCalled();
    wrapper.unmount();
  });

  it("drops old project members after navigation and ignores a late old response", async () => {
    let resolveOld!: (value: Response) => void;
    const fetcher = vi.fn().mockImplementationOnce(() => new Promise<Response>((resolve) => { resolveOld = resolve; }))
      .mockResolvedValueOnce(response({ items: [], next_cursor: null, has_more: false }));
    const { wrapper, router } = await view(await session(), `/projects/${id}/members`, fetcher as typeof fetch);
    await router.push(`/projects/${otherId}/members`);
    await flushPromises();
    resolveOld(response({ items: [entry], next_cursor: null, has_more: false }));
    await flushPromises();
    expect(fetcher).toHaveBeenCalledTimes(2);
    expect(fetcher.mock.calls[1]?.[0]).toBe(`/api/v1/projects/${otherId}/members?page_size=50`);
    expect(wrapper.text()).not.toContain("成员甲");
    expect(wrapper.text()).toContain("没有成员记录");
    wrapper.unmount();
  });

  it("clears all members when another page repeats an existing member", async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(response({ items: [entry], next_cursor: cursor, has_more: true }))
      .mockResolvedValueOnce(response({ items: [entry], next_cursor: null, has_more: false }));
    const { wrapper } = await view(await session(), `/projects/${id}/members`, fetcher as typeof fetch);
    await wrapper.get("button:last-of-type").trigger("click");
    await flushPromises();
    expect(wrapper.get('[role="alert"]').text()).toContain("暂时无法读取");
    expect(wrapper.text()).not.toContain("成员甲");
    wrapper.unmount();
  });

  it("offers no mutation to a reader and never loads department choices", async () => {
    const auth = await session();
    const choices = new ProjectMemberChoicesClient(auth);
    const departments = vi.spyOn(choices, "activeDepartments");
    const fetcher = vi.fn().mockImplementation(() => Promise.resolve(response({ items: [entry], next_cursor: null, has_more: false })));
    const { wrapper } = await view(auth, `/projects/${id}/members`, fetcher as typeof fetch, choices);
    expect(wrapper.text()).not.toContain("修改角色或部门");
    expect(departments).not.toHaveBeenCalled();
    wrapper.unmount();
  });

  it("requires current member, active department and explicit confirmation before one PATCH", async () => {
    const auth = await session(false, true);
    const choices = new ProjectMemberChoicesClient(auth);
    vi.spyOn(choices, "activeDepartments").mockResolvedValue([
      { department_id: entry.department.department_id, code: "DEV", name: "研发部" },
    ]);
    const patcher = new ProjectMemberPatchClient(auth);
    const patch = vi.spyOn(patcher, "patch").mockResolvedValue({ ...entry, role: "CUSTOMER_MEMBER", etag: '"v1"' });
    const fetcher = vi.fn().mockImplementation(() => Promise.resolve(response({ items: [entry], next_cursor: null, has_more: false })));
    const { wrapper } = await view(auth, `/projects/${id}/members`, fetcher as typeof fetch, choices, patcher);
    await wrapper.get("li button").trigger("click");
    await flushPromises();
    expect(wrapper.text()).toContain(entry.user.user_id);
    expect(wrapper.text()).toContain('版本 "v0"');
    expect(wrapper.get("form button[type=submit]").attributes("disabled")).toBeDefined();
    await wrapper.get("#member-edit-role").setValue("CUSTOMER_MEMBER");
    await wrapper.get('input[name="confirm_member_patch"]').setValue(true);
    await wrapper.get("form").trigger("submit");
    await flushPromises();
    expect(patch).toHaveBeenCalledTimes(1);
    expect(patch).toHaveBeenCalledWith(id, entry,
      { role: "CUSTOMER_MEMBER", department_id: entry.department.department_id });
    expect(wrapper.text()).toContain("本次写入回执");
    expect(fetcher).toHaveBeenCalledTimes(2);
    wrapper.unmount();
  });

  it("locks further writes on uncertain result while allowing read-only reconciliation", async () => {
    const auth = await session(false, true);
    const choices = new ProjectMemberChoicesClient(auth);
    vi.spyOn(choices, "activeDepartments").mockResolvedValue([
      { department_id: entry.department.department_id, code: "DEV", name: "研发部" },
    ]);
    const patcher = new ProjectMemberPatchClient(auth);
    const patch = vi.spyOn(patcher, "patch").mockRejectedValue(new ProjectMemberPatchError("PROJECT_MEMBER_PATCH_UNCERTAIN"));
    const fetcher = vi.fn().mockImplementation(() => Promise.resolve(response({ items: [entry], next_cursor: null, has_more: false })));
    const { wrapper } = await view(auth, `/projects/${id}/members`, fetcher as typeof fetch, choices, patcher);
    await wrapper.get("li button").trigger("click"); await flushPromises();
    await wrapper.get("#member-edit-role").setValue("CUSTOMER_MEMBER");
    await wrapper.get('input[name="confirm_member_patch"]').setValue(true);
    await wrapper.get("form").trigger("submit"); await flushPromises();
    expect(patch).toHaveBeenCalledTimes(1);
    expect(wrapper.text()).toContain("已停止本页后续提交");
    expect(wrapper.find("li button").exists()).toBe(false);
    expect(fetcher).toHaveBeenCalledTimes(2);
    wrapper.unmount();
  });

  it("requires fresh selection after a known version conflict", async () => {
    const auth = await session(false, true);
    const choices = new ProjectMemberChoicesClient(auth);
    vi.spyOn(choices, "activeDepartments").mockResolvedValue([
      { department_id: entry.department.department_id, code: "DEV", name: "研发部" },
    ]);
    const patcher = new ProjectMemberPatchClient(auth);
    const patch = vi.spyOn(patcher, "patch").mockRejectedValue(new ProjectMemberPatchError("CONFLICT_VERSION"));
    const fetcher = vi.fn().mockImplementation(() => Promise.resolve(response({ items: [entry], next_cursor: null, has_more: false })));
    const { wrapper } = await view(auth, `/projects/${id}/members`, fetcher as typeof fetch, choices, patcher);
    await wrapper.get("li button").trigger("click"); await flushPromises();
    await wrapper.get("#member-edit-role").setValue("CUSTOMER_MEMBER");
    await wrapper.get('input[name="confirm_member_patch"]').setValue(true);
    await wrapper.get("form").trigger("submit"); await flushPromises();
    expect(wrapper.text()).toContain("重新读取后再决定");
    expect(wrapper.find("form").exists()).toBe(false);
    expect(wrapper.find("li button").exists()).toBe(true);
    expect(patch).toHaveBeenCalledTimes(1);
    expect(fetcher).toHaveBeenCalledTimes(2);
    wrapper.unmount();
  });

  it("drops a late PATCH receipt after project navigation", async () => {
    const auth = await session(false, true);
    const choices = new ProjectMemberChoicesClient(auth);
    vi.spyOn(choices, "activeDepartments").mockResolvedValue([
      { department_id: entry.department.department_id, code: "DEV", name: "研发部" },
    ]);
    let resolvePatch!: (value: typeof entry) => void;
    const patcher = new ProjectMemberPatchClient(auth);
    vi.spyOn(patcher, "patch").mockImplementation(() => new Promise((resolve) => { resolvePatch = resolve; }));
    const fetcher = vi.fn().mockResolvedValueOnce(response({ items: [entry], next_cursor: null, has_more: false }))
      .mockResolvedValueOnce(response({ items: [], next_cursor: null, has_more: false }));
    const { wrapper, router } = await view(auth, `/projects/${id}/members`, fetcher as typeof fetch, choices, patcher);
    await wrapper.get("li button").trigger("click"); await flushPromises();
    await wrapper.get("#member-edit-role").setValue("CUSTOMER_MEMBER");
    await wrapper.get('input[name="confirm_member_patch"]').setValue(true);
    await wrapper.get("form").trigger("submit");
    await router.push(`/projects/${otherId}/members`); await flushPromises();
    resolvePatch(entry); await flushPromises();
    expect(wrapper.text()).not.toContain("本次写入回执");
    expect(wrapper.text()).toContain("没有成员记录");
    wrapper.unmount();
  });

  it("requires explicit target/version confirmation before one state command and separates first receipt", async () => {
    const auth = await session(false, true);
    const states = new ProjectMemberStateClient(auth);
    const suspended = { ...entry, state: "SUSPENDED" as const, etag: '"v1"' };
    const change = vi.spyOn(states, "change").mockResolvedValue({
      first_result: suspended, is_current_state_proof: false,
    });
    const fetcher = vi.fn().mockResolvedValueOnce(response({ items: [entry], next_cursor: null, has_more: false }))
      .mockResolvedValueOnce(response({ items: [suspended], next_cursor: null, has_more: false }));
    const { wrapper } = await view(auth, `/projects/${id}/members`, fetcher as typeof fetch,
      undefined, undefined, states);
    await wrapper.get("li button:nth-of-type(2)").trigger("click");
    expect(wrapper.text()).toContain('版本 "v0"');
    expect(wrapper.get('form[aria-label="更改成员状态"] button[type=submit]').attributes("disabled")).toBeDefined();
    await wrapper.get('input[name="confirm_member_state"]').setValue(true);
    await wrapper.get('form[aria-label="更改成员状态"]').trigger("submit"); await flushPromises();
    expect(change).toHaveBeenCalledTimes(1);
    expect(change.mock.calls[0]?.slice(0, 3)).toEqual([id, entry, "suspend"]);
    expect(change.mock.calls[0]?.[3]).toMatch(/^[0-9a-f-]{36}$/);
    expect(wrapper.text()).toContain("本次状态命令首次回执");
    expect(wrapper.text()).toContain("它不是当前状态证明");
    expect(wrapper.text()).toContain("暂停 · 研发部");
    expect(fetcher).toHaveBeenCalledTimes(2);
    wrapper.unmount();
  });

  it("retains original action, version and Key on uncertain result and requires explicit original retry", async () => {
    const auth = await session(false, true);
    const states = new ProjectMemberStateClient(auth);
    const suspended = { ...entry, state: "SUSPENDED" as const, etag: '"v1"' };
    const change = vi.spyOn(states, "change")
      .mockRejectedValueOnce(new ProjectMemberStateError("PROJECT_MEMBER_STATE_UNCERTAIN"))
      .mockResolvedValueOnce({ first_result: suspended, is_current_state_proof: false });
    const fetcher = vi.fn().mockImplementation(() => Promise.resolve(response({
      items: [entry], next_cursor: null, has_more: false,
    })));
    const { wrapper } = await view(auth, `/projects/${id}/members`, fetcher as typeof fetch,
      undefined, undefined, states);
    await wrapper.get("li button:nth-of-type(2)").trigger("click");
    await wrapper.get('input[name="confirm_member_state"]').setValue(true);
    await wrapper.get('form[aria-label="更改成员状态"]').trigger("submit"); await flushPromises();
    expect(change).toHaveBeenCalledTimes(1);
    expect(wrapper.text()).toContain("原目标、动作、版本和操作记录保留");
    expect(wrapper.find("li button").exists()).toBe(false);
    expect(wrapper.get('form[aria-label="恢复原状态命令"] button[type=submit]').attributes("disabled")).toBeDefined();
    await wrapper.get('input[name="confirm_original_state"]').setValue(true);
    await wrapper.get('form[aria-label="恢复原状态命令"]').trigger("submit"); await flushPromises();
    expect(change).toHaveBeenCalledTimes(2);
    expect(change.mock.calls[1]).toEqual(change.mock.calls[0]);
    expect(wrapper.text()).toContain("本次状态命令首次回执");
    wrapper.unmount();
  });

  it("states removal keeps history and blocks resuming removed members", async () => {
    const auth = await session(false, true);
    const fetcher = vi.fn().mockResolvedValue(response({ items: [entry], next_cursor: null, has_more: false }));
    const { wrapper } = await view(auth, `/projects/${id}/members`, fetcher as typeof fetch);
    await wrapper.get("li button:nth-of-type(3)").trigger("click");
    expect(wrapper.text()).toContain("不能在本页直接恢复");
    expect(wrapper.get('form[aria-label="更改成员状态"] button[type=submit]').attributes("disabled")).toBeDefined();
    wrapper.unmount();
  });

  it("locks all writes after original idempotency conflict", async () => {
    const auth = await session(false, true);
    const states = new ProjectMemberStateClient(auth);
    const change = vi.spyOn(states, "change")
      .mockRejectedValue(new ProjectMemberStateError("CONFLICT_IDEMPOTENCY"));
    const fetcher = vi.fn().mockImplementation(() => Promise.resolve(response({
      items: [entry], next_cursor: null, has_more: false,
    })));
    const { wrapper } = await view(auth, `/projects/${id}/members`, fetcher as typeof fetch,
      undefined, undefined, states);
    await wrapper.get("li button:nth-of-type(2)").trigger("click");
    await wrapper.get('input[name="confirm_member_state"]').setValue(true);
    await wrapper.get('form[aria-label="更改成员状态"]').trigger("submit"); await flushPromises();
    expect(change).toHaveBeenCalledTimes(1);
    expect(wrapper.text()).toContain("已停止本页后续提交");
    expect(wrapper.find("li button").exists()).toBe(false);
    expect(wrapper.find('form[aria-label="恢复原状态命令"]').exists()).toBe(false);
    wrapper.unmount();
  });

  it("drops a late state receipt after project navigation", async () => {
    const auth = await session(false, true);
    const states = new ProjectMemberStateClient(auth);
    let resolveState!: (value: { first_result: typeof entry; is_current_state_proof: false }) => void;
    vi.spyOn(states, "change").mockImplementation(() => new Promise((resolve) => { resolveState = resolve; }));
    const fetcher = vi.fn().mockResolvedValueOnce(response({ items: [entry], next_cursor: null, has_more: false }))
      .mockResolvedValueOnce(response({ items: [], next_cursor: null, has_more: false }));
    const { wrapper, router } = await view(auth, `/projects/${id}/members`, fetcher as typeof fetch,
      undefined, undefined, states);
    await wrapper.get("li button:nth-of-type(2)").trigger("click");
    await wrapper.get('input[name="confirm_member_state"]').setValue(true);
    await wrapper.get('form[aria-label="更改成员状态"]').trigger("submit");
    await router.push(`/projects/${otherId}/members`); await flushPromises();
    resolveState({ first_result: entry, is_current_state_proof: false }); await flushPromises();
    expect(wrapper.text()).not.toContain("本次状态命令首次回执");
    expect(wrapper.text()).toContain("没有成员记录");
    wrapper.unmount();
  });
});
