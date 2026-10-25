import { afterEach, describe, expect, it, vi } from "vitest";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import type { HandoverAnalysisVersionView } from "./handoverReadClient";
import { HandoverVersionSubmitReviewClient } from "./handoverVersionSubmitReviewClient";

const actor = "01234567-89ab-4cde-8123-456789abcdef";
const project = "11234567-89ab-4cde-8123-456789abcdef";
const analysis = "21234567-89ab-4cde-8123-456789abcdef";
const versionId = "31234567-89ab-4cde-8123-456789abcdef";
const reviewerA = "41234567-89ab-4cde-8123-456789abcdef";
const reviewerB = "51234567-89ab-4cde-8123-456789abcdef";
const reviewId = "61234567-89ab-4cde-8123-456789abcdef";
const roundId = "71234567-89ab-4cde-8123-456789abcdef";
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
const submitted = { review_id: reviewId, review_round_id: roundId, subject_type: "HND-02",
  project_id: project, handover_analysis_id: analysis, handover_analysis_version_id: versionId,
  policy_ref: "HANDOVER_ALL_V1", reviewer_ids: [reviewerA, reviewerB], state: "IN_REVIEW",
  round_no: 1, review_etag: '"v1"', submitted_by: actor, submitted_at: "2026-10-25T01:01:00Z" };
function json(data: unknown, status = 201, extra: Record<string, string> = {}): Response {
  return new Response(JSON.stringify({ data, trace_id: actor }), { status, headers: {
    "Content-Type": "application/json", "Cache-Control": "no-store", "X-Trace-Id": actor,
    ETag: '"v1"', ...extra } });
}
function error(code: string, status: number): Response {
  return new Response(JSON.stringify({ error: { code, message: "synthetic" }, trace_id: actor }), {
    status, headers: { "Content-Type": "application/json", "Cache-Control": "no-store", "X-Trace-Id": actor },
  });
}
function auth(role: "PROJECT_MANAGER" | "IMPLEMENTATION_MEMBER"): Response {
  return json({ user: { user_id: actor, username_display: "合成用户" }, deployment_role: "NONE",
    password_change_required: false, authorized_projects: [{ project_id: project,
      name: "合成项目", role }], absolute_expires_at: "2030-01-01T12:00:00Z",
    idle_expires_at: "2030-01-01T11:00:00Z", csrf_token: "a".repeat(64) }, 200);
}
function harness(role: "PROJECT_MANAGER" | "IMPLEMENTATION_MEMBER", ...results: Response[]) {
  const fetcher = vi.fn(); [auth(role), ...results].forEach(result => fetcher.mockResolvedValueOnce(result));
  const session = new SessionClient(fetcher as typeof fetch);
  return { session, client: new HandoverVersionSubmitReviewClient(session), fetcher };
}
describe("HandoverVersionSubmitReviewClient", () => {
  afterEach(() => { vi.restoreAllMocks(); });
  it("sends exact frozen body and accepts only IN_REVIEW first round", async () => {
    const { session, client, fetcher } = harness("PROJECT_MANAGER", json(submitted));
    await session.login("synthetic", "synthetic-only");
    await expect(client.submit(version, [reviewerB, reviewerA], "synthetic-hnd-review-001"))
      .resolves.toMatchObject({ state: "IN_REVIEW", review_id: reviewId });
    expect(fetcher.mock.calls[1][0]).toBe(
      `/api/v1/projects/${project}/handover-analyses/${analysis}/versions/${versionId}:submit-review`);
    expect(JSON.parse(fetcher.mock.calls[1][1].body)).toEqual({ reviewer_ids: [reviewerA, reviewerB],
      policy_ref: "HANDOVER_ALL_V1", due_at: null, submission_note: null });
    expect(fetcher.mock.calls[1][1].headers).toMatchObject({
      "X-CSRF-Token": "a".repeat(64), "Idempotency-Key": "synthetic-hnd-review-001" });
  });
  it("prevents non-manager, reviewed version and repeated reviewer before network", async () => {
    const member = harness("IMPLEMENTATION_MEMBER"); await member.session.login("synthetic", "synthetic-only");
    await expect(member.client.submit(version, [reviewerA], "synthetic-hnd-review-002"))
      .rejects.toMatchObject({ code: "HND_REVIEW_INVALID" });
    const manager = harness("PROJECT_MANAGER"); await manager.session.login("synthetic", "synthetic-only");
    await expect(manager.client.submit({ ...version, state: "IN_REVIEW" }, [reviewerA],
      "synthetic-hnd-review-003")).rejects.toMatchObject({ code: "HND_REVIEW_INVALID" });
    await expect(manager.client.submit(version, [reviewerA, reviewerA],
      "synthetic-hnd-review-004")).rejects.toMatchObject({ code: "HND_REVIEW_INVALID" });
    expect(manager.fetcher).toHaveBeenCalledTimes(1);
  });
  it("rejects reviewer mismatch and invented approval as uncertain", async () => {
    const mismatch = harness("PROJECT_MANAGER", json({ ...submitted, reviewer_ids: [reviewerA] }));
    await mismatch.session.login("synthetic", "synthetic-only");
    await expect(mismatch.client.submit(version, [reviewerA, reviewerB], "synthetic-hnd-review-005"))
      .rejects.toMatchObject({ code: "HND_REVIEW_UNCERTAIN", uncertain: true });
    const approved = harness("PROJECT_MANAGER", json({ ...submitted, state: "APPROVED" }));
    await approved.session.login("synthetic", "synthetic-only");
    await expect(approved.client.submit(version, [reviewerA, reviewerB], "synthetic-hnd-review-006"))
      .rejects.toMatchObject({ code: "HND_REVIEW_UNCERTAIN" });
  });
  it.each([
    ["AUTH_SESSION_EXPIRED", 401], ["LICENSE_OPERATION_DENIED", 403],
    ["RESOURCE_NOT_FOUND", 404], ["REVIEW_SUBJECT_LOCKED", 409],
    ["REVIEW_REVIEWER_INELIGIBLE", 422], ["SYSTEM_UNAVAILABLE", 503],
  ])("maps frozen refusal %s at its status", async (code, status) => {
    const { session, client } = harness("PROJECT_MANAGER", error(code, status));
    await session.login("synthetic", "synthetic-only");
    await expect(client.submit(version, [reviewerA], "synthetic-hnd-review-refusal"))
      .rejects.toMatchObject({ code, uncertain: code === "SYSTEM_UNAVAILABLE" });
  });
  it("retains uncertainty for a missing network result", async () => {
    const { session, client, fetcher } = harness("PROJECT_MANAGER");
    await session.login("synthetic", "synthetic-only");
    await expect(client.submit(version, [reviewerA], "synthetic-hnd-review-lost"))
      .rejects.toMatchObject({ code: "HND_REVIEW_UNCERTAIN", uncertain: true });
    expect(fetcher.mock.calls[1][1].headers["Idempotency-Key"]).toBe("synthetic-hnd-review-lost");
  });
});
