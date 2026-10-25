import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, describe, expect, it, vi } from "vitest";
import { createMemoryHistory } from "vue-router";
import { createAppRouter } from "@/app/router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { AdminUserListClient } from "@/modules/auth/api/adminUserListClient";
import { CapabilityVersionSubmitReviewClient, CapabilityReviewSubmitError } from
  "@/modules/capability/api/capabilityVersionSubmitReviewClient";
import CapabilityVersionSubmitReviewPanel from "./CapabilityVersionSubmitReviewPanel.vue";

const actor = "01234567-89ab-4cde-8123-456789abcdef";
const baselineId = "11234567-89ab-4cde-8123-456789abcdef";
const versionId = "21234567-89ab-4cde-8123-456789abcdef";
const reviewerId = "31234567-89ab-4cde-8123-456789abcdef";
const ordinaryId = "41234567-89ab-4cde-8123-456789abcdef";
const version = { baseline_id: baselineId, baseline_version_id: versionId, version_no: 1,
  state: "DRAFT" as const, source_collection_ref: `sha256:${"a".repeat(64)}`,
  content_fingerprint: "b".repeat(64), declared_item_count: 1, declared_document_ref_count: 1,
  declared_evidence_ref_count: 1, supersedes_version_ref: null, review_ref: null,
  review_round_ref: null, created_at: "2026-10-24T01:00:00Z" };
const receipt = { review_id: "51234567-89ab-4cde-8123-456789abcdef",
  review_round_id: "61234567-89ab-4cde-8123-456789abcdef", subject_type: "CAP-01" as const,
  baseline_id: baselineId, baseline_version_id: versionId, policy_ref: "DEPLOYMENT_ALL_V1" as const,
  reviewer_ids: [reviewerId], state: "IN_REVIEW" as const, round_no: 1 as const,
  review_etag: '"v1"' as const, submitted_by: actor, submitted_at: "2026-10-24T01:01:00Z" };
async function setup(admin = true) {
  const session = new SessionClient(vi.fn().mockResolvedValue(new Response(JSON.stringify({
    data: { user: { user_id: actor, username_display: "合成用户" },
      deployment_role: admin ? "DEPLOYMENT_ADMIN" : "NONE", password_change_required: false,
      authorized_projects: admin ? [] : [{ project_id: baselineId, name: "合成项目", role: "PROJECT_MANAGER" }],
      absolute_expires_at: "2030-01-01T12:00:00Z", idle_expires_at: "2030-01-01T11:00:00Z",
      csrf_token: "a".repeat(64) }, trace_id: actor }),
    { status: 200, headers: { "Content-Type": "application/json" } })) as typeof fetch);
  await session.login("synthetic", "synthetic-only");
  const users = new AdminUserListClient(vi.fn() as typeof fetch);
  const page = vi.spyOn(users, "page").mockResolvedValue({ items: [
    { user_id: reviewerId, username_display: "合格管理员", account_state: "ENABLED", deployment_role: "DEPLOYMENT_ADMIN" },
    { user_id: ordinaryId, username_display: "普通用户", account_state: "ENABLED", deployment_role: "NONE" },
  ], next_cursor: null, has_more: false });
  const submitter = new CapabilityVersionSubmitReviewClient(session);
  const submit = vi.spyOn(submitter, "submit").mockResolvedValue(receipt);
  const router = createAppRouter(createMemoryHistory());
  await router.push(`/capability-baselines/${baselineId}`); await router.isReady();
  const wrapper = mount(CapabilityVersionSubmitReviewPanel, { props: {
    version, session, users, submitter }, global: { plugins: [router] } });
  await flushPromises();
  return { wrapper, page, submit };
}
describe("CapabilityVersionSubmitReviewPanel", () => {
  afterEach(() => { vi.restoreAllMocks(); window.sessionStorage.clear(); });
  it("shows enabled reviewers and records IN_REVIEW, not approval", async () => {
    const { wrapper, submit } = await setup();
    expect(wrapper.text()).toContain("合格管理员");
    expect(wrapper.text()).toContain("普通用户");
    await wrapper.find('input[value="'+ordinaryId+'"]').setValue(true);
    await wrapper.findAll('input[type="checkbox"]').at(-1)!.setValue(true);
    await wrapper.findAll("button").at(-1)!.trigger("click"); await flushPromises();
    expect(submit).toHaveBeenCalledOnce();
    expect(submit.mock.calls[0]![1]).toEqual([ordinaryId]);
    expect(wrapper.text()).toContain("已进入评审");
    expect(wrapper.text()).toContain("尚未批准");
    expect(wrapper.get("a").attributes("href")).toBe(
      `/capability-baselines/${baselineId}/versions/${versionId}/reviews/${receipt.review_id}`);
    expect(window.sessionStorage.length).toBe(0);
    wrapper.unmount();
  });
  it("retries an uncertain send with the original reviewer set and operation key", async () => {
    const { wrapper, submit } = await setup();
    submit.mockRejectedValueOnce(new CapabilityReviewSubmitError("CAP_REVIEW_UNCERTAIN"));
    await wrapper.find('input[value="'+reviewerId+'"]').setValue(true);
    await wrapper.findAll('input[type="checkbox"]').at(-1)!.setValue(true);
    await wrapper.findAll("button").at(-1)!.trigger("click"); await flushPromises();
    const original = submit.mock.calls[0]![2];
    expect(window.sessionStorage.length).toBe(1);
    expect(wrapper.text()).toContain("原送审结果未确认");
    await wrapper.get('input[type="checkbox"]').setValue(true);
    await wrapper.get("button").trigger("click"); await flushPromises();
    expect(submit.mock.calls[1]![1]).toEqual([reviewerId]);
    expect(submit.mock.calls[1]![2]).toBe(original);
    expect(window.sessionStorage.length).toBe(0);
    wrapper.unmount();
  });
  it("does not read reviewers or offer submission to an ordinary user", async () => {
    const { wrapper, page, submit } = await setup(false);
    expect(wrapper.find("button").exists()).toBe(false);
    expect(page).not.toHaveBeenCalled();
    expect(submit).not.toHaveBeenCalled();
    wrapper.unmount();
  });
});
