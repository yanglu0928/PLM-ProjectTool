import { flushPromises, mount } from "@vue/test-utils";
import { createMemoryHistory } from "vue-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { createAppRouter } from "@/app/router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { DocumentReadClient } from "@/modules/document/api/documentReadClient";
import ProjectDocumentListView from "./ProjectDocumentListView.vue";

const id = "01234567-89ab-4cde-8123-456789abcdef";
const otherId = "11234567-89ab-4cde-8123-456789abcdef";
const docId = "21234567-89ab-4cde-8123-456789abcdef";
const cursor = `${"a".repeat(40)}.${"b".repeat(43)}`;
const entry = { document_id: docId, scope: "PROJECT", category: "PROJECT_RECORD", subtype: null,
  title: "调研记录", display_name: "调研.pdf", state: "ACTIVE", latest_version_ref: null,
  effective_version_ref: null, created_at: "2026-09-29T02:00:00Z", etag: '"v0"' };
function response(data: unknown): Response {
  return new Response(JSON.stringify({ data, trace_id: id }), { status: 200,
    headers: { "Content-Type": "application/json" } });
}
function failure(status: number, code: string): Response {
  return new Response(JSON.stringify({ error: { code, message: "private details" }, trace_id: id }),
    { status, headers: { "Content-Type": "application/json" } });
}
async function session(restricted = false, role: string | null = null): Promise<SessionClient> {
  const api = new SessionClient(vi.fn().mockResolvedValue(response({
    user: { user_id: id, username_display: "合成用户" }, deployment_role: "NONE",
    password_change_required: restricted,
    authorized_projects: role ? [{ project_id: id, name: "演示项目", role }] : [],
    absolute_expires_at: "2030-01-01T12:00:00Z", idle_expires_at: "2030-01-01T11:00:00Z",
    csrf_token: "a".repeat(64),
  })) as typeof fetch);
  await api.login("user", "synthetic-only");
  return api;
}
async function view(auth: SessionClient, fetcher: typeof fetch) {
  const router = createAppRouter(createMemoryHistory());
  await router.push(`/projects/${id}/documents`);
  await router.isReady();
  const wrapper = mount(ProjectDocumentListView, { props: { session: auth,
    documents: new DocumentReadClient(fetcher) }, global: { plugins: [router] } });
  await flushPromises();
  return { wrapper, router };
}

describe("ProjectDocumentListView", () => {
  afterEach(() => vi.restoreAllMocks());

  it("does not fetch without identity or before required password change", async () => {
    const fetcher = vi.fn();
    const absent = await view(new SessionClient(fetcher as typeof fetch), fetcher as typeof fetch);
    expect(absent.wrapper.text()).toContain("尚未读取当前身份");
    absent.wrapper.unmount();
    const restricted = await view(await session(true), fetcher as typeof fetch);
    expect(restricted.wrapper.text()).toContain("须先修改密码");
    expect(fetcher).not.toHaveBeenCalled();
    restricted.wrapper.unmount();
  });

  it("renders authorized metadata history without content or location", async () => {
    const archived = { ...entry, document_id: otherId, title: "旧方案", state: "ARCHIVED" };
    const fetcher = vi.fn().mockResolvedValue(response({ items: [entry, archived], next_cursor: null, has_more: false }));
    const { wrapper } = await view(await session(), fetcher as typeof fetch);
    expect(wrapper.text()).toContain("调研记录");
    expect(wrapper.text()).toContain("旧方案");
    expect(wrapper.text()).toContain("已归档");
    expect(wrapper.get(`a[href$="/documents/${docId}"]`).text()).toBe("调研记录");
    expect(wrapper.text()).toContain("不含文档正文");
    expect(fetcher.mock.calls[0]?.[0]).toBe(`/api/v1/projects/${id}/documents?page_size=50`);
    expect(wrapper.text()).not.toContain("storage_locator");
    wrapper.unmount();
  });

  it("shows the new Document upload entry only to a current writable project role", async () => {
    const fetcher = vi.fn().mockResolvedValue(response({ items: [], next_cursor: null, has_more: false }));
    const writer = await view(await session(false, "PROJECT_MANAGER"), fetcher as typeof fetch);
    expect(writer.wrapper.get(`a[href="/projects/${id}/documents/new"]`).text()).toBe("上传新文档");
    writer.wrapper.unmount();
    const reader = await view(await session(false, "CUSTOMER_MEMBER"), fetcher as typeof fetch);
    expect(reader.wrapper.find(`a[href="/projects/${id}/documents/new"]`).exists()).toBe(false);
    reader.wrapper.unmount();
  });

  it("loads next page then refreshes from the beginning", async () => {
    const another = { ...entry, document_id: otherId, title: "接口手册" };
    const fetcher = vi.fn().mockResolvedValueOnce(response({ items: [entry], next_cursor: cursor, has_more: true }))
      .mockResolvedValueOnce(response({ items: [another], next_cursor: null, has_more: false }))
      .mockResolvedValueOnce(response({ items: [another], next_cursor: null, has_more: false }));
    const { wrapper } = await view(await session(), fetcher as typeof fetch);
    await wrapper.get("button:last-of-type").trigger("click");
    await flushPromises();
    expect(wrapper.text()).toContain("调研记录");
    expect(wrapper.text()).toContain("接口手册");
    expect(fetcher.mock.calls[1]?.[0]).toContain(`cursor=${cursor}`);
    await wrapper.get("button:first-of-type").trigger("click");
    await flushPromises();
    expect(wrapper.text()).not.toContain("调研记录");
    expect(wrapper.text()).toContain("接口手册");
    wrapper.unmount();
  });

  it("clears prior pages when next-page access is denied", async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(response({ items: [entry], next_cursor: cursor, has_more: true }))
      .mockResolvedValueOnce(failure(404, "RESOURCE_NOT_FOUND"));
    const { wrapper } = await view(await session(), fetcher as typeof fetch);
    await wrapper.get("button:last-of-type").trigger("click");
    await flushPromises();
    expect(wrapper.text()).not.toContain("调研记录");
    expect(wrapper.get('[role="alert"]').text()).toContain("无权查看");
    wrapper.unmount();
  });

  it("clears prior pages on duplicate ID across pages", async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(response({ items: [entry], next_cursor: cursor, has_more: true }))
      .mockResolvedValueOnce(response({ items: [entry], next_cursor: null, has_more: false }));
    const { wrapper } = await view(await session(), fetcher as typeof fetch);
    await wrapper.get("button:last-of-type").trigger("click");
    await flushPromises();
    expect(wrapper.text()).not.toContain("调研记录");
    expect(wrapper.get('[role="alert"]').text()).toContain("暂时无法读取");
    wrapper.unmount();
  });

  it("drops a late result when the project route changes", async () => {
    let finish!: (value: Response) => void;
    const fetcher = vi.fn().mockReturnValueOnce(new Promise<Response>((resolve) => { finish = resolve; }))
      .mockResolvedValueOnce(response({ items: [], next_cursor: null, has_more: false }));
    const { wrapper, router } = await view(await session(), fetcher as typeof fetch);
    await router.push(`/projects/${otherId}/documents`);
    await flushPromises();
    finish(response({ items: [entry], next_cursor: null, has_more: false }));
    await flushPromises();
    expect(wrapper.text()).not.toContain("调研记录");
    expect(wrapper.text()).toContain("当前项目没有可见文档记录");
    wrapper.unmount();
  });
});
