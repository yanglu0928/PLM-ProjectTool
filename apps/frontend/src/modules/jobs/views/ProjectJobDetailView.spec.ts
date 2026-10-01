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
async function writableSession(cancelReply: Response) {
  const fetcher = vi.fn().mockResolvedValueOnce(response({
    user: { user_id: actorId, username_display: "合成用户" }, deployment_role: "NONE",
    password_change_required: false,
    authorized_projects: [{ project_id: projectId, name: "演示项目", role: "PROJECT_MANAGER" }],
    absolute_expires_at: "2030-01-01T12:00:00Z", idle_expires_at: "2030-01-01T11:00:00Z",
    csrf_token: "a".repeat(64),
  })).mockResolvedValueOnce(cancelReply);
  const auth = new SessionClient(fetcher as typeof fetch);
  await auth.login("user", "synthetic-only");
  return { auth, fetcher };
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
  afterEach(() => { vi.restoreAllMocks(); window.sessionStorage.clear(); });

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

  it("shows current authorized metadata without direct file access or an unconfirmed write", async () => {
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

  it("stores original operation before one explicit cancellation and shows receipt as non-current", async () => {
    const receipt = { job_id: jobId, state: "CANCEL_REQUESTED", changed: true, etag: '"v2"',
      status_url: `/api/v1/projects/${projectId}/jobs/${jobId}` };
    const { auth, fetcher } = await writableSession(response(receipt, '"v2"'));
    const jobs = vi.fn().mockResolvedValue(response(item));
    const { wrapper } = await view(auth, jobs as typeof fetch);
    await wrapper.get("button:nth-of-type(2)").trigger("click");
    await wrapper.get("textarea").setValue("  用户要求取消  ");
    await wrapper.get("input[type=checkbox]").setValue(true);
    await wrapper.get("form").trigger("submit"); await flushPromises();
    expect(fetcher).toHaveBeenCalledTimes(2);
    expect(fetcher.mock.calls[1][0]).toBe(`/api/v1/projects/${projectId}/jobs/${jobId}:cancel`);
    expect(fetcher.mock.calls[1][1]).toMatchObject({ headers: { "If-Match": '"v1"' },
      body: JSON.stringify({ reason: "用户要求取消" }) });
    expect(wrapper.text()).toContain("这不是当前状态");
    expect(window.sessionStorage.length).toBe(0);
    wrapper.unmount();
  });

  it("retains an uncertain original operation across remount and blocks new cancellation", async () => {
    const { auth, fetcher } = await writableSession(new Response("private", { status: 503 }));
    const jobs = vi.fn().mockResolvedValue(response(item));
    const first = await view(auth, jobs as typeof fetch);
    await first.wrapper.get("button:nth-of-type(2)").trigger("click");
    await first.wrapper.get("textarea").setValue("用户要求取消");
    await first.wrapper.get("input[type=checkbox]").setValue(true);
    await first.wrapper.get("form").trigger("submit"); await flushPromises();
    expect(first.wrapper.text()).toContain("已保留原操作号和版本");
    expect(window.sessionStorage.length).toBe(1);
    first.wrapper.unmount();
    const second = await view(auth, jobs as typeof fetch);
    expect(second.wrapper.text()).toContain("待核对的原取消操作");
    expect(second.wrapper.text()).not.toContain("申请取消此任务");
    expect(fetcher).toHaveBeenCalledTimes(2);
    second.wrapper.unmount();
  });

  it("only clears a pending record after current version changes and explicit acknowledgement", async () => {
    const { auth } = await writableSession(new Response("private", { status: 503 }));
    const jobs = vi.fn().mockResolvedValueOnce(response(item))
      .mockResolvedValueOnce(response({ ...item, state: "CANCEL_REQUESTED", etag: '"v2"' }, '"v2"'));
    const { wrapper } = await view(auth, jobs as typeof fetch);
    await wrapper.get("button:nth-of-type(2)").trigger("click");
    await wrapper.get("textarea").setValue("用户要求取消");
    await wrapper.get("input[type=checkbox]").setValue(true);
    await wrapper.get("form").trigger("submit"); await flushPromises();
    expect(wrapper.text()).not.toContain("清除本机待核对记录");
    await wrapper.get("button").trigger("click"); await flushPromises();
    expect(wrapper.text()).toContain("此变化不证明原请求成功");
    await wrapper.get("form input[type=checkbox]").setValue(true);
    await wrapper.get("form").trigger("submit"); await flushPromises();
    expect(window.sessionStorage.length).toBe(0);
    wrapper.unmount();
  });

  it("fails closed before POST if original operation cannot be saved", async () => {
    const { auth, fetcher } = await writableSession(response({}));
    const jobs = vi.fn().mockResolvedValue(response(item));
    const { wrapper } = await view(auth, jobs as typeof fetch);
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("synthetic storage fault"); });
    await wrapper.get("button:nth-of-type(2)").trigger("click");
    await wrapper.get("textarea").setValue("用户要求取消");
    await wrapper.get("input[type=checkbox]").setValue(true);
    await wrapper.get("form").trigger("submit"); await flushPromises();
    expect(wrapper.text()).toContain("取消请求未发送");
    expect(fetcher).toHaveBeenCalledTimes(1);
    wrapper.unmount();
  });

  it("rejects unsafe reason before storing or sending the operation", async () => {
    const { auth, fetcher } = await writableSession(response({}));
    const jobs = vi.fn().mockResolvedValue(response(item));
    const { wrapper } = await view(auth, jobs as typeof fetch);
    await wrapper.get("button:nth-of-type(2)").trigger("click");
    await wrapper.get("textarea").setValue("含有\u200b控制字符");
    await wrapper.get("input[type=checkbox]").setValue(true);
    await wrapper.get("form").trigger("submit"); await flushPromises();
    expect(wrapper.text()).toContain("请求未发送");
    expect(window.sessionStorage.length).toBe(0);
    expect(fetcher).toHaveBeenCalledTimes(1);
    wrapper.unmount();
  });
});
