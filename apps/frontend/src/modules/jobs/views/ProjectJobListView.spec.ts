import { flushPromises, mount } from "@vue/test-utils";
import { createMemoryHistory } from "vue-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import { createAppRouter } from "@/app/router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { JobListClient } from "@/modules/jobs/api/jobListClient";
import ProjectJobListView from "./ProjectJobListView.vue";

const id = "01234567-89ab-4cde-8123-456789abcdef";
const otherId = "11234567-89ab-4cde-8123-456789abcdef";
const jobId = "21234567-89ab-4cde-8123-456789abcdef";
const token = "j1.ABC_def-123";
const item = { job_id: jobId, job_type: "DOCUMENT_PARSE", owner_module: "document", scope: "PROJECT",
  project_id: id, state: "RUNNING", progress: null, checkpoint: null, attempt_count: 1,
  retryable: false, error_code: null, result_ref: null, created_at: "2026-10-02T00:00:00Z",
  completed_at: null, etag: '"v1"' };
function response(data: unknown): Response {
  return new Response(JSON.stringify({ data, trace_id: id }), { status: 200, headers: { "Content-Type": "application/json" } });
}
function failure(status: number, code: string): Response {
  return new Response(JSON.stringify({ error: { code, message: "private server detail" }, trace_id: id }),
    { status, headers: { "Content-Type": "application/json" } });
}
async function session(restricted = false) {
  const api = new SessionClient(vi.fn().mockResolvedValue(response({
    user: { user_id: id, username_display: "合成用户" }, deployment_role: "NONE",
    password_change_required: restricted, authorized_projects: restricted ? [] : [{ project_id: id, name: "演示项目", role: "PROJECT_MANAGER" }],
    absolute_expires_at: "2030-01-01T12:00:00Z", idle_expires_at: "2030-01-01T11:00:00Z", csrf_token: "a".repeat(64),
  })) as typeof fetch);
  await api.login("user", "synthetic-only");
  return api;
}
async function view(auth: SessionClient, fetcher: typeof fetch) {
  const router = createAppRouter(createMemoryHistory());
  await router.push(`/projects/${id}/jobs`);
  await router.isReady();
  const wrapper = mount(ProjectJobListView, { props: { session: auth, jobs: new JobListClient(fetcher) }, global: { plugins: [router] } });
  await flushPromises();
  return { wrapper, router };
}

describe("ProjectJobListView", () => {
  afterEach(() => vi.restoreAllMocks());

  it("does not read without an identity or before password change", async () => {
    const fetcher = vi.fn();
    const absent = await view(new SessionClient(fetcher as typeof fetch), fetcher as typeof fetch);
    expect(absent.wrapper.text()).toContain("尚未读取当前身份");
    absent.wrapper.unmount();
    const restricted = await view(await session(true), fetcher as typeof fetch);
    expect(restricted.wrapper.text()).toContain("须先修改密码");
    expect(fetcher).not.toHaveBeenCalled();
    restricted.wrapper.unmount();
  });

  it("shows only safe Job metadata and no write action", async () => {
    const fetcher = vi.fn().mockResolvedValue(response({ items: [{ ...item, private_payload: "secret" }], next_cursor: null, has_more: false }));
    const { wrapper } = await view(await session(), fetcher as typeof fetch);
    expect(wrapper.text()).toContain("DOCUMENT_PARSE · RUNNING");
    expect(wrapper.text()).toContain(jobId);
    expect(wrapper.get(`a[href="/projects/${id}/jobs/${jobId}"]`).text()).toBe(jobId);
    expect(wrapper.text()).not.toContain("secret");
    expect(wrapper.find("form").exists()).toBe(false);
    expect(fetcher.mock.calls[0][0]).toBe(`/api/v1/projects/${id}/jobs?page_size=50`);
    wrapper.unmount();
  });

  it("appends a distinct next page and refreshes from the start", async () => {
    const second = { ...item, job_id: otherId, state: "FAILED", completed_at: "2026-10-02T00:01:00Z" };
    const fetcher = vi.fn().mockResolvedValueOnce(response({ items: [item], next_cursor: token, has_more: true }))
      .mockResolvedValueOnce(response({ items: [second], next_cursor: null, has_more: false }))
      .mockResolvedValueOnce(response({ items: [second], next_cursor: null, has_more: false }));
    const { wrapper } = await view(await session(), fetcher as typeof fetch);
    await wrapper.get("button:last-of-type").trigger("click");
    await flushPromises();
    expect(wrapper.text()).toContain(jobId);
    expect(wrapper.text()).toContain(otherId);
    expect(fetcher.mock.calls[1][0]).toContain(`cursor=${token}`);
    await wrapper.get("button:first-of-type").trigger("click");
    await flushPromises();
    expect(wrapper.text()).not.toContain(jobId);
    expect(wrapper.text()).toContain(otherId);
    wrapper.unmount();
  });

  it("clears old results if next-page authority is denied", async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(response({ items: [item], next_cursor: token, has_more: true }))
      .mockResolvedValueOnce(failure(404, "RESOURCE_NOT_FOUND"));
    const { wrapper } = await view(await session(), fetcher as typeof fetch);
    await wrapper.get("button:last-of-type").trigger("click");
    await flushPromises();
    expect(wrapper.find("[role=alert]").text()).toContain("无权查看");
    expect(wrapper.text()).not.toContain(jobId);
    expect(wrapper.text()).not.toContain("private");
    wrapper.unmount();
  });

  it("discards an old project's response after navigation", async () => {
    let resolve!: (value: Response) => void;
    const fetcher = vi.fn().mockImplementationOnce(() => new Promise<Response>(r => { resolve = r; }))
      .mockResolvedValueOnce(response({ items: [], next_cursor: null, has_more: false }));
    const { wrapper, router } = await view(await session(), fetcher as typeof fetch);
    await router.push(`/projects/${otherId}/jobs`);
    await flushPromises();
    resolve(response({ items: [item], next_cursor: null, has_more: false }));
    await flushPromises();
    expect(wrapper.text()).not.toContain(jobId);
    expect(fetcher.mock.calls[1][0]).toContain(otherId);
    wrapper.unmount();
  });
});
