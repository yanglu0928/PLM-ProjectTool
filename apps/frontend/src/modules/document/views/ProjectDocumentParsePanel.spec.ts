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
const parseId = "61234567-89ab-4cde-8123-456789abcdef";
const olderParseId = "71234567-89ab-4cde-8123-456789abcdef";
const jobId = "81234567-89ab-4cde-8123-456789abcdef";
const cursor = `${"a".repeat(800)}.${"b".repeat(43)}`;
const document = { document_id: documentId, scope: "PROJECT", category: "PROJECT_RECORD", subtype: null,
  title: "合成项目记录", display_name: "record.pdf", state: "ACTIVE", latest_version_ref: versionId,
  effective_version_ref: versionId, created_at: "2026-09-30T01:00:00Z", etag: '"v1"' };
const latest = { document_version_id: versionId, version_no: 2, content_sha256: "a".repeat(64),
  size_bytes: 50, detected_mime: "application/pdf", availability_state: "AVAILABLE",
  supersedes_version_ref: olderVersionId, created_at: "2026-09-30T01:02:00Z", integrity_checked_at: null };
const older = { ...latest, document_version_id: olderVersionId, version_no: 1,
  supersedes_version_ref: null, created_at: "2026-09-30T01:00:00Z" };
const pending = { parse_record_id: parseId, parser_profile: "pdf", parser_version: "1.0",
  parse_state: "PENDING", attempt_no: 1, job_ref: jobId, result_ref: null,
  error_code: null, retryable: null, created_at: "2026-09-30T01:03:00Z",
  started_at: null, completed_at: null };
const failed = { ...pending, parse_record_id: olderParseId, parse_state: "FAILED",
  started_at: "2026-09-30T01:03:01Z", completed_at: "2026-09-30T01:03:02Z",
  error_code: "PARSER_FAILED", retryable: true };

function response(data: unknown): Response {
  return new Response(JSON.stringify({ data, trace_id: projectId }), { status: 200,
    headers: { "Content-Type": "application/json", ETag: '"v1"' } });
}
function denied(): Response {
  return new Response(JSON.stringify({ error: { code: "RESOURCE_NOT_FOUND", message: "private details" },
    trace_id: projectId }), { status: 404, headers: { "Content-Type": "application/json" } });
}
function expired(): Response {
  return new Response(JSON.stringify({ error: { code: "AUTH_SESSION_EXPIRED", message: "private details" },
    trace_id: projectId }), { status: 401, headers: { "Content-Type": "application/json" } });
}
async function session(): Promise<SessionClient> {
  const api = new SessionClient(vi.fn().mockResolvedValue(response({
    user: { user_id: projectId, username_display: "合成用户" }, deployment_role: "NONE",
    password_change_required: false, authorized_projects: [{ project_id: projectId,
      name: "合成项目", role: "PROJECT_MANAGER" }],
    absolute_expires_at: "2030-01-01T12:00:00Z", idle_expires_at: "2030-01-01T11:00:00Z",
    csrf_token: "a".repeat(64),
  })) as typeof fetch);
  await api.login("synthetic", "synthetic-only");
  return api;
}
async function view(fetcher: typeof fetch) {
  const router = createAppRouter(createMemoryHistory());
  await router.push(`/projects/${projectId}/documents/${documentId}`);
  await router.isReady();
  const wrapper = mount(ProjectDocumentDetailView, { props: { session: await session(),
    documents: new DocumentReadClient(fetcher) }, global: { plugins: [router] } });
  await flushPromises();
  return { wrapper, router };
}
function button(wrapper: Awaited<ReturnType<typeof view>>["wrapper"], label: string) {
  const result = wrapper.findAll("button").find((item) => item.text().includes(label));
  if (!result) throw new Error(`missing ${label}`);
  return result;
}

describe("ProjectDocumentDetailView ParseRecord panel", () => {
  afterEach(() => vi.restoreAllMocks());

  it("loads fixed-version status only on demand and does not claim Evidence is ready", async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(response(document))
      .mockResolvedValueOnce(response({ items: [latest], next_cursor: null, has_more: false }))
      .mockResolvedValueOnce(response({ items: [{ ...pending, storage_locator: "private" }],
        next_cursor: null, has_more: false }));
    const { wrapper } = await view(fetcher as typeof fetch);
    await button(wrapper, "查看版本历史").trigger("click");
    await flushPromises();
    expect(fetcher).toHaveBeenCalledTimes(2);
    await button(wrapper, "查看版本 2 解析状态").trigger("click");
    await flushPromises();
    expect(fetcher.mock.calls[2]?.[0]).toBe(
      `/api/v1/projects/${projectId}/documents/${documentId}/versions/${versionId}/parses?page_size=50`);
    expect(wrapper.text()).toContain("待处理");
    expect(wrapper.text()).toContain("不表示解析完成");
    expect(wrapper.text()).not.toContain("private");
    expect(wrapper.text()).not.toContain("storage_locator");
    wrapper.unmount();
  });

  it("switches versions without showing a late result from the previous version", async () => {
    let finish!: (value: Response) => void;
    const fetcher = vi.fn().mockResolvedValueOnce(response(document))
      .mockResolvedValueOnce(response({ items: [latest, older], next_cursor: null, has_more: false }))
      .mockReturnValueOnce(new Promise<Response>((resolve) => { finish = resolve; }))
      .mockResolvedValueOnce(response({ items: [], next_cursor: null, has_more: false }));
    const { wrapper } = await view(fetcher as typeof fetch);
    await button(wrapper, "查看版本历史").trigger("click");
    await flushPromises();
    await button(wrapper, "查看版本 2 解析状态").trigger("click");
    await button(wrapper, "查看版本 1 解析状态").trigger("click");
    await flushPromises();
    finish(response({ items: [pending], next_cursor: null, has_more: false }));
    await flushPromises();
    expect(fetcher.mock.calls[3]?.[0]).toContain(`/versions/${olderVersionId}/parses`);
    expect(wrapper.text()).toContain("版本 1 的解析记录");
    expect(wrapper.text()).toContain("暂无解析记录");
    expect(wrapper.find('ol[aria-label="固定版本解析记录"]').exists()).toBe(false);
    wrapper.unmount();
  });

  it("paginates and refreshes a single version, clearing old status", async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(response(document))
      .mockResolvedValueOnce(response({ items: [latest], next_cursor: null, has_more: false }))
      .mockResolvedValueOnce(response({ items: [pending], next_cursor: cursor, has_more: true }))
      .mockResolvedValueOnce(response({ items: [failed], next_cursor: null, has_more: false }))
      .mockResolvedValueOnce(response({ items: [], next_cursor: null, has_more: false }));
    const { wrapper } = await view(fetcher as typeof fetch);
    await button(wrapper, "查看版本历史").trigger("click");
    await flushPromises();
    await button(wrapper, "查看版本 2 解析状态").trigger("click");
    await flushPromises();
    await button(wrapper, "继续加载解析记录").trigger("click");
    await flushPromises();
    expect(fetcher.mock.calls[3]?.[0]).toContain(`cursor=${cursor}`);
    expect(wrapper.findAll('ol[aria-label="固定版本解析记录"] li')).toHaveLength(2);
    await button(wrapper, "刷新解析状态").trigger("click");
    await flushPromises();
    expect(wrapper.text()).toContain("暂无解析记录");
    expect(wrapper.text()).not.toContain("PARSER_FAILED");
    wrapper.unmount();
  });

  it("clears previously shown ParseRecords when a refresh is denied", async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(response(document))
      .mockResolvedValueOnce(response({ items: [latest], next_cursor: null, has_more: false }))
      .mockResolvedValueOnce(response({ items: [pending], next_cursor: null, has_more: false }))
      .mockResolvedValueOnce(denied());
    const { wrapper } = await view(fetcher as typeof fetch);
    await button(wrapper, "查看版本历史").trigger("click");
    await flushPromises();
    await button(wrapper, "查看版本 2 解析状态").trigger("click");
    await flushPromises();
    expect(wrapper.text()).toContain(parseId);
    await button(wrapper, "刷新解析状态").trigger("click");
    await flushPromises();
    expect(wrapper.text()).not.toContain(parseId);
    expect(wrapper.get('[role="alert"]').text()).toContain("无权查看");
    expect(wrapper.text()).not.toContain("private details");
    wrapper.unmount();
  });

  it("clears stale ParseRecords on a 401 session expiry", async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(response(document))
      .mockResolvedValueOnce(response({ items: [latest], next_cursor: null, has_more: false }))
      .mockResolvedValueOnce(response({ items: [pending], next_cursor: null, has_more: false }))
      .mockResolvedValueOnce(expired());
    const { wrapper } = await view(fetcher as typeof fetch);
    await button(wrapper, "查看版本历史").trigger("click");
    await flushPromises();
    await button(wrapper, "查看版本 2 解析状态").trigger("click");
    await flushPromises();
    await button(wrapper, "刷新解析状态").trigger("click");
    await flushPromises();
    expect(wrapper.text()).not.toContain(parseId);
    expect(wrapper.get('[role="alert"]').text()).toContain("重新登录");
    wrapper.unmount();
  });

  it("discards late ParseRecords after changing the project/document route", async () => {
    let finish!: (value: Response) => void;
    const fetcher = vi.fn().mockResolvedValueOnce(response(document))
      .mockResolvedValueOnce(response({ items: [latest], next_cursor: null, has_more: false }))
      .mockReturnValueOnce(new Promise<Response>((resolve) => { finish = resolve; }))
      .mockResolvedValueOnce(denied());
    const { wrapper, router } = await view(fetcher as typeof fetch);
    await button(wrapper, "查看版本历史").trigger("click");
    await flushPromises();
    await button(wrapper, "查看版本 2 解析状态").trigger("click");
    await router.push(`/projects/${otherProjectId}/documents/${otherDocumentId}`);
    await flushPromises();
    finish(response({ items: [pending], next_cursor: null, has_more: false }));
    await flushPromises();
    expect(wrapper.text()).not.toContain(parseId);
    expect(wrapper.text()).not.toContain("版本 2 的解析记录");
    wrapper.unmount();
  });
});
