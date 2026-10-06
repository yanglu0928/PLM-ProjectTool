import { flushPromises, mount } from "@vue/test-utils";
import { createMemoryHistory } from "vue-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { createAppRouter } from "@/app/router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { WorkflowReadClient, parseWorkflow } from "@/modules/workflow/api/workflowReadClient";
import { WorkflowStartClient, WorkflowStartError } from "@/modules/workflow/api/workflowStartClient";
import { WorkflowChecklistQualificationClient } from "@/modules/workflow/api/workflowChecklistQualificationClient";
import { WorkflowChecklistRecordClient, WorkflowChecklistRecordError,
  type WorkflowChecklistFirstReceipt } from "@/modules/workflow/api/workflowChecklistRecordClient";
import { WorkflowTransitionClient, WorkflowTransitionError,
  type WorkflowTransitionFirstReceipt } from "@/modules/workflow/api/workflowTransitionClient";
import ProjectWorkflowView from "./ProjectWorkflowView.vue";

const id = "01234567-89ab-4cde-8123-456789abcdef";
const otherId = "21234567-89ab-4cde-8123-456789abcdef";
const workflowId = "11234567-89ab-4cde-8123-456789abcdef";
const analysisId = "31234567-89ab-4cde-8123-456789abcdef";
const reviewRoundId = "41234567-89ab-4cde-8123-456789abcdef";
const evidenceId = "51234567-89ab-4cde-8123-456789abcdef";
const checklistRecordId = "61234567-89ab-4cde-8123-456789abcdef";
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
  qualifications?: WorkflowChecklistQualificationClient,
  checklistRecords?: WorkflowChecklistRecordClient,
  transitions?: WorkflowTransitionClient,
  path = `/projects/${id}/workflow`) {
  const router = createAppRouter(createMemoryHistory());
  await router.push(path); await router.isReady();
  const wrapper = mount(ProjectWorkflowView, { props: { session: auth, workflows: reader, starter,
    qualifications, checklistRecords, transitions },
    global: { plugins: [router] } });
  await flushPromises();
  return { wrapper, router };
}
function transitionSnapshot(etag = '"v3"') {
  const current = snapshot(true);
  return parseWorkflow({ ...current, etag,
    stages: current.stages.map((stage, index) => index === 0 ? { ...stage, state: "ACTIVE",
      checklist_items: stage.checklist_items.map((item) => ({ ...item, state: "PASS" })) }
      : stage),
  });
}
function qualification(item: "HANDOVER_BASELINE" | "HANDOVER_ISSUES" = "HANDOVER_BASELINE") {
  return Object.freeze({ workflow_id: workflowId, project_id: id, definition_version: 1 as const,
    stage_key: "HANDOVER" as const, item_key: item, current_item_state: "PENDING" as const,
    workflow_etag: '"v1"', handover_analysis_version_id: analysisId,
    review_round_ref: reviewRoundId, evidence_refs: Object.freeze([evidenceId]) });
}
function checklistReceipt(result: "PASS" | "FAIL" = "PASS"): WorkflowChecklistFirstReceipt {
  return Object.freeze({ is_current_state_proof: false as const, first_record: Object.freeze({
    record_id: checklistRecordId, workflow_id: workflowId, project_id: id,
    definition_version: 1 as const, stage_key: "HANDOVER" as const,
    item_key: "HANDOVER_BASELINE" as const, result, item_version: 1,
    recorded_workflow_version: 2, current_workflow_version: 2,
    supersedes_record_id: null, evidence_refs: result === "PASS" ? [evidenceId] : [],
    review_round_refs: result === "PASS" ? [reviewRoundId] : [], exception_refs: [],
    reason: result === "FAIL" ? "尚未满足" : null,
    impact: result === "FAIL" ? "继续处理" : null,
    occurred_at: "2026-10-06T02:00:00Z", etag: '"v2"',
  }) });
}
function transitionReceipt(): WorkflowTransitionFirstReceipt {
  return Object.freeze({ is_current_state_proof: false as const,
    first_transition: Object.freeze({
      stage_transition_id: otherId, workflow_id: workflowId, project_id: id,
      definition_version: 1 as const, from_stage: "HANDOVER" as const,
      to_stage: "SURVEY" as const, before_workflow_version: 3,
      transitioned_workflow_version: 4, current_workflow_version: 4,
      reason: "交接事实已核对", occurred_at: "2026-10-06T02:00:00Z", etag: '"v4"',
    }) });
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
    expect(wrapper.findAll('ol[aria-label="六阶段流程"] > li > h2').map((heading) => heading.text()))
      .toEqual(["HANDOVER · NOT_STARTED", "SURVEY · NOT_STARTED",
        "REQUIREMENT · NOT_STARTED", "PROTOTYPE · NOT_STARTED",
        "SOLUTION · NOT_STARTED", "PLAN · NOT_STARTED"]);
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

  it("blocks a malformed saved Checklist operation rather than replacing its Key", async () => {
    window.sessionStorage.setItem(`plm.workflow.checklist.pending.${id}`, JSON.stringify({
      actor: id, project: id, workflow: workflowId, item: "HANDOVER_BASELINE",
      result: "PASS", key: "synthetic-checklist-key", etag: '"v1"', evidence: [],
      reason: null, impact: null,
    }));
    const auth = await session(true);
    const reader = new WorkflowReadClient(
      vi.fn().mockResolvedValue(response(snapshot(true), '"v1"')) as typeof fetch,
    );
    const { wrapper } = await page(auth, reader);
    expect(wrapper.text()).toContain("已关闭新的启动请求及检查项记录请求");
    expect(wrapper.findAll("button").some((button) => button.text() === "核验并记录通过"))
      .toBe(false);
    wrapper.unmount();
  });

  it("gets authoritative qualification before PASS and never asks for raw identifiers", async () => {
    const auth = await session(true);
    const reader = new WorkflowReadClient(
      vi.fn().mockImplementation(() => Promise.resolve(
        response(snapshot(true), '"v1"'),
      )) as typeof fetch,
    );
    const qualifications = new WorkflowChecklistQualificationClient();
    const get = vi.spyOn(qualifications, "get").mockResolvedValue(qualification());
    const records = new WorkflowChecklistRecordClient(auth);
    const record = vi.spyOn(records, "record").mockResolvedValue(checklistReceipt());
    const { wrapper } = await page(auth, reader, undefined, qualifications, records);
    await wrapper.findAll("button").find((button) => button.text() === "核验并记录通过")!.trigger("click");
    await flushPromises();
    expect(get).toHaveBeenCalledWith(id, "HANDOVER_BASELINE");
    expect(wrapper.text()).toContain("服务器已按当前版本");
    expect(wrapper.text()).toContain("不会要求手填或展示内部UUID");
    expect(wrapper.text()).not.toContain(evidenceId);
    const form = wrapper.get('form[aria-label="检查项记录确认"]');
    await form.get('input[type="checkbox"]').setValue(true);
    await form.trigger("submit"); await flushPromises();
    expect(record).toHaveBeenCalledTimes(1);
    expect(record.mock.calls[0]?.[1]).toMatchObject({ item_key: "HANDOVER_BASELINE",
      result: "PASS", evidence_refs: [evidenceId], reason: null, impact: null });
    expect(record.mock.calls[0]?.[1].idempotency_key).toMatch(/^[\x20-\x7e]{16,128}$/);
    expect(wrapper.text()).toContain("不是当前状态或 Gate 通过证明");
    expect(wrapper.find("ol").exists()).toBe(false);
    expect(window.sessionStorage.length).toBe(0);
    wrapper.unmount();
  });

  it("prompts for reason and impact on FAIL without requesting qualification", async () => {
    const auth = await session(true);
    const reader = new WorkflowReadClient(
      vi.fn().mockResolvedValue(response(snapshot(true), '"v1"')) as typeof fetch,
    );
    const qualifications = new WorkflowChecklistQualificationClient();
    const get = vi.spyOn(qualifications, "get");
    const records = new WorkflowChecklistRecordClient(auth);
    const record = vi.spyOn(records, "record").mockResolvedValue(checklistReceipt("FAIL"));
    const { wrapper } = await page(auth, reader, undefined, qualifications, records);
    await wrapper.findAll("button").find((button) => button.text() === "记录未通过")!.trigger("click");
    const form = wrapper.get('form[aria-label="检查项记录确认"]');
    await form.get('input[type="checkbox"]').setValue(true);
    await form.trigger("submit");
    expect(wrapper.text()).toContain("请填写未满足原因和影响/后续处理");
    expect(record).not.toHaveBeenCalled();
    const areas = form.findAll("textarea");
    await areas[0]!.setValue("尚未满足"); await areas[1]!.setValue("继续处理");
    await form.trigger("submit"); await flushPromises();
    expect(get).not.toHaveBeenCalled();
    expect(record.mock.calls[0]?.[1]).toMatchObject({ result: "FAIL", evidence_refs: [],
      reason: "尚未满足", impact: "继续处理" });
    wrapper.unmount();
  });

  it("rejects a stale qualification instead of presenting a confirmation", async () => {
    const auth = await session(true);
    const reader = new WorkflowReadClient(
      vi.fn().mockResolvedValue(response(snapshot(true), '"v1"')) as typeof fetch,
    );
    const qualifications = new WorkflowChecklistQualificationClient();
    vi.spyOn(qualifications, "get").mockResolvedValue(Object.freeze({
      ...qualification(), workflow_etag: '"v2"',
    }));
    const { wrapper } = await page(auth, reader, undefined, qualifications);
    await wrapper.findAll("button").find((button) => button.text() === "核验并记录通过")!.trigger("click");
    await flushPromises();
    expect(wrapper.text()).toContain("资格依据与当前流程快照不一致");
    expect(wrapper.find('form[aria-label="检查项记录确认"]').exists()).toBe(false);
    expect(wrapper.find("ol").exists()).toBe(false);
    wrapper.unmount();
  });

  it("retains and retries only the original uncertain Checklist operation", async () => {
    const auth = await session(true);
    const reader = new WorkflowReadClient(
      vi.fn().mockImplementation(() => Promise.resolve(
        response(snapshot(true), '"v1"'),
      )) as typeof fetch,
    );
    const qualifications = new WorkflowChecklistQualificationClient();
    const get = vi.spyOn(qualifications, "get").mockResolvedValue(qualification());
    const records = new WorkflowChecklistRecordClient(auth);
    const record = vi.spyOn(records, "record")
      .mockRejectedValueOnce(new WorkflowChecklistRecordError("WORKFLOW_CHECKLIST_UNCERTAIN"))
      .mockResolvedValueOnce(checklistReceipt());
    const { wrapper } = await page(auth, reader, undefined, qualifications, records);
    await wrapper.findAll("button").find((button) => button.text() === "核验并记录通过")!.trigger("click");
    await flushPromises();
    const first = wrapper.get('form[aria-label="检查项记录确认"]');
    await first.get('input[type="checkbox"]').setValue(true);
    await first.trigger("submit"); await flushPromises();
    expect(wrapper.text()).toContain("原操作号、版本和依据已保留");
    expect(window.sessionStorage.length).toBe(1);
    await wrapper.findAll("button").find((button) => button.text() === "刷新当前流程")!.trigger("click");
    await flushPromises();
    const retry = wrapper.get('form[aria-label="检查项原操作重试"]');
    await retry.get('input[type="checkbox"]').setValue(true);
    await retry.trigger("submit"); await flushPromises();
    expect(record).toHaveBeenCalledTimes(2);
    expect(record.mock.calls[0]?.[1].idempotency_key)
      .toBe(record.mock.calls[1]?.[1].idempotency_key);
    expect(get).toHaveBeenCalledTimes(1);
    expect(window.sessionStorage.length).toBe(0);
    wrapper.unmount();
  });

  it("offers a confirmed Handover transition only after both current items PASS", async () => {
    const auth = await session(true);
    const reader = new WorkflowReadClient(
      vi.fn().mockImplementation(() => Promise.resolve(
        response(transitionSnapshot(), '"v3"'),
      )) as typeof fetch,
    );
    const transitions = new WorkflowTransitionClient(auth);
    const transition = vi.spyOn(transitions, "transition").mockResolvedValue(transitionReceipt());
    const { wrapper } = await page(auth, reader, undefined, undefined, undefined, transitions);
    const prepare = wrapper.findAll("button")
      .find((button) => button.text() === "准备推进至 SURVEY");
    expect(prepare).toBeDefined();
    await prepare!.trigger("click");
    expect(wrapper.text()).toContain("不会接收、展示或生成 Gate UUID");
    expect(wrapper.text()).not.toContain(otherId);
    const form = wrapper.get('form[aria-label="阶段推进确认"]');
    await form.get('input[type="checkbox"]').setValue(true);
    await form.trigger("submit");
    expect(wrapper.text()).toContain("请填写本次推进理由");
    expect(transition).not.toHaveBeenCalled();
    await form.get("textarea").setValue("  交接事实已核对  ");
    await form.trigger("submit"); await flushPromises();
    expect(transition).toHaveBeenCalledTimes(1);
    expect(transition.mock.calls[0]?.[1]).toMatchObject({ reason: "交接事实已核对" });
    expect(transition.mock.calls[0]?.[1].idempotency_key).toMatch(/^[\x20-\x7e]{16,128}$/);
    expect(wrapper.text()).toContain("不是当前流程状态证明");
    expect(wrapper.find("ol").exists()).toBe(false);
    expect(window.sessionStorage.length).toBe(0);
    wrapper.unmount();
  });

  it("does not offer transition while a Handover item is not PASS", async () => {
    const auth = await session(true);
    const reader = new WorkflowReadClient(
      vi.fn().mockResolvedValue(response(snapshot(true), '"v1"')) as typeof fetch,
    );
    const { wrapper } = await page(auth, reader);
    expect(wrapper.findAll("button").some((button) => button.text() === "准备推进至 SURVEY"))
      .toBe(false);
    wrapper.unmount();
  });

  it("retains and retries only the original uncertain transition operation", async () => {
    const auth = await session(true);
    const reader = new WorkflowReadClient(
      vi.fn().mockImplementation(() => Promise.resolve(
        response(transitionSnapshot(), '"v3"'),
      )) as typeof fetch,
    );
    const transitions = new WorkflowTransitionClient(auth);
    const transition = vi.spyOn(transitions, "transition")
      .mockRejectedValueOnce(new WorkflowTransitionError("WORKFLOW_TRANSITION_UNCERTAIN"))
      .mockResolvedValueOnce(transitionReceipt());
    const { wrapper } = await page(auth, reader, undefined, undefined, undefined, transitions);
    await wrapper.findAll("button").find((button) => button.text() === "准备推进至 SURVEY")!
      .trigger("click");
    const first = wrapper.get('form[aria-label="阶段推进确认"]');
    await first.get("textarea").setValue("交接事实已核对");
    await first.get('input[type="checkbox"]').setValue(true);
    await first.trigger("submit"); await flushPromises();
    expect(wrapper.text()).toContain("原操作号、理由和版本已保留");
    expect(window.sessionStorage.length).toBe(1);
    await wrapper.findAll("button").find((button) => button.text() === "刷新当前流程")!
      .trigger("click"); await flushPromises();
    const retry = wrapper.get('form[aria-label="阶段推进原操作重试"]');
    await retry.get('input[type="checkbox"]').setValue(true);
    await retry.trigger("submit"); await flushPromises();
    expect(transition).toHaveBeenCalledTimes(2);
    expect(transition.mock.calls[0]?.[1].idempotency_key)
      .toBe(transition.mock.calls[1]?.[1].idempotency_key);
    expect(transition.mock.calls[0]?.[1].reason).toBe(transition.mock.calls[1]?.[1].reason);
    expect(window.sessionStorage.length).toBe(0);
    wrapper.unmount();
  });

  it("blocks a malformed saved transition rather than replacing its key", async () => {
    window.sessionStorage.setItem(`plm.workflow.transition.pending.${id}`, JSON.stringify({
      actor: id, project: id, workflow: workflowId, key: "short", etag: '"v3"',
      reason: "交接事实已核对", target: "SURVEY",
    }));
    const auth = await session(true);
    const reader = new WorkflowReadClient(
      vi.fn().mockResolvedValue(response(transitionSnapshot(), '"v3"')) as typeof fetch,
    );
    const { wrapper } = await page(auth, reader);
    expect(wrapper.text()).toContain("已关闭新的启动请求及检查项记录请求，并关闭阶段推进请求");
    expect(wrapper.findAll("button").some((button) => button.text() === "准备推进至 SURVEY"))
      .toBe(false);
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
