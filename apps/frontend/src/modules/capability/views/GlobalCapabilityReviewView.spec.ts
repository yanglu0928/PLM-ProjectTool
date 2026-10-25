import { flushPromises, mount } from "@vue/test-utils";
import { createMemoryHistory } from "vue-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import { createAppRouter } from "@/app/router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { GlobalCapabilityReviewClient, GlobalReviewError } from
  "@/modules/capability/api/globalCapabilityReviewClient";
import GlobalCapabilityReviewView from "./GlobalCapabilityReviewView.vue";

const actor = "01234567-89ab-4cde-8123-456789abcdef";
const baseline = "11234567-89ab-4cde-8123-456789abcdef";
const versionId = "21234567-89ab-4cde-8123-456789abcdef";
const reviewId = "31234567-89ab-4cde-8123-456789abcdef";
const round = "41234567-89ab-4cde-8123-456789abcdef";
const other = "51234567-89ab-4cde-8123-456789abcdef";
const trace = "61234567-89ab-4cde-8123-456789abcdef";
const at = "2026-10-24T01:00:00Z";
const metadata = { review_id: reviewId, subject_type: "CAP-01" as const,
  baseline_id: baseline, baseline_version_id: versionId, policy_ref: "DEPLOYMENT_ALL_V1" as const,
  review_round_id: round, round_no: 1 as const, reviewer_ids: [actor], decisions: [],
  state: "IN_REVIEW" as const, review_etag: '"v1"', round_etag: '"v0"',
  submitted_by: other, submitted_at: at };
const fixed = { baseline_version_id: versionId, baseline_id: baseline, version_no: 1,
  state: "IN_REVIEW" as const, source_collection_ref: `sha256:${"a".repeat(64)}`,
  content_fingerprint: "b".repeat(64), declared_item_count: 1,
  declared_document_ref_count: 1, declared_evidence_ref_count: 1,
  supersedes_version_ref: null, review_ref: reviewId, review_round_ref: round, created_at: at };
const item = { capability_item_id: trace, baseline_version_id: versionId, baseline_id: baseline,
  ordinal: 0, capability_code: "STD-01", domain_name: "PLM", module_name: "Capability",
  feature_name: "Review", name: "固定能力", description: "必须核对内容", boundary: "GLOBAL",
  prerequisites: [], interface_refs: [], state: "AVAILABLE" as const,
  document_version_refs: [other], evidence_refs: [actor] };
const receipt = { review_id: reviewId, review_round_id: round, baseline_version_id: versionId,
  actor_id: actor, decision: "APPROVE" as const, decision_id: other, state: "APPROVED" as const,
  review_etag: '"v2"', round_etag: '"v1"', occurred_at: at, event_id: trace };
async function setup(assigned = true) {
  const login = new Response(JSON.stringify({ data: {
    user: { user_id: actor, username_display: "普通受分配评审人" }, deployment_role: "NONE",
    password_change_required: false, authorized_projects: [],
    absolute_expires_at: "2030-01-01T12:00:00Z", idle_expires_at: "2030-01-01T11:00:00Z",
    csrf_token: "a".repeat(64) }, trace_id: trace }),
  { status: 200, headers: { "Content-Type": "application/json" } });
  const session = new SessionClient(vi.fn().mockResolvedValue(login) as typeof fetch);
  await session.login("reviewer", "synthetic-only");
  const reviews = new GlobalCapabilityReviewClient(session);
  const read = vi.spyOn(reviews, "read").mockResolvedValue({ ...metadata,
    reviewer_ids: assigned ? [actor] : [other] });
  const fixedVersion = vi.spyOn(reviews, "fixedVersion").mockResolvedValue(fixed);
  const fixedItems = vi.spyOn(reviews, "fixedItems").mockResolvedValue({ items: [item],
    next_cursor: null, has_more: false });
  const decide = vi.spyOn(reviews, "decide").mockResolvedValue(receipt);
  const router = createAppRouter(createMemoryHistory());
  await router.push(`/capability-baselines/${baseline}/versions/${versionId}/reviews/${reviewId}`);
  await router.isReady();
  const wrapper = mount(GlobalCapabilityReviewView, {
    props: { session, reviews }, global: { plugins: [router] },
  });
  await flushPromises();
  return { wrapper, read, fixedVersion, fixedItems, decide };
}
describe("GlobalCapabilityReviewView", () => {
  afterEach(() => { vi.restoreAllMocks(); window.sessionStorage.clear(); });
  it("shows all fixed content before enabling the assigned ordinary reviewer decision", async () => {
    const { wrapper, read, fixedVersion, decide } = await setup();
    expect(read).toHaveBeenCalledWith(reviewId, baseline, versionId);
    expect(wrapper.text()).toContain("固定能力");
    expect(wrapper.text()).toContain(other);
    const approve = wrapper.findAll("button").find(button => button.text() === "批准本轮版本")!;
    expect(approve.attributes("disabled")).toBeDefined();
    await wrapper.get('input[type="checkbox"]').setValue(true);
    expect(approve.attributes("disabled")).toBeUndefined();
    read.mockResolvedValue({ ...metadata, review_etag: '"v2"', state: "APPROVED",
      decisions: [{ reviewer_id: actor, decision: "APPROVE", comment: null,
        decided_at: at, decision_id: other }] });
    fixedVersion.mockResolvedValue({ ...fixed, state: "APPROVED" });
    await approve.trigger("click"); await flushPromises();
    expect(decide).toHaveBeenCalledWith(expect.objectContaining({ review_id: reviewId }),
      "APPROVE", null, expect.stringMatching(/^cap-global-review-decision-/), false);
    expect(window.sessionStorage.length).toBe(0);
    expect(wrapper.text()).toContain("你已完成本轮决定");
    expect(wrapper.text()).not.toContain("回执与当前评审不一致");
    wrapper.unmount();
  });
  it("does not offer a decision to an unassigned reviewer", async () => {
    const { wrapper, decide } = await setup(false);
    expect(wrapper.text()).toContain("你不是本轮评审人");
    expect(wrapper.text()).not.toContain("批准本轮版本");
    expect(decide).not.toHaveBeenCalled(); wrapper.unmount();
  });
  it("retains the original operation key after an uncertain result", async () => {
    const { wrapper, read, fixedVersion, decide } = await setup();
    decide.mockRejectedValueOnce(new GlobalReviewError("CAP_GLOBAL_REVIEW_UNCERTAIN"));
    await wrapper.get('input[type="checkbox"]').setValue(true);
    await wrapper.findAll("button").find(button => button.text() === "批准本轮版本")!.trigger("click");
    await flushPromises();
    expect(window.sessionStorage.length).toBe(1);
    const key = decide.mock.calls[0]![3];
    expect(wrapper.text()).toContain("原决定操作号");
    read.mockResolvedValue({ ...metadata, review_etag: '"v2"', state: "APPROVED",
      decisions: [{ reviewer_id: actor, decision: "APPROVE", comment: null,
        decided_at: at, decision_id: other }] });
    fixedVersion.mockResolvedValue({ ...fixed, state: "APPROVED" });
    await wrapper.findAll("button").find(button => button.text() === "刷新固定内容与评审状态")!.trigger("click");
    await flushPromises();
    await wrapper.get('input[type="checkbox"]').setValue(true);
    await wrapper.findAll("button").find(button => button.text() === "按原操作号重试")!.trigger("click");
    await flushPromises();
    expect(decide.mock.calls[1]![3]).toBe(key);
    expect(decide.mock.calls[1]![4]).toBe(true);
    expect(window.sessionStorage.length).toBe(0);
    wrapper.unmount();
  });
  it("fails closed when the fixed item list is incomplete", async () => {
    const { wrapper, fixedItems, decide } = await setup();
    fixedItems.mockResolvedValue({ items: [], next_cursor: null, has_more: false });
    await wrapper.findAll("button").find(button => button.text() === "刷新固定内容与评审状态")!.trigger("click");
    await flushPromises();
    expect(wrapper.text()).toContain("固定评审内容未能完整核对");
    expect(wrapper.text()).not.toContain("批准本轮版本");
    expect(decide).not.toHaveBeenCalled(); wrapper.unmount();
  });
});
