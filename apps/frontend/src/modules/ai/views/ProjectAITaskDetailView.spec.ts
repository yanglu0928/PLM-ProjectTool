import { flushPromises, mount } from "@vue/test-utils";
import { createMemoryHistory } from "vue-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import { createAppRouter } from "@/app/router";
import { AIReadClient } from "@/modules/ai/api/aiReadClient";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import ProjectAITaskDetailView from "./ProjectAITaskDetailView.vue";

const project = "01234567-89ab-4cde-8123-456789abcdef";
const task = "11234567-89ab-4cde-8123-456789abcdef";
const otherTask = "21234567-89ab-4cde-8123-456789abcdef";
const actor = "31234567-89ab-4cde-8123-456789abcdef";
const document = "41234567-89ab-4cde-8123-456789abcdef";
const version = "51234567-89ab-4cde-8123-456789abcdef";
const job = "61234567-89ab-4cde-8123-456789abcdef";
const invocation = "71234567-89ab-4cde-8123-456789abcdef";
const olderInvocation = "81234567-89ab-4cde-8123-456789abcdef";
const trace = "91234567-89ab-4cde-8123-456789abcdef";
const now = "2026-10-03T12:00:00Z";
const taskView = { ai_task_id: task, project_id: project, task_type: "GAP_ANALYSIS", requested_by: actor,
  input_refs: [{ resource_type: "DOC-02", resource_id: document, version_id: version }],
  prompt_policy_ref: "gap-analysis.v1", prompt_policy_version: 1,
  prompt_version_ref: { prompt_template_id: actor, version_no: 1 }, output_schema_ref: "gap-output.v2",
  context_policy_ref: "project-documents.v1", egress_authorization_ref: actor, job_id: job,
  current_invocation_id: invocation, task_state: "SUCCEEDED", suggestion_state: "AVAILABLE", trace_id: trace,
  error_code: null, retryable: null, requested_at: now, started_at: now, completed_at: now, etag: '"v2"' };
const attempt = { ai_invocation_id: invocation, ai_task_id: task, attempt_no: 2,
  provider: { ai_provider_id: actor, provider_config_version_id: trace },
  model: { ai_model_id: actor, revision: "model-v1" }, prompt_version_ref: { prompt_template_id: trace, version_no: 2 },
  output_schema: { ref: "gap-output.v2", version: 2 }, context: { content_plan_id: actor, content_plan_version: 1,
    context_policy_ref: "project-documents.v1", mode: "NONE", retrieval_run_id: null, context_bundle_id: null },
  invocation_state: "SUCCEEDED", schema_validation_state: "VALID", usage: { input_tokens: 100, output_tokens: 20 },
  latency_ms: 300, error_code: null, retryable: null, created_at: now, started_at: now, completed_at: now };
function response(data: unknown, etag?: string): Response {
  return new Response(JSON.stringify({ data, trace_id: trace }),
    { status: 200, headers: { "Content-Type": "application/json", ...(etag ? { ETag: etag } : {}) } });
}
function failure(status: number, code: string): Response {
  return new Response(JSON.stringify({ error: { code, message: "private detail" }, trace_id: trace }),
    { status, headers: { "Content-Type": "application/json" } });
}
async function session(restricted = false): Promise<SessionClient> {
  const api = new SessionClient(vi.fn().mockResolvedValue(response({ user: { user_id: actor, username_display: "合成用户" },
    deployment_role: "NONE", password_change_required: restricted,
    authorized_projects: restricted ? [] : [{ project_id: project, name: "演示项目", role: "PROJECT_MANAGER" }],
    absolute_expires_at: "2030-01-01T12:00:00Z", idle_expires_at: "2030-01-01T11:00:00Z", csrf_token: "a".repeat(64) })) as typeof fetch);
  await api.login("user", "synthetic-only"); return api;
}
async function view(auth: SessionClient, fetcher: typeof fetch) {
  const router = createAppRouter(createMemoryHistory());
  await router.push(`/projects/${project}/ai/${task}`); await router.isReady();
  const wrapper = mount(ProjectAITaskDetailView, { props: { session: auth, ai: new AIReadClient(fetcher) }, global: { plugins: [router] } });
  await flushPromises(); return { wrapper, router };
}

describe("ProjectAITaskDetailView", () => {
  afterEach(() => vi.restoreAllMocks());

  it("does not read without identity or before required password change", async () => {
    const fetcher = vi.fn();
    const absent = await view(new SessionClient(fetcher as typeof fetch), fetcher as typeof fetch);
    expect(absent.wrapper.text()).toContain("尚未读取当前身份"); absent.wrapper.unmount();
    const restricted = await view(await session(true), fetcher as typeof fetch);
    expect(restricted.wrapper.text()).toContain("须先修改密码"); expect(fetcher).not.toHaveBeenCalled(); restricted.wrapper.unmount();
  });

  it("shows safe Task, fixed inputs, Invocation versions and reuses Job controls", async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(response({ ...taskView, private_payload: "secret" }, '"v2"'))
      .mockResolvedValueOnce(response({ items: [{ ...attempt, provider_response: "secret" }], next_cursor: null, has_more: false }));
    const { wrapper } = await view(await session(), fetcher as typeof fetch);
    expect(wrapper.text()).toContain("AI 输出不是正式业务事实");
    expect(wrapper.get('dl[aria-label="AI任务安全详情"]').text()).toContain("GAP_ANALYSIS");
    expect(wrapper.get(`a[href="/projects/${project}/documents/${document}"]`).text()).toBe(document);
    expect(wrapper.get(`a[href="/projects/${project}/jobs/${job}"]`).text()).toContain(job);
    expect(wrapper.text()).toContain("model-v1"); expect(wrapper.text()).toContain("VALID");
    expect(wrapper.text()).not.toContain("secret"); expect(wrapper.find("form").exists()).toBe(false);
    expect(fetcher.mock.calls.map(call => call[0])).toEqual([
      `/api/v1/projects/${project}/ai-tasks/${task}`,
      `/api/v1/projects/${project}/ai-tasks/${task}/invocations?page_size=50`,
    ]);
    wrapper.unmount();
  });

  it("appends distinct Invocation history", async () => {
    const older = { ...attempt, ai_invocation_id: olderInvocation, attempt_no: 1 };
    const fetcher = vi.fn().mockResolvedValueOnce(response(taskView, '"v2"'))
      .mockResolvedValueOnce(response({ items: [attempt], next_cursor: "aii1.ABC_def", has_more: true }))
      .mockResolvedValueOnce(response({ items: [older], next_cursor: null, has_more: false }));
    const { wrapper } = await view(await session(), fetcher as typeof fetch);
    await wrapper.findAll("button").at(-1)!.trigger("click"); await flushPromises();
    expect(wrapper.text()).toContain(invocation); expect(wrapper.text()).toContain(olderInvocation);
    expect(fetcher.mock.calls[2][0]).toContain("cursor=aii1.ABC_def"); wrapper.unmount();
  });

  it("clears the whole current view when either authority read fails", async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(response(taskView, '"v2"'))
      .mockResolvedValueOnce(failure(404, "RESOURCE_NOT_FOUND"));
    const { wrapper } = await view(await session(), fetcher as typeof fetch);
    expect(wrapper.get('[role="alert"]').text()).toContain("无权查看");
    expect(wrapper.find("dl").exists()).toBe(false); expect(wrapper.html()).not.toContain("private detail"); wrapper.unmount();
  });

  it("discards late results after switching Task route", async () => {
    let first!: (value: Response) => void; let second!: (value: Response) => void;
    const fetcher = vi.fn().mockImplementationOnce(() => new Promise<Response>(done => { first = done; }))
      .mockImplementationOnce(() => new Promise<Response>(done => { second = done; }))
      .mockResolvedValueOnce(failure(404, "RESOURCE_NOT_FOUND"))
      .mockResolvedValueOnce(failure(404, "RESOURCE_NOT_FOUND"));
    const { wrapper, router } = await view(await session(), fetcher as typeof fetch);
    await router.push(`/projects/${project}/ai/${otherTask}`); await flushPromises();
    first(response(taskView, '"v2"')); second(response({ items: [attempt], next_cursor: null, has_more: false }));
    await flushPromises(); expect(wrapper.text()).not.toContain("GAP_ANALYSIS");
    expect(wrapper.get('[role="alert"]').text()).toContain("无权查看"); wrapper.unmount();
  });
});
