import { afterEach, describe, expect, it, vi } from "vitest";
import { ProjectReviewListClient, ReviewListError, parseReviewListPage } from "./projectReviewListClient";

const project = "01234567-89ab-4cde-8123-456789abcdef";
const other = "11234567-89ab-4cde-8123-456789abcdef";
const review = "21234567-89ab-4cde-8123-456789abcdef";
const round = "31234567-89ab-4cde-8123-456789abcdef";
const assignment = "41234567-89ab-4cde-8123-456789abcdef";
const actor = "51234567-89ab-4cde-8123-456789abcdef";
const trace = "61234567-89ab-4cde-8123-456789abcdef";
const cursor = `r1.${"a".repeat(60)}`;
const pending = { review_id: review, project_id: project,
  subject_ref: { resource_type: "SOL-06", resource_id: other },
  policy_code: "STRUCTURED_SPEC_ALL_V1", state: "IN_REVIEW", created_by: actor,
  created_at: "2026-10-19T04:00:00Z", etag: '"v1"', active_round: {
    review_round_id: round, round_no: 1, subject_version_ref: other,
    started_at: "2026-10-19T04:01:00Z", my_assignment: {
      assignment_id: assignment, state: "PENDING", decision: null, decided_at: null,
    },
  },
};
function response(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(status === 200 ? { data, trace_id: trace }
    : { error: { code: data, message: "synthetic" }, trace_id: trace }), { status,
    headers: { "Content-Type": "application/json", "Cache-Control": "no-store",
      "X-Trace-Id": trace, "X-Content-Type-Options": "nosniff" } });
}

describe("ProjectReviewListClient", () => {
  afterEach(() => vi.restoreAllMocks());

  it("uses frozen query and accepts a hidden empty page with encrypted continuation", async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(response({ items: [], next_cursor: cursor,
      has_more: true })).mockResolvedValueOnce(response({ items: [pending], next_cursor: null,
      has_more: false }));
    const client = new ProjectReviewListClient(fetcher as typeof fetch);
    const first = await client.list(project, "my_pending", 1);
    expect(first.items).toEqual([]);
    const second = await client.list(project, "my_pending", 1, first.next_cursor);
    expect(second.items[0]?.active_round?.my_assignment?.state).toBe("PENDING");
    expect(fetcher.mock.calls[0]?.[0]).toBe(`/api/v1/projects/${project}/reviews?view=my_pending&page_size=1`);
    expect(fetcher.mock.calls[1]?.[0]).toContain(`cursor=${cursor}`);
    expect(fetcher.mock.calls[0]?.[1]).toMatchObject({ method: "GET", credentials: "same-origin",
      cache: "no-store", redirect: "error" });
  });

  it("accepts terminal history but rejects it as pending and excludes other actor details", () => {
    const terminal = { ...pending, state: "APPROVED", etag: '"v2"', active_round: null };
    expect(parseReviewListPage({ items: [terminal], next_cursor: null, has_more: false },
      project, "all", 50, null).items[0]?.active_round).toBeNull();
    expect(() => parseReviewListPage({ items: [terminal], next_cursor: null, has_more: false },
      project, "my_pending", 50, null)).toThrowError(ReviewListError);
    for (const changed of [
      { ...pending, project_id: other },
      { ...pending, active_round: { ...pending.active_round, assignments: [] } },
      { ...pending, active_round: { ...pending.active_round, my_assignment: {
        ...pending.active_round.my_assignment, state: "DECIDED" } } },
    ]) expect(() => parseReviewListPage({ items: [changed], next_cursor: null,
      has_more: false }, project, "my_pending", 50, null)).toThrowError(ReviewListError);
  });

  it("fails closed on cursor loops, duplicate rows, bad transport and safe errors", async () => {
    expect(() => parseReviewListPage({ items: [pending, pending], next_cursor: null,
      has_more: false }, project, "all", 50, null)).toThrowError(ReviewListError);
    expect(() => parseReviewListPage({ items: [], next_cursor: cursor,
      has_more: true }, project, "all", 50, cursor)).toThrowError(ReviewListError);
    await expect(new ProjectReviewListClient(vi.fn().mockResolvedValue(response(
      "RESOURCE_NOT_FOUND", 404)) as typeof fetch).list(project)).rejects.toMatchObject({ code: "RESOURCE_NOT_FOUND" });
    await expect(new ProjectReviewListClient(vi.fn().mockResolvedValue(response(
      "PRIVATE", 503)) as typeof fetch).list(project)).rejects.toMatchObject({ code: "REVIEW_LIST_UNAVAILABLE" });
    const missingNoStore = new Response(JSON.stringify({ data: { items: [], next_cursor: null,
      has_more: false }, trace_id: trace }), { status: 200,
      headers: { "Content-Type": "application/json", "X-Trace-Id": trace } });
    await expect(new ProjectReviewListClient(vi.fn().mockResolvedValue(missingNoStore) as typeof fetch)
      .list(project)).rejects.toMatchObject({ code: "REVIEW_LIST_UNAVAILABLE" });
  });

  it("rejects invalid inputs before sending any request", async () => {
    const fetcher = vi.fn(); const client = new ProjectReviewListClient(fetcher as typeof fetch);
    for (const call of [() => client.list("bad"), () => client.list(project, "all", 201),
      () => client.list(project, "my_pending", 50, "bad")]) {
      await expect(call()).rejects.toMatchObject({ code: "REVIEW_LIST_INVALID" });
    }
    expect(fetcher).not.toHaveBeenCalled();
  });
});
