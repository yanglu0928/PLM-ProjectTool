import { flushPromises, mount } from "@vue/test-utils";
import { createMemoryHistory } from "vue-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { createAppRouter } from "@/app/router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { DocumentReadClient } from "@/modules/document/api/documentReadClient";
import ProjectDocumentDetailView from "./ProjectDocumentDetailView.vue";

const projectId = "01234567-89ab-4cde-8123-456789abcdef";
const otherProjectId = "11234567-89ab-4cde-8123-456789abcdef";
const documentId = "21234567-89ab-4cde-8123-456789abcdef";
const otherDocumentId = "31234567-89ab-4cde-8123-456789abcdef";
const versionId = "41234567-89ab-4cde-8123-456789abcdef";
const olderVersionId = "51234567-89ab-4cde-8123-456789abcdef";
const cursor = `${"a".repeat(40)}.${"b".repeat(43)}`;
const entry = { document_id: documentId, scope: "PROJECT", category: "PROJECT_RECORD", subtype: "会议纪要",
  title: "项目调研记录", display_name: "调研记录.pdf", state: "ACTIVE", latest_version_ref: versionId,
  effective_version_ref: versionId, created_at: "2026-09-29T02:00:00Z", etag: '"v1"' };
const version = { document_version_id: versionId, version_no: 2, content_sha256: "a".repeat(64),
  size_bytes: 4096, detected_mime: "application/pdf", availability_state: "AVAILABLE",
  supersedes_version_ref: olderVersionId, created_at: "2026-09-29T02:00:00Z", integrity_checked_at: null };
function response(data: unknown, etag = '"v1"'): Response {
  return new Response(JSON.stringify({ data, trace_id: projectId }), { status: 200,
    headers: { "Content-Type": "application/json", ETag: etag } });
}
function failure(status: number, code: string): Response {
  return new Response(JSON.stringify({ error: { code, message: "private details" }, trace_id: projectId }),
    { status, headers: { "Content-Type": "application/json" } });
}
async function session(restricted = false): Promise<SessionClient> {
  const api = new SessionClient(vi.fn().mockResolvedValue(response({
    user: { user_id: projectId, username_display: "合成用户" }, deployment_role: "NONE",
    password_change_required: restricted, authorized_projects: [],
    absolute_expires_at: "2030-01-01T12:00:00Z", idle_expires_at: "2030-01-01T11:00:00Z",
    csrf_token: "a".repeat(64),
  })) as typeof fetch);
  await api.login("user", "synthetic-only");
  return api;
}
async function view(auth: SessionClient, fetcher: typeof fetch, path = `/projects/${projectId}/documents/${documentId}`) {
  const router = createAppRouter(createMemoryHistory());
  await router.push(path);
  await router.isReady();
  const wrapper = mount(ProjectDocumentDetailView, { props: { session: auth,
    documents: new DocumentReadClient(fetcher) }, global: { plugins: [router] } });
  await flushPromises();
  return { wrapper, router };
}
function versionButton(wrapper: Awaited<ReturnType<typeof view>>["wrapper"]) {
  const button = wrapper.findAll("button").find((item) => /查看版本历史|继续加载版本/.test(item.text()));
  if (!button) throw new Error("version button missing");
  return button;
}

describe("ProjectDocumentDetailView", () => {
  afterEach(() => vi.restoreAllMocks());

  it("does not fetch without identity or while password change is required", async () => {
    const fetcher = vi.fn();
    const absent = await view(new SessionClient(fetcher as typeof fetch), fetcher as typeof fetch);
    expect(absent.wrapper.text()).toContain("尚未读取当前身份");
    absent.wrapper.unmount();
    const restricted = await view(await session(true), fetcher as typeof fetch);
    expect(restricted.wrapper.text()).toContain("须先修改密码");
    expect(fetcher).not.toHaveBeenCalled();
    restricted.wrapper.unmount();
  });

  it("reads a direct URL from the server and renders only safe metadata", async () => {
    const fetcher = vi.fn().mockResolvedValue(response({ ...entry, storage_locator: "secret-location" }));
    const { wrapper } = await view(await session(), fetcher as typeof fetch);
    expect(fetcher.mock.calls[0]?.[0]).toBe(`/api/v1/projects/${projectId}/documents/${documentId}`);
    expect(wrapper.text()).toContain("项目调研记录");
    expect(wrapper.text()).toContain("会议纪要");
    expect(wrapper.text()).toContain(versionId);
    expect(wrapper.text()).not.toContain("secret-location");
    expect(wrapper.text()).toContain("仅展示服务器授权的元数据");
    wrapper.unmount();
  });

  it("hides denied documents and does not leak server details", async () => {
    const fetcher = vi.fn().mockResolvedValue(failure(404, "RESOURCE_NOT_FOUND"));
    const { wrapper } = await view(await session(), fetcher as typeof fetch);
    expect(wrapper.find("dl").exists()).toBe(false);
    expect(wrapper.get('[role="alert"]').text()).toContain("无权查看");
    expect(wrapper.text()).not.toContain("private details");
    wrapper.unmount();
  });

  it("rejects an ETag mismatch and clears prior data on refresh failure", async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(response(entry))
      .mockResolvedValueOnce(response(entry, '"v0"'));
    const { wrapper } = await view(await session(), fetcher as typeof fetch);
    expect(wrapper.text()).toContain("项目调研记录");
    await wrapper.get("button").trigger("click");
    await flushPromises();
    expect(wrapper.text()).not.toContain("项目调研记录");
    expect(wrapper.get('[role="alert"]').text()).toContain("暂时无法读取");
    wrapper.unmount();
  });

  it("rejects an invalid document ID before network access", async () => {
    const fetcher = vi.fn();
    const { wrapper } = await view(await session(), fetcher as typeof fetch,
      `/projects/${projectId}/documents/bad`);
    expect(fetcher).not.toHaveBeenCalled();
    expect(wrapper.get('[role="alert"]').text()).toContain("文档标识无效");
    wrapper.unmount();
  });

  it("drops a late result after project or document route changes", async () => {
    let finish!: (value: Response) => void;
    const fetcher = vi.fn().mockReturnValueOnce(new Promise<Response>((resolve) => { finish = resolve; }))
      .mockResolvedValueOnce(failure(404, "RESOURCE_NOT_FOUND"));
    const { wrapper, router } = await view(await session(), fetcher as typeof fetch);
    await router.push(`/projects/${otherProjectId}/documents/${otherDocumentId}`);
    await flushPromises();
    finish(response(entry));
    await flushPromises();
    expect(wrapper.text()).not.toContain("项目调研记录");
    expect(wrapper.get('[role="alert"]').text()).toContain("无权查看");
    wrapper.unmount();
  });

  it("loads available versions on demand without exposing server-only fields", async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(response(entry))
      .mockResolvedValueOnce(response({ items: [{ ...version, storage_locator: "private" }],
        next_cursor: null, has_more: false }));
    const { wrapper } = await view(await session(), fetcher as typeof fetch);
    expect(fetcher).toHaveBeenCalledTimes(1);
    expect(wrapper.find('a[href*="/content"]').exists()).toBe(false);
    await versionButton(wrapper).trigger("click");
    await flushPromises();
    expect(fetcher.mock.calls[1]?.[0]).toBe(
      `/api/v1/projects/${projectId}/documents/${documentId}/versions?page_size=50`);
    expect(wrapper.text()).toContain("版本 2");
    expect(wrapper.text()).toContain("application/pdf");
    expect(wrapper.text()).not.toContain("private");
    const download = wrapper.get('a[href*="/content"]');
    expect(download.attributes("href")).toBe(
      `/api/v1/projects/${projectId}/documents/${documentId}/versions/${versionId}/content`);
    expect(download.attributes("target")).toBeUndefined();
    expect(download.text()).toContain("下载版本 2");
    expect(fetcher).toHaveBeenCalledTimes(2);
    wrapper.unmount();
  });

  it("renders an explicit empty state and a safe server error", async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(response(entry))
      .mockResolvedValueOnce(response({ items: [], next_cursor: null, has_more: false }));
    const empty = await view(await session(), fetcher as typeof fetch);
    await versionButton(empty.wrapper).trigger("click");
    await flushPromises();
    expect(empty.wrapper.text()).toContain("暂无可用版本");
    expect(empty.wrapper.find('a[href*="/content"]').exists()).toBe(false);
    empty.wrapper.unmount();

    const denied = vi.fn().mockResolvedValueOnce(response(entry))
      .mockResolvedValueOnce(failure(404, "RESOURCE_NOT_FOUND"));
    const inaccessible = await view(await session(), denied as typeof fetch);
    await versionButton(inaccessible.wrapper).trigger("click");
    await flushPromises();
    expect(inaccessible.wrapper.get('[role="alert"]').text()).toContain("无权查看");
    expect(inaccessible.wrapper.text()).not.toContain("private details");
    inaccessible.wrapper.unmount();
  });

  it("appends a descending next page and clears history on document refresh", async () => {
    const older = { ...version, document_version_id: olderVersionId, version_no: 1,
      supersedes_version_ref: null };
    const fetcher = vi.fn().mockResolvedValueOnce(response(entry))
      .mockResolvedValueOnce(response({ items: [version], next_cursor: cursor, has_more: true }))
      .mockResolvedValueOnce(response({ items: [older], next_cursor: null, has_more: false }))
      .mockResolvedValueOnce(response(entry));
    const { wrapper } = await view(await session(), fetcher as typeof fetch);
    await versionButton(wrapper).trigger("click");
    await flushPromises();
    await versionButton(wrapper).trigger("click");
    await flushPromises();
    expect(fetcher.mock.calls[2]?.[0]).toContain(`cursor=${cursor}`);
    expect(wrapper.findAll("ol li")).toHaveLength(2);
    await wrapper.get("button").trigger("click");
    await flushPromises();
    expect(wrapper.find("ol").exists()).toBe(false);
    expect(wrapper.text()).toContain("查看版本历史");
    wrapper.unmount();
  });

  it("discards a late version response after a route change", async () => {
    let finish!: (value: Response) => void;
    const fetcher = vi.fn().mockResolvedValueOnce(response(entry))
      .mockReturnValueOnce(new Promise<Response>((resolve) => { finish = resolve; }))
      .mockResolvedValueOnce(failure(404, "RESOURCE_NOT_FOUND"));
    const { wrapper, router } = await view(await session(), fetcher as typeof fetch);
    await versionButton(wrapper).trigger("click");
    await router.push(`/projects/${otherProjectId}/documents/${otherDocumentId}`);
    await flushPromises();
    finish(response({ items: [version], next_cursor: null, has_more: false }));
    await flushPromises();
    expect(wrapper.text()).not.toContain("版本 2");
    expect(wrapper.get('[role="alert"]').text()).toContain("无权查看");
    wrapper.unmount();
  });
});
