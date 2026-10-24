import { flushPromises, mount } from "@vue/test-utils";
import { createMemoryHistory } from "vue-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import { createAppRouter } from "@/app/router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { ProjectMemberReadClient } from "@/modules/project/api/projectMemberReadClient";
import type { HandoverAnalysisVersionView } from "@/modules/handover/api/handoverReadClient";
import { HandoverSubmitReviewError, HandoverVersionSubmitReviewClient } from "@/modules/handover/api/handoverVersionSubmitReviewClient";
import HandoverVersionSubmitReviewPanel from "./HandoverVersionSubmitReviewPanel.vue";

const actor = "01234567-89ab-4cde-8123-456789abcdef";
const project = "11234567-89ab-4cde-8123-456789abcdef";
const analysis = "21234567-89ab-4cde-8123-456789abcdef";
const versionId = "31234567-89ab-4cde-8123-456789abcdef";
const customer = "41234567-89ab-4cde-8123-456789abcdef";
const implementation = "51234567-89ab-4cde-8123-456789abcdef";
const review = "61234567-89ab-4cde-8123-456789abcdef";
const round = "71234567-89ab-4cde-8123-456789abcdef";
const version: HandoverAnalysisVersionView = {
  handover_analysis_version_id: versionId, handover_analysis_id: analysis, project_id: project,
  version_no: 1, state: "DRAFT", source_set_ref: `sha256:${"a".repeat(64)}`,
  capability_baseline_id: "81234567-89ab-4cde-8123-456789abcdef",
  capability_baseline_version_ref: "91234567-89ab-4cde-8123-456789abcdef",
  content_fingerprint: "b".repeat(64), declared_source_count: 1, declared_item_count: 2,
  declared_evidence_count: 2, declared_capability_ref_count: 0, declared_ai_task_count: 0,
  supersedes_version_ref: null, review_ref: null, review_round_ref: null,
  created_by: actor, created_at: "2026-10-25T01:00:00Z", source_documents: [], ai_tasks: [],
};
const receipt = { review_id: review, review_round_id: round, subject_type: "HND-02",
  project_id: project, handover_analysis_id: analysis, handover_analysis_version_id: versionId,
  policy_ref: "HANDOVER_ALL_V1", reviewer_ids: [customer], state: "IN_REVIEW", round_no: 1,
  review_etag: '"v1"', submitted_by: actor, submitted_at: "2026-10-25T01:01:00Z" };
const candidates = [
  { member_id: customer, user: { user_id: customer, display_name: "客户甲" },
    role: "CUSTOMER_MEMBER", state: "ACTIVE" },
  { member_id: implementation, user: { user_id: implementation, display_name: "实施乙" },
    role: "IMPLEMENTATION_MEMBER", state: "ACTIVE" },
];
async function session(role: string) {
  const login = new Response(JSON.stringify({ data: {
    user: { user_id: actor, username_display: "合成用户" }, deployment_role: "NONE",
    password_change_required: false, authorized_projects: [{ project_id: project,
      name: "合成项目", role }], absolute_expires_at: "2030-01-01T12:00:00Z",
    idle_expires_at: "2030-01-01T11:00:00Z", csrf_token: "a".repeat(64),
  }, trace_id: project }), { status: 200, headers: { "Content-Type": "application/json" } });
  const client = new SessionClient(vi.fn().mockResolvedValue(login) as typeof fetch);
  await client.login("user", "synthetic-only"); return client;
}
async function panel(role = "PROJECT_MANAGER", outcome = vi.fn().mockResolvedValue(receipt),
  memberList = vi.fn().mockResolvedValue({ items: candidates, next_cursor: null, has_more: false }),
  detail: HandoverAnalysisVersionView = version) {
  const router = createAppRouter(createMemoryHistory());
  await router.push(`/projects/${project}/handover/${analysis}`); await router.isReady();
  const memberClient = { list: memberList }; const submitter = { submit: outcome };
  const wrapper = mount(HandoverVersionSubmitReviewPanel, { props: {
    session: await session(role), version: detail,
    members: memberClient as unknown as ProjectMemberReadClient,
    submitter: submitter as unknown as HandoverVersionSubmitReviewClient,
  }, global: { plugins: [router] } });
  await flushPromises();
  const load = wrapper.findAll("button").find(button => button.text() === "读取当前项目确认人");
  if (load) { await load.trigger("click"); await flushPromises(); }
  return { wrapper, memberClient, submitter };
}
describe("HandoverVersionSubmitReviewPanel", () => {
  afterEach(() => { vi.restoreAllMocks(); sessionStorage.clear(); });
  it("offers only active customer reviewers and links IN_REVIEW without approval claim", async () => {
    const { wrapper, submitter } = await panel();
    expect(wrapper.text()).toContain("客户甲"); expect(wrapper.text()).not.toContain("实施乙");
    await wrapper.get(`input[value="${customer}"]`).setValue(true);
    await wrapper.get('input[type="checkbox"]:not([value])').setValue(true);
    await wrapper.findAll("button").find(button => button.text() === "提交交接版本评审")!.trigger("click");
    await flushPromises();
    expect(submitter.submit).toHaveBeenCalledWith(version, [customer], expect.stringMatching(/^handover-review-/));
    expect(wrapper.get(`a[href="/projects/${project}/reviews/${review}"]`).text()).toContain("打开评审");
    expect(wrapper.text()).toContain("这不是批准"); expect(sessionStorage.length).toBe(0);
    wrapper.unmount();
  });
  it("retains exact reviewer set and key on uncertain result until explicit retry", async () => {
    const outcome = vi.fn().mockRejectedValueOnce(new HandoverSubmitReviewError("HND_REVIEW_UNCERTAIN"))
      .mockResolvedValueOnce(receipt);
    const { wrapper, submitter } = await panel("PROJECT_MANAGER", outcome);
    await wrapper.get(`input[value="${customer}"]`).setValue(true);
    await wrapper.get('input[type="checkbox"]:not([value])').setValue(true);
    await wrapper.findAll("button").find(button => button.text() === "提交交接版本评审")!.trigger("click");
    await flushPromises();
    expect(sessionStorage.length).toBe(1);
    const first = submitter.submit.mock.calls[0];
    await wrapper.get('input[type="checkbox"]:not([value])').setValue(true);
    await wrapper.findAll("button").find(button => button.text() === "按原操作号重试送审")!.trigger("click");
    await flushPromises();
    expect(submitter.submit.mock.calls[1]).toEqual(first);
    expect(sessionStorage.length).toBe(0); wrapper.unmount();
  });
  it("does not load candidates or submit for non-manager or reviewed version", async () => {
    const customerPage = await panel("CUSTOMER_MEMBER");
    expect(customerPage.wrapper.find("button").exists()).toBe(false);
    expect(customerPage.memberClient.list).not.toHaveBeenCalled();
    customerPage.wrapper.unmount();
    const reviewed = await panel("PROJECT_MANAGER", vi.fn(), undefined,
      { ...version, state: "IN_REVIEW", review_ref: review, review_round_ref: round });
    expect(reviewed.wrapper.findAll("button").some(button => button.text() === "提交交接版本评审"))
      .toBe(false); reviewed.wrapper.unmount();
  });
  it("does not offer a false complete reviewer set when pagination is incomplete", async () => {
    const broken = vi.fn().mockResolvedValue({ items: candidates, next_cursor: null, has_more: true });
    const { wrapper, submitter } = await panel("PROJECT_MANAGER", vi.fn(), broken);
    expect(wrapper.text()).toContain("成员翻页无效");
    expect(wrapper.find(`input[value="${customer}"]`).exists()).toBe(false);
    expect(submitter.submit).not.toHaveBeenCalled(); wrapper.unmount();
  });
});
