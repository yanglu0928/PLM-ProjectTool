import { flushPromises, mount } from "@vue/test-utils";
import { createMemoryHistory } from "vue-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { createAppRouter } from "@/app/router";
import { AIReadClient } from "@/modules/ai/api/aiReadClient";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import ProjectAIWorkbenchView from "./ProjectAIWorkbenchView.vue";

const project = "01234567-89ab-4cde-8123-456789abcdef";
const otherProject = "11234567-89ab-4cde-8123-456789abcdef";
const task = "21234567-89ab-4cde-8123-456789abcdef";
const otherTask = "31234567-89ab-4cde-8123-456789abcdef";
const actor = "41234567-89ab-4cde-8123-456789abcdef";
const document = "51234567-89ab-4cde-8123-456789abcdef";
const version = "61234567-89ab-4cde-8123-456789abcdef";
const job = "71234567-89ab-4cde-8123-456789abcdef";
const trace = "81234567-89ab-4cde-8123-456789abcdef";
const cursor = "ait1.ABC_def-123";
const item = { ai_task_id: task, project_id: project, task_type: "GAP_ANALYSIS", requested_by: actor,
  input_refs: [{ resource_type: "DOC-02", resource_id: document, version_id: version }],
  prompt_policy_ref: "gap-analysis.v1", prompt_policy_version: 1,
  prompt_version_ref: { prompt_template_id: actor, version_no: 1 }, output_schema_ref: "gap-output.v2",
  context_policy_ref: "project-documents.v1", egress_authorization_ref: actor, job_id: job,
  current_invocation_id: actor, task_state: "SUCCEEDED", suggestion_state: "AVAILABLE",
  trace_id: trace, error_code: null, retryable: null, requested_at: "2026-10-03T12:00:00Z",
  started_at: "2026-10-03T12:00:00Z", completed_at: "2026-10-03T12:00:01Z", etag: '"v2"' };
function response(data: unknown): Response {
  return new Response(JSON.stringify({ data, trace_id: trace }), { status: 200, headers: { "Content-Type": "application/json" } });
}
function failure(status: number, code: string): Response {
  return new Response(JSON.stringify({ error: { code, message: "private detail" }, trace_id: trace }),
    { status, headers: { "Content-Type": "application/json" } });
}
async function session(restricted = false): Promise<SessionClient> {
  const api = new SessionClient(vi.fn().mockResolvedValue(response({
    user: { user_id: actor, username_display: "合成用户" }, deployment_role: "NONE",
    password_change_required: restricted, authorized_projects: restricted ? [] : [{ project_id: project, name: "演示项目", role: "PROJECT_MANAGER" }],
    absolute_expires_at: "2030-01-01T12:00:00Z", idle_expires_at: "2030-01-01T11:00:00Z", csrf_token: "a".repeat(64),
  })) as typeof fetch);
  await api.login("user", "synthetic-only");
  return api;
}
async function view(auth: SessionClient, fetcher: typeof fetch) {
  const router = createAppRouter(createMemoryHistory());
  await router.push(`/projects/${project}/ai`); await router.isReady();
  const wrapper = mount(ProjectAIWorkbenchView, { props: { session: auth, ai: new AIReadClient(fetcher) },
    global: { plugins: [router] } });
  await flushPromises();
  return { wrapper, router };
}

describe("ProjectAIWorkbenchView", () => {
  afterEach(() => vi.restoreAllMocks());

  it("does not read without identity or before required password change", async () => {
    const fetcher = vi.fn();
    const absent = await view(new SessionClient(fetcher as typeof fetch), fetcher as typeof fetch);
    expect(absent.wrapper.text()).toContain("尚未读取当前身份"); absent.wrapper.unmount();
    const restricted = await view(await session(true), fetcher as typeof fetch);
    expect(restricted.wrapper.text()).toContain("须先修改密码");
    expect(fetcher).not.toHaveBeenCalled(); restricted.wrapper.unmount();
  });

  it("shows only safe read-only Task status and the non-formal warning", async () => {
    const fetcher = vi.fn().mockResolvedValue(response({ items: [{ ...item, private_payload: "secret" }], next_cursor: null, has_more: false }));
    const { wrapper } = await view(await session(), fetcher as typeof fetch);
    expect(wrapper.text()).toContain("AI 输出不是正式业务事实");
    expect(wrapper.text()).toContain("GAP_ANALYSIS");
    expect(wrapper.text()).toContain("建议待查看");
    expect(wrapper.get(`a[href="/projects/${project}/jobs/${job}"]`).text()).toBe(job);
    expect(wrapper.text()).not.toContain("secret");
    expect(wrapper.find("form").exists()).toBe(false);
    expect(wrapper.text()).not.toContain("接受建议");
    expect(fetcher.mock.calls[0][0]).toBe(`/api/v1/projects/${project}/ai-tasks?page_size=50`);
    wrapper.unmount();
  });

  it("appends a distinct next page and refreshes from the start", async () => {
    const older = { ...item, ai_task_id: otherTask, task_state: "FAILED", suggestion_state: "NONE",
      error_code: "PROVIDER_TIMEOUT", retryable: true, requested_at: "2026-10-03T11:00:00Z",
      started_at: "2026-10-03T11:00:00Z", completed_at: "2026-10-03T11:00:01Z" };
    const fetcher = vi.fn().mockResolvedValueOnce(response({ items: [item], next_cursor: cursor, has_more: true }))
      .mockResolvedValueOnce(response({ items: [older], next_cursor: null, has_more: false }))
      .mockResolvedValueOnce(response({ items: [older], next_cursor: null, has_more: false }));
    const { wrapper } = await view(await session(), fetcher as typeof fetch);
    await wrapper.findAll("button").at(-1)!.trigger("click"); await flushPromises();
    expect(wrapper.text()).toContain(task); expect(wrapper.text()).toContain(otherTask);
    expect(wrapper.text()).toContain("可按受控流程重试");
    expect(fetcher.mock.calls[1][0]).toContain(`cursor=${cursor}`);
    await wrapper.findAll("button")[0]!.trigger("click"); await flushPromises();
    expect(wrapper.text()).not.toContain(task); expect(wrapper.text()).toContain(otherTask);
    wrapper.unmount();
  });

  it("clears prior tasks when later authorization is denied", async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(response({ items: [item], next_cursor: cursor, has_more: true }))
      .mockResolvedValueOnce(failure(404, "RESOURCE_NOT_FOUND"));
    const { wrapper } = await view(await session(), fetcher as typeof fetch);
    await wrapper.findAll("button").at(-1)!.trigger("click"); await flushPromises();
    expect(wrapper.get('[role="alert"]').text()).toContain("无权查看");
    expect(wrapper.text()).not.toContain(task); expect(wrapper.html()).not.toContain("private detail");
    wrapper.unmount();
  });

  it("discards an old project's late response after navigation", async () => {
    let resolve!: (value: Response) => void;
    const fetcher = vi.fn().mockImplementationOnce(() => new Promise<Response>(done => { resolve = done; }))
      .mockResolvedValueOnce(response({ items: [], next_cursor: null, has_more: false }));
    const { wrapper, router } = await view(await session(), fetcher as typeof fetch);
    await router.push(`/projects/${otherProject}/ai`); await flushPromises();
    resolve(response({ items: [item], next_cursor: null, has_more: false })); await flushPromises();
    expect(wrapper.text()).not.toContain(task);
    expect(fetcher.mock.calls[1][0]).toContain(otherProject);
    wrapper.unmount();
  });
});
