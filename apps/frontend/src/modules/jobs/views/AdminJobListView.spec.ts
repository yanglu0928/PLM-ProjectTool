import { flushPromises, mount } from "@vue/test-utils";
import { createMemoryHistory } from "vue-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import { createAppRouter } from "@/app/router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { JobListClient } from "@/modules/jobs/api/jobListClient";
import AdminJobListView from "./AdminJobListView.vue";

const actorId = "01234567-89ab-4cde-8123-456789abcdef";
const globalId = "11234567-89ab-4cde-8123-456789abcdef";
const deploymentId = "21234567-89ab-4cde-8123-456789abcdef";
const token = "j1.ABC_def-123";
const item = { job_id: globalId, job_type: "AUDIT_EXPORT", owner_module: "audit", scope: "GLOBAL",
  project_id: null, state: "SUCCEEDED", progress: null, checkpoint: null, attempt_count: 1,
  retryable: false, error_code: null, result_ref: { type: "AUDIT_EXPORT", id: globalId },
  created_at: "2026-10-02T00:00:00Z", completed_at: "2026-10-02T00:01:00Z", etag: '"v2"' };
function response(data: unknown): Response {
  return new Response(JSON.stringify({ data, trace_id: actorId }), { status: 200, headers: { "Content-Type": "application/json" } });
}
function failure(status: number, code: string): Response {
  return new Response(JSON.stringify({ error: { code, message: "private server detail" }, trace_id: actorId }),
    { status, headers: { "Content-Type": "application/json" } });
}
async function session(admin: boolean) {
  const api = new SessionClient(vi.fn().mockResolvedValue(response({
    user: { user_id: actorId, username_display: "合成用户" }, deployment_role: admin ? "DEPLOYMENT_ADMIN" : "NONE",
    password_change_required: false, authorized_projects: [], absolute_expires_at: "2030-01-01T12:00:00Z",
    idle_expires_at: "2030-01-01T11:00:00Z", csrf_token: "a".repeat(64),
  })) as typeof fetch);
  await api.login("user", "synthetic-only");
  return api;
}
async function view(auth: SessionClient, fetcher: typeof fetch) {
  const router = createAppRouter(createMemoryHistory());
  await router.push("/admin/jobs"); await router.isReady();
  const wrapper = mount(AdminJobListView, { props: { session: auth, jobs: new JobListClient(fetcher) }, global: { plugins: [router] } });
  await flushPromises();
  return wrapper;
}

describe("AdminJobListView", () => {
  afterEach(() => vi.restoreAllMocks());

  it("does not call Job API without current DeploymentAdmin identity", async () => {
    const fetcher = vi.fn();
    const ordinary = await view(await session(false), fetcher as typeof fetch);
    expect(ordinary.text()).toContain("无权查看部署任务");
    ordinary.unmount();
    const absent = await view(new SessionClient(fetcher as typeof fetch), fetcher as typeof fetch);
    expect(absent.text()).toContain("无权查看部署任务");
    expect(fetcher).not.toHaveBeenCalled();
    absent.unmount();
  });

  it("shows only safe Admin metadata; no project or write link", async () => {
    const fetcher = vi.fn().mockResolvedValue(response({ items: [{ ...item, private_payload: "secret" }], next_cursor: null, has_more: false }));
    const wrapper = await view(await session(true), fetcher as typeof fetch);
    expect(fetcher.mock.calls[0][0]).toBe("/api/v1/admin/jobs?page_size=50");
    expect(wrapper.text()).toContain(globalId);
    expect(wrapper.get(`a[href="/admin/jobs/${globalId}"]`).text()).toBe(globalId);
    expect(wrapper.text()).not.toContain("secret");
    expect(wrapper.find("form").exists()).toBe(false);
    wrapper.unmount();
  });

  it("changes Scope and discards an older unfiltered response", async () => {
    let resolve!: (value: Response) => void;
    const fetcher = vi.fn().mockImplementationOnce(() => new Promise<Response>(r => { resolve = r; }))
      .mockResolvedValueOnce(response({ items: [{ ...item, scope: "DEPLOYMENT", job_id: deploymentId }], next_cursor: null, has_more: false }));
    const wrapper = await view(await session(true), fetcher as typeof fetch);
    await wrapper.get("select").setValue("DEPLOYMENT");
    await flushPromises();
    resolve(response({ items: [item], next_cursor: null, has_more: false }));
    await flushPromises();
    expect(fetcher.mock.calls[1][0]).toBe("/api/v1/admin/jobs?page_size=50&scope=DEPLOYMENT");
    expect(wrapper.text()).toContain(deploymentId);
    expect(wrapper.text()).not.toContain(globalId);
    wrapper.unmount();
  });

  it("appends a next page, then clears history on authorization denial", async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(response({ items: [item], next_cursor: token, has_more: true }))
      .mockResolvedValueOnce(failure(401, "AUTH_SESSION_EXPIRED"));
    const wrapper = await view(await session(true), fetcher as typeof fetch);
    await wrapper.get("button:last-of-type").trigger("click"); await flushPromises();
    expect(fetcher.mock.calls[1][0]).toContain(`cursor=${token}`);
    expect(wrapper.find("[role=alert]").text()).toContain("会话已失效");
    expect(wrapper.text()).not.toContain(globalId);
    expect(wrapper.text()).not.toContain("private");
    wrapper.unmount();
  });

  it("rejects a project Job even from an Admin endpoint", async () => {
    const fetcher = vi.fn().mockResolvedValue(response({ items: [{ ...item, scope: "PROJECT", project_id: actorId }], next_cursor: null, has_more: false }));
    const wrapper = await view(await session(true), fetcher as typeof fetch);
    expect(wrapper.find("[role=alert]").text()).toContain("暂时无法读取任务列表");
    expect(wrapper.text()).not.toContain(globalId);
    wrapper.unmount();
  });
});
