import { flushPromises, mount } from "@vue/test-utils";
import { createMemoryHistory } from "vue-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { createAppRouter } from "@/app/router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { ProjectReadClient } from "@/modules/project/api/projectReadClient";
import ProjectDetailView from "./ProjectDetailView.vue";

const id = "01234567-89ab-4cde-8123-456789abcdef";
const otherId = "11234567-89ab-4cde-8123-456789abcdef";
const project = { project_id: id, code: "TEST", name: "合成项目", state: "ACTIVE",
  created_at: "2026-09-28T08:30:00Z", etag: '"v0"' };
function response(data: unknown, etag?: string) {
  return new Response(JSON.stringify({ data, trace_id: id }),
    { headers: { "Content-Type": "application/json", ...(etag ? { ETag: etag } : {}) } });
}
function failure(status: number, code: string) {
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
async function view(auth: SessionClient, path: string, fetcher: typeof fetch) {
  const router = createAppRouter(createMemoryHistory());
  await router.push(path);
  await router.isReady();
  const wrapper = mount(ProjectDetailView, { props: { session: auth, projects: new ProjectReadClient(fetcher) },
    global: { plugins: [router] } });
  await flushPromises();
  return { wrapper, router };
}

describe("ProjectDetailView", () => {
  afterEach(() => vi.restoreAllMocks());

  it("does not fetch with no in-memory identity or restricted password session", async () => {
    const fetcher = vi.fn();
    const absent = await view(new SessionClient(fetcher as typeof fetch), `/projects/${id}`, fetcher as typeof fetch);
    expect(absent.wrapper.text()).toContain("尚未读取当前身份");
    absent.wrapper.unmount();
    const restricted = await view(await session(true), `/projects/${id}`, fetcher as typeof fetch);
    expect(restricted.wrapper.text()).toContain("须先修改密码");
    expect(fetcher).not.toHaveBeenCalled();
    restricted.wrapper.unmount();
  });

  it("loads only server-confirmed detail for direct URL and escapes display text", async () => {
    const fetcher = vi.fn().mockResolvedValue(response({ ...project, name: "<img src=x>" }, project.etag));
    const { wrapper } = await view(await session(), `/projects/${id}`, fetcher as typeof fetch);
    expect(wrapper.text()).toContain("<img src=x>");
    expect(wrapper.find("img").exists()).toBe(false);
    expect(wrapper.get('dl[aria-label="当前授权项目详情"]')).toBeTruthy();
    expect(wrapper.get('a[href="/projects/' + id + '/members"]').text()).toContain("成员历史");
    expect(fetcher).toHaveBeenCalledTimes(1);
    expect(fetcher.mock.calls[0][0]).toBe(`/api/v1/projects/${id}`);
    wrapper.unmount();
  });

  it.each([[404, "RESOURCE_NOT_FOUND", "项目不存在或无权查看"],
    [401, "AUTH_SESSION_EXPIRED", "会话已失效"],
    [403, "LICENSE_OPERATION_DENIED", "当前许可不允许查看项目"]] as const)(
    "safely handles direct URL rejection %s %s", async (status, code, message) => {
      const fetcher = vi.fn().mockResolvedValue(failure(status, code));
      const { wrapper } = await view(await session(), `/projects/${id}`, fetcher as typeof fetch);
      expect(wrapper.get('[role="alert"]').text()).toContain(message);
      expect(wrapper.find("dl").exists()).toBe(false);
      expect(wrapper.html()).not.toContain("private details");
      wrapper.unmount();
    });

  it("rejects an unsafe path ID before network access", async () => {
    const fetcher = vi.fn();
    const { wrapper } = await view(await session(), "/projects/not-an-id", fetcher as typeof fetch);
    expect(wrapper.get('[role="alert"]').text()).toContain("项目标识无效");
    expect(fetcher).not.toHaveBeenCalled();
    wrapper.unmount();
  });

  it("clears prior detail when navigating to another project whose server response is 404", async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(response(project, project.etag))
      .mockResolvedValueOnce(failure(404, "RESOURCE_NOT_FOUND"));
    const { wrapper, router } = await view(await session(), `/projects/${id}`, fetcher as typeof fetch);
    expect(wrapper.text()).toContain(project.name);
    await router.push(`/projects/${otherId}`);
    await flushPromises();
    expect(wrapper.text()).not.toContain(project.name);
    expect(wrapper.get('[role="alert"]').text()).toContain("项目不存在或无权查看");
    expect(fetcher).toHaveBeenCalledTimes(2);
    wrapper.unmount();
  });

  it("rejects a response with a different ID or ETag instead of showing it", async () => {
    const fetcher = vi.fn().mockResolvedValue(response({ ...project, project_id: otherId }, project.etag));
    const { wrapper } = await view(await session(), `/projects/${id}`, fetcher as typeof fetch);
    expect(wrapper.get('[role="alert"]').text()).toContain("暂时无法读取项目");
    expect(wrapper.find("dl").exists()).toBe(false);
    wrapper.unmount();
  });
});
