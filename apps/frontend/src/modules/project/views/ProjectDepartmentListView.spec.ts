import { flushPromises, mount } from "@vue/test-utils";
import { createMemoryHistory } from "vue-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { createAppRouter } from "@/app/router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { ProjectDepartmentReadClient } from "@/modules/project/api/projectDepartmentReadClient";
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
async function session(restricted = false): Promise<SessionClient> {
  const api = new SessionClient(vi.fn().mockResolvedValue(response({
    user: { user_id: id, username_display: "合成用户" }, deployment_role: "NONE",
    password_change_required: restricted, authorized_projects: [],
    absolute_expires_at: "2030-01-01T12:00:00Z", idle_expires_at: "2030-01-01T11:00:00Z",
    csrf_token: "a".repeat(64),
  })) as typeof fetch);
  await api.login("user", "synthetic-only");
  return api;
}
async function view(auth: SessionClient, fetcher: typeof fetch) {
  const router = createAppRouter(createMemoryHistory());
  await router.push(`/projects/${id}/departments`);
  await router.isReady();
  const wrapper = mount(ProjectDepartmentListView, { props: { session: auth,
    departments: new ProjectDepartmentReadClient(fetcher) }, global: { plugins: [router] } });
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
});
