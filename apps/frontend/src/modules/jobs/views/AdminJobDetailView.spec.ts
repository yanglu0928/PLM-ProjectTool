import { flushPromises, mount } from "@vue/test-utils";
import { createMemoryHistory } from "vue-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import { createAppRouter } from "@/app/router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { JobDetailClient } from "@/modules/jobs/api/jobDetailClient";
import AdminJobDetailView from "./AdminJobDetailView.vue";

const actorId = "01234567-89ab-4cde-8123-456789abcdef";
const jobId = "11234567-89ab-4cde-8123-456789abcdef";
const otherJob = "21234567-89ab-4cde-8123-456789abcdef";
const item = { job_id: jobId, job_type: "AUDIT_EXPORT", owner_module: "audit", scope: "GLOBAL",
  project_id: null, state: "SUCCEEDED", progress: null, checkpoint: null, attempt_count: 1,
  retryable: false, error_code: null, result_ref: { type: "AUDIT_EXPORT", id: jobId },
  created_at: "2026-10-02T00:00:00Z", completed_at: "2026-10-02T00:01:00Z", etag: '"v2"' };
function response(data: unknown): Response {
  return new Response(JSON.stringify({ data, trace_id: actorId }), { status: 200,
    headers: { "Content-Type": "application/json", ETag: '"v2"' } });
}
function failure(status: number, code: string): Response {
  return new Response(JSON.stringify({ error: { code, message: "private detail" }, trace_id: actorId }),
    { status, headers: { "Content-Type": "application/json" } });
}
async function session(admin: boolean) {
  const auth = new SessionClient(vi.fn().mockResolvedValue(response({
    user: { user_id: actorId, username_display: "合成用户" }, deployment_role: admin ? "DEPLOYMENT_ADMIN" : "NONE",
    password_change_required: false, authorized_projects: [], absolute_expires_at: "2030-01-01T12:00:00Z",
    idle_expires_at: "2030-01-01T11:00:00Z", csrf_token: "a".repeat(64),
  })) as typeof fetch);
  await auth.login("user", "synthetic-only");
  return auth;
}
async function view(auth: SessionClient, fetcher: typeof fetch) {
  const router = createAppRouter(createMemoryHistory());
  await router.push(`/admin/jobs/${jobId}`); await router.isReady();
  const wrapper = mount(AdminJobDetailView, { props: { session: auth, jobs: new JobDetailClient(fetcher) },
    global: { plugins: [router] } });
  await flushPromises();
  return { wrapper, router };
}

describe("AdminJobDetailView", () => {
  afterEach(() => vi.restoreAllMocks());

  it("does not fetch for ordinary or absent identity", async () => {
    const fetcher = vi.fn();
    const ordinary = await view(await session(false), fetcher as typeof fetch);
    expect(ordinary.wrapper.text()).toContain("无权查看部署任务"); ordinary.wrapper.unmount();
    const absent = await view(new SessionClient(fetcher as typeof fetch), fetcher as typeof fetch);
    expect(absent.wrapper.text()).toContain("无权查看部署任务"); absent.wrapper.unmount();
    expect(fetcher).not.toHaveBeenCalled();
  });

  it("shows safe Admin detail but no write or direct result download", async () => {
    const fetcher = vi.fn().mockResolvedValue(response({ ...item, private_payload: "secret" }));
    const { wrapper } = await view(await session(true), fetcher as typeof fetch);
    expect(fetcher.mock.calls[0][0]).toBe(`/api/v1/admin/jobs/${jobId}`);
    expect(wrapper.text()).toContain(jobId);
    expect(wrapper.text()).toContain("逻辑结果引用");
    expect(wrapper.text()).not.toContain("secret");
    expect(wrapper.find("form").exists()).toBe(false);
    expect(wrapper.findAll("a")).toHaveLength(1);
    wrapper.unmount();
  });

  it("drops older response after navigating to another Job", async () => {
    let resolve!: (value: Response) => void;
    const fetcher = vi.fn().mockImplementationOnce(() => new Promise<Response>(r => { resolve = r; }))
      .mockResolvedValueOnce(response({ ...item, job_id: otherJob, result_ref: { type: "AUDIT_EXPORT", id: otherJob } }));
    const { wrapper, router } = await view(await session(true), fetcher as typeof fetch);
    await router.push(`/admin/jobs/${otherJob}`); await flushPromises();
    resolve(response(item)); await flushPromises();
    expect(wrapper.text()).toContain(otherJob);
    expect(wrapper.text()).not.toContain(jobId);
    wrapper.unmount();
  });

  it("clears old detail after a revoked refresh", async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(response(item)).mockResolvedValueOnce(failure(404, "RESOURCE_NOT_FOUND"));
    const { wrapper } = await view(await session(true), fetcher as typeof fetch);
    await wrapper.get("button").trigger("click"); await flushPromises();
    expect(wrapper.find("[role=alert]").text()).toContain("无权查看");
    expect(wrapper.text()).not.toContain(jobId);
    expect(wrapper.text()).not.toContain("private");
    wrapper.unmount();
  });

  it("rejects PROJECT data even if served from the Admin route", async () => {
    const fetcher = vi.fn().mockResolvedValue(response({ ...item, scope: "PROJECT", project_id: actorId }));
    const { wrapper } = await view(await session(true), fetcher as typeof fetch);
    expect(wrapper.find("[role=alert]").text()).toContain("暂时无法读取任务详情");
    expect(wrapper.text()).not.toContain(jobId);
    wrapper.unmount();
  });
});
