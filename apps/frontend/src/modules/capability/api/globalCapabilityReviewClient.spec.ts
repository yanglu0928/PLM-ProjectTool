import { describe, expect, it, vi } from "vitest";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { GlobalCapabilityReviewClient, GlobalReviewError,
  type GlobalCapabilityReview } from "./globalCapabilityReviewClient";

const baseline = "01234567-89ab-4cde-8123-456789abcdef";
const version = "11234567-89ab-4cde-8123-456789abcdef";
const review = "21234567-89ab-4cde-8123-456789abcdef";
const round = "31234567-89ab-4cde-8123-456789abcdef";
const actor = "41234567-89ab-4cde-8123-456789abcdef";
const other = "51234567-89ab-4cde-8123-456789abcdef";
const trace = "61234567-89ab-4cde-8123-456789abcdef";
const decisionId = "71234567-89ab-4cde-8123-456789abcdef";
const at = "2026-10-24T04:00:00Z";
const detail = { review_id: review, subject_type: "CAP-01", baseline_id: baseline,
  baseline_version_id: version, policy_ref: "DEPLOYMENT_ALL_V1", review_round_id: round,
  round_no: 1, reviewer_ids: [actor], decisions: [], state: "IN_REVIEW",
  review_etag: '"v1"', round_etag: '"v0"', submitted_by: other, submitted_at: at } as const;
const receipt = { review_id: review, review_round_id: round, baseline_version_id: version,
  actor_id: actor, decision: "APPROVE", decision_id: decisionId, state: "APPROVED",
  review_etag: '"v2"', round_etag: '"v1"', occurred_at: at, event_id: other } as const;
const fixedVersion = { baseline_version_id: version, baseline_id: baseline, version_no: 1,
  state: "IN_REVIEW", source_collection_ref: `sha256:${"a".repeat(64)}`,
  content_fingerprint: "b".repeat(64), declared_item_count: 1,
  declared_document_ref_count: 1, declared_evidence_ref_count: 1,
  supersedes_version_ref: null, review_ref: review, review_round_ref: round, created_at: at } as const;
const fixedItem = { capability_item_id: decisionId, baseline_version_id: version, baseline_id: baseline,
  ordinal: 0, capability_code: "STD-01", domain_name: "PLM", module_name: "Capability",
  feature_name: "Review", name: "Fixed Item", description: "Scope", boundary: "GLOBAL",
  prerequisites: [], interface_refs: [], state: "AVAILABLE", document_version_refs: [other],
  evidence_refs: [actor] } as const;
function response(data: unknown, status = 200, etag: string | null = null): Response {
  return new Response(JSON.stringify(status === 200 ? { data, trace_id: trace }
    : { error: { code: data, message: "safe" }, trace_id: trace }), {
    status, headers: { "Content-Type": "application/json", "Cache-Control": "no-store",
      "X-Trace-Id": trace, ...(etag === null ? {} : { ETag: etag }) },
  });
}
async function setup(write: Response = response(receipt, 200, '"v2"')) {
  const login = response({ user: { user_id: actor, username_display: "内部评审人" },
    deployment_role: "NONE", password_change_required: false, authorized_projects: [],
    absolute_expires_at: "2030-01-01T12:00:00Z", idle_expires_at: "2030-01-01T11:00:00Z",
    csrf_token: "a".repeat(64) });
  const transport = vi.fn().mockResolvedValueOnce(login).mockResolvedValueOnce(write);
  const session = new SessionClient(transport as typeof fetch);
  await session.login("reviewer", "synthetic-only");
  return { session, transport };
}

describe("GlobalCapabilityReviewClient", () => {
  it("reads exact CAP-01 binding and sends assigned ordinary reviewer decision", async () => {
    const { session, transport } = await setup();
    const reader = vi.fn().mockResolvedValue(response(detail, 200, '"v1"'));
    const client = new GlobalCapabilityReviewClient(session, reader as typeof fetch);
    const current = await client.read(review, baseline, version);
    expect(current).toEqual(detail);
    expect(reader.mock.calls[0][0]).toBe(`/api/v1/global/reviews/${review}`);
    await expect(client.decide(current, "APPROVE", null, "global-review-decision-0001"))
      .resolves.toEqual(receipt);
    expect(transport.mock.calls[1]).toEqual([
      `/api/v1/global/reviews/${review}/rounds/${round}:decide`,
      expect.objectContaining({ method: "POST", credentials: "same-origin", cache: "no-store",
        redirect: "error", body: JSON.stringify({ decision: "APPROVE", comment: null }),
        headers: expect.objectContaining({ "X-CSRF-Token": "a".repeat(64),
          "Idempotency-Key": "global-review-decision-0001" }) }),
    ]);
  });
  it("rejects crossed version, unassigned actor, blank return and malformed projection", async () => {
    const { session, transport } = await setup();
    const reader = (value: unknown) => new GlobalCapabilityReviewClient(session,
      vi.fn().mockResolvedValue(response(value, 200, '"v1"')) as typeof fetch);
    await expect(reader(detail).read(review, baseline, other)).rejects.toBeInstanceOf(GlobalReviewError);
    const current = await reader(detail).read(review, baseline, version);
    await expect(reader({ ...detail, policy_ref: "OTHER" }).read(review, baseline, version))
      .rejects.toMatchObject({ code: "CAP_GLOBAL_REVIEW_UNCERTAIN" });
    await expect(reader({ ...detail, reviewer_ids: [actor, actor] }).read(review, baseline, version))
      .rejects.toBeInstanceOf(GlobalReviewError);
    await expect(reader({ ...detail, state: "APPROVED" }).read(review, baseline, version))
      .rejects.toBeInstanceOf(GlobalReviewError);
    await expect(reader({ ...detail, decisions: [{ decision_id: decisionId, reviewer_id: other,
      decision: "APPROVE", comment: null, decided_at: at }] }).read(review, baseline, version))
      .rejects.toBeInstanceOf(GlobalReviewError);
    await expect(client(session).decide({ ...current, reviewer_ids: [other] } as GlobalCapabilityReview,
      "APPROVE", null, "global-review-decision-0001"))
      .rejects.toMatchObject({ code: "CAP_GLOBAL_REVIEW_INVALID" });
    await expect(client(session).decide(current, "RETURN", "  ", "global-review-decision-0001"))
      .rejects.toMatchObject({ code: "CAP_GLOBAL_REVIEW_INVALID" });
    expect(transport).toHaveBeenCalledTimes(1);
  });
  it("maps confirmed denial and preserves uncertain write result", async () => {
    const { session } = await setup(response("SYSTEM_UNAVAILABLE", 503));
    const denied = new GlobalCapabilityReviewClient(session,
      vi.fn().mockResolvedValue(response("RESOURCE_NOT_FOUND", 404)) as typeof fetch);
    await expect(denied.read(review, baseline, version)).rejects.toMatchObject({
      code: "RESOURCE_NOT_FOUND", uncertain: false,
    });
    const current = await new GlobalCapabilityReviewClient(session,
      vi.fn().mockResolvedValue(response(detail, 200, '"v1"')) as typeof fetch)
      .read(review, baseline, version);
    await expect(client(session).decide(current, "APPROVE", null, "global-review-decision-0001"))
      .rejects.toMatchObject({ code: "SYSTEM_UNAVAILABLE", uncertain: true });
  });
  it("replays a preserved original key after a terminal result only when explicitly requested", async () => {
    const { session, transport } = await setup();
    const client = new GlobalCapabilityReviewClient(session);
    const terminal = { ...detail, state: "APPROVED", decisions: [{ decision_id: decisionId,
      reviewer_id: actor, decision: "APPROVE", comment: null, decided_at: at }] } as unknown as GlobalCapabilityReview;
    await expect(client.decide(terminal, "APPROVE", null, "global-review-decision-0001"))
      .rejects.toMatchObject({ code: "CAP_GLOBAL_REVIEW_INVALID" });
    await expect(client.decide(terminal, "APPROVE", null,
      "global-review-decision-0001", true)).resolves.toEqual(receipt);
    expect(transport).toHaveBeenCalledTimes(2);
  });
  it("reads bound fixed version and item page, rejecting crossed content", async () => {
    const { session } = await setup();
    const read = vi.fn().mockResolvedValueOnce(response({ review_id: review, review_round_id: round,
      version: fixedVersion, review_etag: '"v1"' }, 200, '"v1"'))
      .mockResolvedValueOnce(response({ review_id: review, review_round_id: round,
        baseline_version_id: version, items: [fixedItem], next_cursor: null,
        has_more: false, review_etag: '"v1"' }, 200, '"v1"'));
    const client = new GlobalCapabilityReviewClient(session, read as typeof fetch);
    const bound = await client.fixedVersion(detail as unknown as GlobalCapabilityReview);
    expect(bound).toEqual(fixedVersion);
    const page = await client.fixedItems(detail as unknown as GlobalCapabilityReview, bound);
    expect(page.items).toEqual([fixedItem]);
    expect(read.mock.calls[1][0]).toBe(`/api/v1/global/reviews/${review}/fixed-items?page_size=50`);
    const bad = new GlobalCapabilityReviewClient(session, vi.fn().mockResolvedValue(
      response({ review_id: review, review_round_id: round,
        version: { ...fixedVersion, review_ref: other }, review_etag: '"v1"' }, 200, '"v1"')) as typeof fetch);
    await expect(bad.fixedVersion(detail as unknown as GlobalCapabilityReview))
      .rejects.toMatchObject({ code: "CAP_GLOBAL_REVIEW_UNCERTAIN" });
    const badPage = new GlobalCapabilityReviewClient(session, vi.fn().mockResolvedValue(
      response({ review_id: review, review_round_id: round,
        baseline_version_id: version, items: [{ ...fixedItem, baseline_id: other }],
        next_cursor: null, has_more: false, review_etag: '"v1"' }, 200, '"v1"')) as typeof fetch);
    await expect(badPage.fixedItems(detail as unknown as GlobalCapabilityReview, fixedVersion))
      .rejects.toMatchObject({ code: "CAP_GLOBAL_REVIEW_UNCERTAIN" });
  });
});
function client(session: SessionClient): GlobalCapabilityReviewClient {
  return new GlobalCapabilityReviewClient(session);
}
