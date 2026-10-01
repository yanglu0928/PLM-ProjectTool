import { flushPromises, mount } from "@vue/test-utils";
import { createMemoryHistory } from "vue-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import { createAppRouter } from "@/app/router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { JobDetailClient } from "@/modules/jobs/api/jobDetailClient";
import ProjectJobDetailView from "./ProjectJobDetailView.vue";

const actorId = "01234567-89ab-4cde-8123-456789abcdef";
const projectId = "11234567-89ab-4cde-8123-456789abcdef";
const otherProject = "21234567-89ab-4cde-8123-456789abcdef";
const jobId = "31234567-89ab-4cde-8123-456789abcdef";
const otherJob = "41234567-89ab-4cde-8123-456789abcdef";
const item = { job_id: jobId, job_type: "DOCUMENT_PARSE", owner_module: "document", scope: "PROJECT",
  project_id: projectId, state: "RUNNING", progress: null, checkpoint: null, attempt_count: 1,
  retryable: false, error_code: null, result_ref: null, created_at: "2026-10-02T00:00:00Z",
  completed_at: null, etag: '"v1"' };
function response(data: unknown, etag: string | null = '"v1"'): Response {
  return new Response(JSON.stringify({ data, trace_id: actorId }), { status: 200,
    headers: { "Content-Type": "application/json", ...(etag ? { ETag: etag } : {}) } });
}
function failure(status: number, code: string): Response {
  return new Response(JSON.stringify({ error: { code, message: "private detail" }, trace_id: actorId }),
    { status, headers: { "Content-Type": "application/json" } });
}
async function session(restricted = false) {
  const auth = new SessionClient(vi.fn().mockResolvedValue(response({
    user: { user_id: actorId, username_display: "合成用户" }, deployment_role: "NONE",
    password_change_required: restricted,
    authorized_projects: restricted ? [] : [{ project_id: projectId, name: "演示项目", role: "PROJECT_MANAGER" }],
    absolute_expires_at: "2030-01-01T12:00:00Z", idle_expires_at: "2030-01-01T11:00:00Z", csrf_token: "a".repeat(64),
  })) as typeof fetch);
  await auth.login("user", "synthetic-only");
  return auth;
}
async function view(auth: SessionClient, fetcher: typeof fetch) {
  const router = createAppRouter(createMemoryHistory());
  await router.push(`/projects/${projectId}/jobs/${jobId}`); await router.isReady();
  const wrapper = mount(ProjectJobDetailView, { props: { session: auth, jobs: new JobDetailClient(fetcher) },
    global: { plugins: [router] } });
  await flushPromises();
  return { wrapper, router };
}

describe("ProjectJobDetailView", () => {
  afterEach(() => vi.restoreAllMocks());

  it("does not read without identity or before required password change", async () => {
    const fetcher = vi.fn();
    const absent = await view(new SessionClient(fetcher as typeof fetch), fetcher as typeof fetch);
    expect(absent.wrapper.text()).toContain("尚未读取当前身份");
    absent.wrapper.unmount();
    const restricted = await view(await session(true), fetcher as typeof fetch);
    expect(restricted.wrapper.text()).toContain("须先修改密码");
    expect(fetcher).not.toHaveBeenCalled();
    restricted.wrapper.unmount();
  });

  it("shows current authorized metadata and does not offer write or direct file access", async () => {
    const fetcher = vi.fn().mockResolvedValue(response({ ...item, private_payload: "secret" }));
    const { wrapper } = await view(await session(), fetcher as typeof fetch);
    expect(fetcher.mock.calls[0][0]).toBe(`/api/v1/projects/${projectId}/jobs/${jobId}`);
    expect(wrapper.text()).toContain(jobId);
    expect(wrapper.text()).toContain("DOCUMENT_PARSE");
    expect(wrapper.text()).not.toContain("secret");
    expect(wrapper.find("form").exists()).toBe(false);
    expect(wrapper.find(`a[href$="/jobs/${jobId}"]`).exists()).toBe(false);
    wrapper.unmount();
  });

  it("drops old job data after changing route while its response is pending", async () => {
    let resolve!: (value: Response) => void;
    const fetcher = vi.fn().mockImplementationOnce(() => new Promise<Response>(r => { resolve = r; }))
      .mockResolvedValueOnce(response({ ...item, job_id: otherJob }));
    const { wrapper, router } = await view(await session(), fetcher as typeof fetch);
    await router.push(`/projects/${projectId}/jobs/${otherJob}`); await flushPromises();
    resolve(response(item)); await flushPromises();
    expect(wrapper.text()).toContain(otherJob);
    expect(wrapper.text()).not.toContain(jobId);
    wrapper.unmount();
  });

  it("clears old detail when refreshed permission is revoked", async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(response(item)).mockResolvedValueOnce(failure(404, "RESOURCE_NOT_FOUND"));
    const { wrapper } = await view(await session(), fetcher as typeof fetch);
    expect(wrapper.text()).toContain(jobId);
    await wrapper.get("button").trigger("click"); await flushPromises();
    expect(wrapper.find("[role=alert]").text()).toContain("无权查看");
    expect(wrapper.text()).not.toContain(jobId);
    expect(wrapper.text()).not.toContain("private");
    wrapper.unmount();
  });

  it("rejects detail for a different project and clears it on navigation", async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(response(item)).mockResolvedValueOnce(response(item));
    const { wrapper, router } = await view(await session(), fetcher as typeof fetch);
    await router.push(`/projects/${otherProject}/jobs/${jobId}`); await flushPromises();
    expect(wrapper.find("[role=alert]").text()).toContain("暂时无法读取任务详情");
    expect(wrapper.text()).not.toContain(jobId);
    wrapper.unmount();
  });
});
