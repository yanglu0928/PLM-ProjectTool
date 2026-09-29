import { flushPromises, mount } from "@vue/test-utils";
import { createMemoryHistory } from "vue-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { createAppRouter } from "@/app/router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { ProjectDepartmentReadClient } from "@/modules/project/api/projectDepartmentReadClient";
import { ProjectDepartmentPatchClient, ProjectDepartmentPatchError } from
  "@/modules/project/api/projectDepartmentPatchClient";
import ProjectDepartmentListView from "./ProjectDepartmentListView.vue";

const id = "01234567-89ab-4cde-8123-456789abcdef";
const otherId = "11234567-89ab-4cde-8123-456789abcdef";
const cursor = `${"a".repeat(40)}.${"b".repeat(43)}`;
const entry = { department_id: "21234567-89ab-4cde-8123-456789abcdef", code: "RD", name: "研发部",
  state: "ACTIVE" as const, created_at: "2026-09-29T02:00:00Z", etag: '"v0"' };
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
async function view(auth: SessionClient, fetcher: typeof fetch, patcher?: ProjectDepartmentPatchClient) {
  const router = createAppRouter(createMemoryHistory());
  await router.push(`/projects/${id}/departments`);
  await router.isReady();
  const wrapper = mount(ProjectDepartmentListView, { props: { session: auth,
    departments: new ProjectDepartmentReadClient(fetcher), patcher }, global: { plugins: [router] } });
  await flushPromises();
  return { wrapper, router };
}

describe("ProjectDepartmentListView", () => {
  afterEach(() => vi.restoreAllMocks());

  it("does not fetch without identity or when password change is required", async () => {
    const fetcher = vi.fn();
    const absent = await view(new SessionClient(fetcher as typeof fetch), fetcher as typeof fetch);
    expect(absent.wrapper.text()).toContain("尚未读取当前身份");
    absent.wrapper.unmount();
    const restricted = await view(await session(true), fetcher as typeof fetch);
    expect(restricted.wrapper.text()).toContain("须先修改密码");
    expect(fetcher).not.toHaveBeenCalled();
    restricted.wrapper.unmount();
  });

  it("shows active and inactive history without treating session summary as server authorization", async () => {
    const inactive = { ...entry, department_id: otherId, code: "OLD", name: "旧部门", state: "INACTIVE" };
    const fetcher = vi.fn().mockResolvedValue(response({ items: [entry, inactive], next_cursor: null, has_more: false }));
    const { wrapper } = await view(await session(), fetcher as typeof fetch);
    expect(wrapper.text()).toContain("研发部");
    expect(wrapper.text()).toContain("旧部门");
    expect(wrapper.text()).toContain("已停用");
    expect(wrapper.text()).toContain("跨页内容不代表同一时刻的快照");
    expect(fetcher).toHaveBeenCalledTimes(1);
    wrapper.unmount();
  });

  it("shows the create entry only to a current manager with a write session", async () => {
    const fetcher = vi.fn().mockResolvedValue(response({ items: [], next_cursor: null, has_more: false }));
    const reader = await view(await session(), fetcher as typeof fetch);
    expect(reader.wrapper.text()).not.toContain("创建项目部门");
    reader.wrapper.unmount();
    const manager = await view(await session(false, true), fetcher as typeof fetch);
    expect(manager.wrapper.get('a[href$="/departments/new"]').text()).toBe("创建项目部门");
    manager.wrapper.unmount();
  });

  it("loads the next page and refreshes from the beginning", async () => {
    const another = { ...entry, department_id: otherId, name: "交付部" };
    const fetcher = vi.fn().mockResolvedValueOnce(response({ items: [entry], next_cursor: cursor, has_more: true }))
      .mockResolvedValueOnce(response({ items: [another], next_cursor: null, has_more: false }))
      .mockResolvedValueOnce(response({ items: [another], next_cursor: null, has_more: false }));
    const { wrapper } = await view(await session(), fetcher as typeof fetch);
    await wrapper.get("button:last-of-type").trigger("click");
    await flushPromises();
    expect(wrapper.text()).toContain("研发部");
    expect(wrapper.text()).toContain("交付部");
    expect(fetcher.mock.calls[1]?.[0]).toContain(`cursor=${cursor}`);
    await wrapper.get("button:first-of-type").trigger("click");
    await flushPromises();
    expect(wrapper.text()).not.toContain("研发部");
    expect(wrapper.text()).toContain("交付部");
    wrapper.unmount();
  });

  it("clears old entries on denied next page", async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(response({ items: [entry], next_cursor: cursor, has_more: true }))
      .mockResolvedValueOnce(failure(404, "RESOURCE_NOT_FOUND"));
    const { wrapper } = await view(await session(), fetcher as typeof fetch);
    await wrapper.get("button:last-of-type").trigger("click");
    await flushPromises();
    expect(wrapper.text()).not.toContain("研发部");
    expect(wrapper.get('[role="alert"]').text()).toContain("无权查看部门");
    wrapper.unmount();
  });

  it("clears old entries on duplicate ID across pages", async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(response({ items: [entry], next_cursor: cursor, has_more: true }))
      .mockResolvedValueOnce(response({ items: [entry], next_cursor: null, has_more: false }));
    const { wrapper } = await view(await session(), fetcher as typeof fetch);
    await wrapper.get("button:last-of-type").trigger("click");
    await flushPromises();
    expect(wrapper.text()).not.toContain("研发部");
    expect(wrapper.get('[role="alert"]').text()).toContain("暂时无法读取");
    wrapper.unmount();
  });

  it("does not show a late result for another project", async () => {
    let finish!: (value: Response) => void;
    const fetcher = vi.fn().mockReturnValueOnce(new Promise<Response>((resolve) => { finish = resolve; }))
      .mockResolvedValueOnce(response({ items: [], next_cursor: null, has_more: false }));
    const { wrapper, router } = await view(await session(), fetcher as typeof fetch);
    await router.push(`/projects/${otherId}/departments`);
    await flushPromises();
    finish(response({ items: [entry], next_cursor: null, has_more: false }));
    await flushPromises();
    expect(wrapper.text()).not.toContain("研发部");
    expect(wrapper.text()).toContain("当前项目没有部门记录");
    wrapper.unmount();
  });

  it("offers edit only for active departments to a current manager", async () => {
    const inactive = { ...entry, department_id: otherId, state: "INACTIVE" };
    const fetcher = vi.fn().mockImplementation(() => Promise.resolve(
      response({ items: [entry, inactive], next_cursor: null, has_more: false })));
    const reader = await view(await session(), fetcher as typeof fetch);
    expect(reader.wrapper.findAll("button").map((button) => button.text())).not.toContain("修改此部门");
    reader.wrapper.unmount();
    const manager = await view(await session(false, true), fetcher as typeof fetch);
    expect(manager.wrapper.findAll("button").filter((button) => button.text() === "修改此部门")).toHaveLength(1);
    manager.wrapper.unmount();
  });

  it("requires fresh confirmation after editing and submits the read snapshot once", async () => {
    const auth = await session(false, true);
    const patcher = new ProjectDepartmentPatchClient(auth);
    const patch = vi.spyOn(patcher, "patch").mockResolvedValue({ ...entry, name: "新研发部", etag: '"v1"' });
    const fetcher = vi.fn().mockResolvedValue(response({ items: [entry], next_cursor: null, has_more: false }));
    const { wrapper } = await view(auth, fetcher as typeof fetch, patcher);
    await wrapper.get("li button").trigger("click");
    await wrapper.get("#department-edit-name").setValue("新研发部");
    expect(wrapper.get('button[type="submit"]').attributes("disabled")).toBeDefined();
    await wrapper.get('form input[type="checkbox"]').setValue(true);
    await wrapper.get("#department-edit-code").setValue("NEW");
    expect(wrapper.get('button[type="submit"]').attributes("disabled")).toBeDefined();
    await wrapper.get('form input[type="checkbox"]').setValue(true);
    await wrapper.get("form").trigger("submit");
    await flushPromises();
    expect(patch).toHaveBeenCalledExactlyOnceWith(id, entry, { code: "NEW", name: "新研发部" });
    expect(wrapper.text()).toContain("本次修改回执");
    expect(wrapper.text()).toContain("不是当前状态证明");
    expect(wrapper.text()).not.toContain("编号：RD");
    expect(wrapper.find('button[type="submit"]').exists()).toBe(false);
    wrapper.unmount();
  });

  it("locks unknown results until an independent history refresh succeeds", async () => {
    const auth = await session(false, true);
    const patcher = new ProjectDepartmentPatchClient(auth);
    const patch = vi.spyOn(patcher, "patch").mockRejectedValueOnce(
      new ProjectDepartmentPatchError("PROJECT_DEPARTMENT_PATCH_UNCERTAIN"));
    const fetcher = vi.fn().mockResolvedValueOnce(response({ items: [entry], next_cursor: null, has_more: false }))
      .mockResolvedValueOnce(failure(503, "SYSTEM_UNAVAILABLE"))
      .mockResolvedValueOnce(response({ items: [{ ...entry, name: "服务器当前值", etag: '"v1"' }],
        next_cursor: null, has_more: false }));
    const { wrapper } = await view(auth, fetcher as typeof fetch, patcher);
    await wrapper.get("li button").trigger("click");
    await wrapper.get("#department-edit-name").setValue("新研发部");
    await wrapper.get('form input[type="checkbox"]').setValue(true);
    await wrapper.get("form").trigger("submit");
    await flushPromises();
    expect(wrapper.text()).toContain("勿直接重试");
    expect(wrapper.find("li button").exists()).toBe(false);
    await wrapper.get("button").trigger("click");
    await flushPromises();
    expect(wrapper.text()).toContain("成功重新读取部门历史前");
    await wrapper.get("button").trigger("click");
    await flushPromises();
    expect(wrapper.text()).toContain("服务器当前值");
    expect(wrapper.find("li button").exists()).toBe(true);
    expect(patch).toHaveBeenCalledTimes(1);
    wrapper.unmount();
  });

  it("drops a late PATCH receipt when the project changes", async () => {
    const auth = await session(false, true);
    const patcher = new ProjectDepartmentPatchClient(auth);
    let finish!: (value: typeof entry) => void;
    const patch = vi.spyOn(patcher, "patch").mockReturnValueOnce(new Promise((resolve) => { finish = resolve; }));
    const fetcher = vi.fn().mockResolvedValueOnce(response({ items: [entry], next_cursor: null, has_more: false }))
      .mockResolvedValueOnce(response({ items: [], next_cursor: null, has_more: false }));
    const { wrapper, router } = await view(auth, fetcher as typeof fetch, patcher);
    await wrapper.get("li button").trigger("click");
    await wrapper.get('form input[type="checkbox"]').setValue(true);
    await wrapper.get("form").trigger("submit");
    await router.push(`/projects/${otherId}/departments`);
    finish({ ...entry, etag: '"v1"' });
    await flushPromises();
    expect(patch).toHaveBeenCalledTimes(1);
    expect(wrapper.text()).not.toContain("本次修改回执");
    expect(wrapper.text()).toContain("当前项目没有部门记录");
    wrapper.unmount();
  });
});
