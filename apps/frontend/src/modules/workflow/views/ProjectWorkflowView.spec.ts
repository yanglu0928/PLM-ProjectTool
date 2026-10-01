import { flushPromises, mount } from "@vue/test-utils";
import { createMemoryHistory } from "vue-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { createAppRouter } from "@/app/router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { WorkflowReadClient, parseWorkflow } from "@/modules/workflow/api/workflowReadClient";
import { WorkflowStartClient, WorkflowStartError } from "@/modules/workflow/api/workflowStartClient";
import ProjectWorkflowView from "./ProjectWorkflowView.vue";

const id = "01234567-89ab-4cde-8123-456789abcdef";
const otherId = "21234567-89ab-4cde-8123-456789abcdef";
const workflowId = "11234567-89ab-4cde-8123-456789abcdef";
const stages = [
  ["HANDOVER", "HANDOVER_BASELINE", "HANDOVER_ISSUES"],
  ["SURVEY", "SURVEY_ACTUAL_SOURCES", "SURVEY_CONCLUSION"],
  ["REQUIREMENT", "REQUIREMENT_FORMAL_VERSIONS", "REQUIREMENT_ACCEPTANCE"],
  ["PROTOTYPE", "PROTOTYPE_SCOPE_DECISIONS", "PROTOTYPE_COVERAGE"],
  ["SOLUTION", "SOLUTION_APPROVED_SET", "SOLUTION_COVERAGE"],
  ["PLAN", "PLAN_APPROVED_BASELINE", "PLAN_WBS_VALIDATION"],
] as const;
function snapshot(started = false) {
  return parseWorkflow({ workflow_id: workflowId, version: 1,
    state: started ? "ACTIVE" : "NOT_STARTED",
    current_stage: started ? "HANDOVER" : null,
    stages: stages.map(([stageKey, first, second], index) => ({
      stage_key: stageKey, order: index + 1,
      state: started && index === 0 ? "ACTIVE" : "NOT_STARTED",
      checklist_items: [first, second].map((itemKey) => ({ item_key: itemKey,
        required: true, state: "PENDING" })),
    })), etag: started ? '"v1"' : '"v0"',
  });
}
function response(data: unknown, tag?: string) {
  return new Response(JSON.stringify({ data, trace_id: id }), {
    headers: { "Content-Type": "application/json", ...(tag ? { ETag: tag } : {}) },
  });
}
function failure(status: number, code: string) {
  return new Response(JSON.stringify({ error: { code, message: "private details" }, trace_id: id }), {
    status, headers: { "Content-Type": "application/json" },
  });
}
async function session(manager = false, restricted = false) {
  const auth = new SessionClient(vi.fn().mockResolvedValue(response({
    user: { user_id: id, username_display: "合成用户" }, deployment_role: "NONE",
    password_change_required: restricted, authorized_projects: manager && !restricted
      ? [{ project_id: id, name: "合成项目", role: "PROJECT_MANAGER" }] : [],
    absolute_expires_at: "2030-01-01T12:00:00Z", idle_expires_at: "2030-01-01T11:00:00Z",
    csrf_token: "a".repeat(64),
  })) as typeof fetch);
  await auth.login("user", "synthetic-only");
  return auth;
}
async function page(auth: SessionClient, reader: WorkflowReadClient, starter?: WorkflowStartClient,
  path = `/projects/${id}/workflow`) {
  const router = createAppRouter(createMemoryHistory());
  await router.push(path); await router.isReady();
  const wrapper = mount(ProjectWorkflowView, { props: { session: auth, workflows: reader, starter },
    global: { plugins: [router] } });
  await flushPromises();
  return { wrapper, router };
}

describe("ProjectWorkflowView", () => {
  afterEach(() => { vi.restoreAllMocks(); window.sessionStorage.clear(); });

  it("does not fetch without in-memory identity or when password change is required", async () => {
    const fetcher = vi.fn();
    const absent = await page(new SessionClient(fetcher as typeof fetch),
      new WorkflowReadClient(fetcher as typeof fetch));
    expect(absent.wrapper.text()).toContain("尚未读取当前身份");
    absent.wrapper.unmount();
    const restricted = await page(await session(false, true),
      new WorkflowReadClient(fetcher as typeof fetch));
    expect(restricted.wrapper.text()).toContain("须先修改密码");
    expect(fetcher).not.toHaveBeenCalled();
    restricted.wrapper.unmount();
  });

  it("shows six safe stages but does not infer approval or offer write to a nonmanager", async () => {
    const fetcher = vi.fn().mockResolvedValue(response(snapshot(), '"v0"'));
    const { wrapper } = await page(await session(), new WorkflowReadClient(fetcher as typeof fetch));
    expect(wrapper.findAll('ol[aria-label="六阶段流程"] > li')).toHaveLength(6);
    expect(wrapper.text()).toContain("HANDOVER_BASELINE");
    expect(wrapper.text()).toContain("不代表客户已确认或项目 Gate 已通过");
    expect(wrapper.find("button").text()).not.toContain("准备启动流程");
    expect(fetcher).toHaveBeenCalledTimes(1);
    wrapper.unmount();
  });

  it("requires a manager confirmation, saves the original Key, then clears stale view on receipt", async () => {
    const auth = await session(true);
    const fetcher = vi.fn().mockResolvedValue(response(snapshot(), '"v0"'));
    const starter = new WorkflowStartClient(auth);
    const submit = vi.spyOn(starter, "start").mockResolvedValue({
      first_result: snapshot(true), is_current_state_proof: false,
    });
    const { wrapper } = await page(auth, new WorkflowReadClient(fetcher as typeof fetch), starter);
    const prepare = wrapper.findAll("button").find((button) => button.text() === "准备启动流程");
    expect(prepare).toBeDefined();
    await prepare!.trigger("click");
    expect(submit).not.toHaveBeenCalled();
    await wrapper.get('form input[type="checkbox"]').setValue(true);
    await wrapper.get("form").trigger("submit");
    await flushPromises();
    expect(submit).toHaveBeenCalledTimes(1);
    expect(submit.mock.calls[0]?.[0]).toBe(id);
    expect(submit.mock.calls[0]?.[1].etag).toBe('"v0"');
    expect(submit.mock.calls[0]?.[2]).toMatch(/^[\x20-\x7e]{16,128}$/);
    expect(wrapper.text()).toContain("不是当前状态或 Gate 通过证明");
    expect(wrapper.text()).toContain("须重新读取当前流程");
    expect(wrapper.find("ol").exists()).toBe(false);
    expect(window.sessionStorage.length).toBe(0);
    wrapper.unmount();
  });

  it("retains an uncertain original operation and retries only that Key after fresh v0 GET", async () => {
    const auth = await session(true);
    const fetcher = vi.fn().mockImplementation(() => Promise.resolve(response(snapshot(), '"v0"')));
    const starter = new WorkflowStartClient(auth);
    const submit = vi.spyOn(starter, "start")
      .mockRejectedValueOnce(new WorkflowStartError("WORKFLOW_START_UNCERTAIN"))
      .mockResolvedValueOnce({ first_result: snapshot(true), is_current_state_proof: false });
    const { wrapper } = await page(auth, new WorkflowReadClient(fetcher as typeof fetch), starter);
    await wrapper.findAll("button").find((button) => button.text() === "准备启动流程")!.trigger("click");
    await wrapper.get('form input[type="checkbox"]').setValue(true);
    await wrapper.get("form").trigger("submit"); await flushPromises();
    expect(wrapper.text()).toContain("原操作号和版本已保留");
    expect(window.sessionStorage.length).toBe(1);
    expect(wrapper.find("ol").exists()).toBe(false);
    await wrapper.findAll("button").find((button) => button.text() === "刷新当前流程")!.trigger("click");
    await flushPromises();
    expect(wrapper.text()).toContain("使用原操作号核查");
    const forms = wrapper.findAll("form");
    expect(forms).toHaveLength(1);
    await forms[0]!.get('input[type="checkbox"]').setValue(true);
    await forms[0]!.trigger("submit"); await flushPromises();
    expect(submit).toHaveBeenCalledTimes(2);
    expect(submit.mock.calls[0]?.[2]).toBe(submit.mock.calls[1]?.[2]);
    expect(window.sessionStorage.length).toBe(0);
    wrapper.unmount();
  });

  it("blocks a malformed saved operation rather than creating another Key", async () => {
    window.sessionStorage.setItem(`plm.workflow.start.pending.${id}`, "{broken");
    const auth = await session(true);
    const fetcher = vi.fn().mockResolvedValue(response(snapshot(), '"v0"'));
    const { wrapper } = await page(auth, new WorkflowReadClient(fetcher as typeof fetch));
    expect(wrapper.text()).toContain("已关闭新的启动请求");
    expect(wrapper.findAll("button").some((button) => button.text() === "准备启动流程")).toBe(false);
    wrapper.unmount();
  });

  it("clears a prior project view after navigating to an unauthorized project", async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(response(snapshot(), '"v0"'))
      .mockResolvedValueOnce(failure(404, "RESOURCE_NOT_FOUND"));
    const { wrapper, router } = await page(await session(true),
      new WorkflowReadClient(fetcher as typeof fetch));
    expect(wrapper.text()).toContain("HANDOVER_BASELINE");
    await router.push(`/projects/${otherId}/workflow`); await flushPromises();
    expect(wrapper.find("ol").exists()).toBe(false);
    expect(wrapper.get('[role="alert"]').text()).toContain("无权查看");
    wrapper.unmount();
  });
});
