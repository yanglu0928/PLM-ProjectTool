import { afterEach, describe, expect, it, vi } from "vitest";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { CapabilityVersionSubmitReviewClient } from "./capabilityVersionSubmitReviewClient";

const actor = "01234567-89ab-4cde-8123-456789abcdef";
const baselineId = "11234567-89ab-4cde-8123-456789abcdef";
const versionId = "21234567-89ab-4cde-8123-456789abcdef";
const reviewerId = "31234567-89ab-4cde-8123-456789abcdef";
const reviewId = "41234567-89ab-4cde-8123-456789abcdef";
const roundId = "51234567-89ab-4cde-8123-456789abcdef";
const version = { baseline_id: baselineId, baseline_version_id: versionId, version_no: 1,
  state: "DRAFT" as const, source_collection_ref: `sha256:${"a".repeat(64)}`,
  content_fingerprint: "b".repeat(64), declared_item_count: 1, declared_document_ref_count: 1,
  declared_evidence_ref_count: 1, supersedes_version_ref: null, review_ref: null,
  review_round_ref: null, created_at: "2026-10-24T01:00:00Z" };
const submitted = { review_id: reviewId, review_round_id: roundId, subject_type: "CAP-01",
  baseline_id: baselineId, baseline_version_id: versionId, policy_ref: "DEPLOYMENT_ALL_V1",
  reviewer_ids: [reviewerId], state: "IN_REVIEW", round_no: 1, review_etag: '"v1"',
  submitted_by: actor, submitted_at: "2026-10-24T01:01:00Z" };
function json(data: unknown, status = 201, extra: Record<string, string> = {}): Response {
  return new Response(JSON.stringify({ data, trace_id: actor }), { status, headers: {
    "Content-Type": "application/json", "Cache-Control": "no-store", "X-Trace-Id": actor,
    ETag: '"v1"', ...extra } });
}
function auth(admin: boolean): Response { return json({ user: { user_id: actor, username_display: "合成用户" },
  deployment_role: admin ? "DEPLOYMENT_ADMIN" : "NONE", password_change_required: false,
  authorized_projects: admin ? [] : [{ project_id: baselineId, name: "合成项目", role: "PROJECT_MANAGER" }],
  absolute_expires_at: "2030-01-01T12:00:00Z", idle_expires_at: "2030-01-01T11:00:00Z",
  csrf_token: "a".repeat(64) }, 200); }
function harness(admin: boolean, ...results: Response[]) {
  const fetcher = vi.fn(); [auth(admin), ...results].forEach(result => fetcher.mockResolvedValueOnce(result));
  const session = new SessionClient(fetcher as typeof fetch);
  return { session, client: new CapabilityVersionSubmitReviewClient(session), fetcher };
}
describe("CapabilityVersionSubmitReviewClient", () => {
  afterEach(() => { vi.restoreAllMocks(); });
  it("submits exact frozen body and verifies an IN_REVIEW receipt, never approval", async () => {
    const { session, client, fetcher } = harness(true, json(submitted));
    await session.login("synthetic", "synthetic-only");
    await expect(client.submit(version, [reviewerId], "synthetic-cap-review-001"))
      .resolves.toMatchObject({ state: "IN_REVIEW", review_id: reviewId });
    expect(fetcher.mock.calls[1][0]).toBe(
      `/api/v1/global/capability-baselines/${baselineId}/versions/${versionId}:submit-review`);
    expect(JSON.parse(fetcher.mock.calls[1][1].body)).toEqual({ reviewer_ids: [reviewerId],
      policy_ref: "DEPLOYMENT_ALL_V1", due_at: null, submission_note: null });
    expect(fetcher.mock.calls[1][1].headers).toMatchObject({
      "X-CSRF-Token": "a".repeat(64), "Idempotency-Key": "synthetic-cap-review-001" });
  });
  it("blocks ordinary users, non-DRAFT versions and duplicate reviewers before POST", async () => {
    const ordinary = harness(false); await ordinary.session.login("synthetic", "synthetic-only");
    await expect(ordinary.client.submit(version, [reviewerId], "synthetic-cap-review-002"))
      .rejects.toMatchObject({ code: "CAP_REVIEW_INVALID" });
    const admin = harness(true); await admin.session.login("synthetic", "synthetic-only");
    await expect(admin.client.submit({ ...version, state: "IN_REVIEW" }, [reviewerId],
      "synthetic-cap-review-003")).rejects.toMatchObject({ code: "CAP_REVIEW_INVALID" });
    await expect(admin.client.submit(version, [reviewerId, reviewerId],
      "synthetic-cap-review-004")).rejects.toMatchObject({ code: "CAP_REVIEW_INVALID" });
    expect(admin.fetcher).toHaveBeenCalledTimes(1);
  });
  it("rejects a mismatched reviewer receipt and an invented approval", async () => {
    const mismatch = harness(true, json({ ...submitted, reviewer_ids: [actor] }));
    await mismatch.session.login("synthetic", "synthetic-only");
    await expect(mismatch.client.submit(version, [reviewerId], "synthetic-cap-review-005"))
      .rejects.toMatchObject({ code: "CAP_REVIEW_UNCERTAIN", uncertain: true });
    const approval = harness(true, json({ ...submitted, state: "APPROVED" }));
    await approval.session.login("synthetic", "synthetic-only");
    await expect(approval.client.submit(version, [reviewerId], "synthetic-cap-review-006"))
      .rejects.toMatchObject({ code: "CAP_REVIEW_UNCERTAIN" });
  });
  it("maps known business refusal and preserves uncertainty for unknown network result", async () => {
    const refused = harness(true, new Response(JSON.stringify({ error: {
      code: "BUSINESS_REVIEW_NOT_ELIGIBLE" }, trace_id: actor }), { status: 422,
      headers: { "Content-Type": "application/json", "Cache-Control": "no-store", "X-Trace-Id": actor } }));
    await refused.session.login("synthetic", "synthetic-only");
    await expect(refused.client.submit(version, [reviewerId], "synthetic-cap-review-007"))
      .rejects.toMatchObject({ code: "BUSINESS_REVIEW_NOT_ELIGIBLE", uncertain: false });
    const lost = harness(true); await lost.session.login("synthetic", "synthetic-only");
    await expect(lost.client.submit(version, [reviewerId], "synthetic-cap-review-008"))
      .rejects.toMatchObject({ code: "CAP_REVIEW_UNCERTAIN", uncertain: true });
  });
});
