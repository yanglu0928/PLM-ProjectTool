import { flushPromises, mount } from "@vue/test-utils";
import { createMemoryHistory } from "vue-router";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { createAppRouter } from "@/app/router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { ProjectMemberReadClient } from "@/modules/project/api/projectMemberReadClient";
import { PlanVersionReadClient } from "@/modules/plan/api/planVersionReadClient";
import { PlanVersionWriteClient, PlanVersionWriteError } from "@/modules/plan/api/planVersionWriteClient";
import ProjectPlanVersionSubmitReviewView from "./ProjectPlanVersionSubmitReviewView.vue";

const project = "01234567-89ab-4cde-8123-456789abcdef"; const plan = "11234567-89ab-4cde-8123-456789abcdef";
const version = "21234567-89ab-4cde-8123-456789abcdef"; const actor = "31234567-89ab-4cde-8123-456789abcdef";
const customer = "41234567-89ab-4cde-8123-456789abcdef"; const trace = "51234567-89ab-4cde-8123-456789abcdef";
const row = { plan_version_id: version, plan_id: plan, project_id: project, version_no: 1, version_state: "DRAFT",
  created_by: actor, supersedes_version_ref: null, review_ref: null, review_round_ref: null,
  created_at: "2026-10-26T00:00:00Z", calendar_ref: "CN_WORKDAY", approved_solution_refs: [], wbs_items: [],
  dependencies: [], milestones: [], exclusions: [] };
const member = (userId: string, name: string, role: string, state = "ACTIVE") => ({ member_id: `${userId.slice(0, 8)}-aaaa-4aaa-8aaa-aaaaaaaaaaaa`,
  user: { user_id: userId, display_name: name }, role, state });
const customerRow = member(customer, "客户成员甲", "CUSTOMER_MEMBER");
const otherCustomer = member("61234567-89ab-4cde-8123-456789abcdef", "停用客户", "CUSTOMER_MANAGER", "SUSPENDED");
const managerRow = member("71234567-89ab-4cde-8123-456789abcdef", "项目负责人", "PROJECT_MANAGER");
const receipt = { review_id: "81234567-89ab-4cde-8123-456789abcdef", review_round_id: "91234567-89ab-4cde-8123-456789abcdef",
  subject_type: "PLN-02", project_id: project, plan_id: plan, plan_version_id: version, policy_ref: "PLAN_VERSION_ALL_V1",
  reviewer_ids: [customer], state: "IN_REVIEW", round_no: 1, review_etag: '"v1"', submitted_by: actor,
  submitted_at: "2026-10-26T01:02:03Z" };
function response(data: unknown) { return new Response(JSON.stringify({ data, trace_id: trace }), { status: 200, headers: { "Content-Type": "application/json" } }); }
async function session(role = "PROJECT_MANAGER") {
  const api = new SessionClient(vi.fn().mockResolvedValue(response({ user: { user_id: actor, username_display: "负责人" },
    deployment_role: "NONE", password_change_required: false, authorized_projects: [{ project_id: project, name: "项目", role }],
    absolute_expires_at: "2030-01-01T12:00:00Z", idle_expires_at: "2030-01-01T11:00:00Z", csrf_token: "a".repeat(64) })) as typeof fetch);
  await api.login("user", "synthetic-only"); return api;
}
function router() { return createAppRouter(createMemoryHistory()); }
function memberReader() { return { list: vi.fn().mockResolvedValue({ items: [customerRow, otherCustomer, managerRow], next_cursor: null, has_more: false }) }; }
function navigate(appRouter: ReturnType<typeof router>) { return appRouter.push(`/projects/${project}/plans/${plan}/versions/${version}/submit-review`).then(() => appRouter.isReady()); }

describe("PlanVersion atomic Review submission page", () => {
  beforeEach(() => { window.sessionStorage.clear(); });
  it("filters complete member history and requires explicit confirmation before atomic submit", async () => {
    const appRouter = router(); await navigate(appRouter); const members = memberReader();
    const submitter = { submitReview: vi.fn().mockResolvedValue(receipt) };
    const view = mount(ProjectPlanVersionSubmitReviewView, { props: { session: await session(),
      reader: { detail: vi.fn().mockResolvedValue(row) } as unknown as PlanVersionReadClient,
      members: members as unknown as ProjectMemberReadClient, submitter: submitter as unknown as PlanVersionWriteClient }, global: { plugins: [appRouter] } });
    await flushPromises(); expect(view.text()).toContain("不是批准或客户签署");
    await view.get("button").trigger("click"); await flushPromises(); expect(members.list).toHaveBeenCalledWith(project, null);
    expect(view.text()).toContain("客户成员甲"); expect(view.text()).not.toContain("停用客户"); expect(view.text()).not.toContain("项目负责人");
    await view.find('input[type="checkbox"]').setValue(true); const submitButton = view.findAll("button").find(item => item.text() === "确认提交正式评审")!;
    expect(submitButton.attributes("disabled")).toBeDefined();
    await view.findAll('input[type="checkbox"]')[1]!.setValue(true); await submitButton.trigger("click"); await flushPromises();
    expect(submitter.submitReview).toHaveBeenCalledWith(project, plan, version, [customer], expect.stringMatching(/^plan-review-/));
    expect(view.text()).toContain("尚未批准"); expect(view.text()).toContain(receipt.review_id); expect(window.sessionStorage.length).toBe(0); view.unmount();
  });

  it("retries an uncertain submit with the original reviewer set and operation key", async () => {
    const appRouter = router(); await navigate(appRouter); const submitter = { submitReview: vi.fn()
      .mockRejectedValueOnce(new PlanVersionWriteError("SYSTEM_UNAVAILABLE")).mockResolvedValueOnce(receipt) };
    const view = mount(ProjectPlanVersionSubmitReviewView, { props: { session: await session(),
      reader: { detail: vi.fn().mockResolvedValue(row) } as unknown as PlanVersionReadClient, members: memberReader() as unknown as ProjectMemberReadClient,
      submitter: submitter as unknown as PlanVersionWriteClient }, global: { plugins: [appRouter] } });
    await flushPromises(); await view.get("button").trigger("click"); await flushPromises();
    await view.find('input[type="checkbox"]').setValue(true); await view.findAll('input[type="checkbox"]')[1]!.setValue(true);
    await view.findAll("button").find(item => item.text() === "确认提交正式评审")!.trigger("click"); await flushPromises();
    const saved = JSON.parse(window.sessionStorage.getItem(`plm.plan.version.review.pending.${actor}.${project}.${plan}.${version}`)!);
    expect(view.text()).toContain("原送审结果未确认"); expect(view.text()).toContain("按原操作号重试送审");
    await view.find('input[type="checkbox"]').setValue(true);
    await view.findAll("button").find(item => item.text() === "按原操作号重试送审")!.trigger("click"); await flushPromises();
    expect(submitter.submitReview.mock.calls[0]).toEqual([project, plan, version, [customer], saved.key]);
    expect(submitter.submitReview.mock.calls[1]).toEqual([project, plan, version, [customer], saved.key]);
    expect(view.text()).toContain("尚未批准"); view.unmount();
  });

  it("does not load reviewers or expose submission to implementation members", async () => {
    const appRouter = router(); await navigate(appRouter); const members = memberReader(); const submitter = { submitReview: vi.fn() };
    const view = mount(ProjectPlanVersionSubmitReviewView, { props: { session: await session("IMPLEMENTATION_MEMBER"),
      reader: { detail: vi.fn() } as unknown as PlanVersionReadClient, members: members as unknown as ProjectMemberReadClient,
      submitter: submitter as unknown as PlanVersionWriteClient }, global: { plugins: [appRouter] } });
    await flushPromises(); expect(view.text()).toContain("仅当前项目负责人"); expect(members.list).not.toHaveBeenCalled();
    expect(submitter.submitReview).not.toHaveBeenCalled(); view.unmount();
  });

  it("fails closed when member pagination repeats and exposes no reviewer choices", async () => {
    const appRouter = router(); await navigate(appRouter);
    const members = { list: vi.fn().mockResolvedValue({ items: [customerRow], next_cursor: "cursor.signature", has_more: true }) };
    const submitter = { submitReview: vi.fn() };
    const view = mount(ProjectPlanVersionSubmitReviewView, { props: { session: await session(),
      reader: { detail: vi.fn().mockResolvedValue(row) } as unknown as PlanVersionReadClient,
      members: members as unknown as ProjectMemberReadClient, submitter: submitter as unknown as PlanVersionWriteClient }, global: { plugins: [appRouter] } });
    await flushPromises(); await view.get("button").trigger("click"); await flushPromises();
    expect(members.list).toHaveBeenCalledTimes(2); expect(view.text()).toContain("成员分页未能完整读取");
    expect(view.text()).not.toContain("客户成员甲"); expect(submitter.submitReview).not.toHaveBeenCalled(); view.unmount();
  });
});
