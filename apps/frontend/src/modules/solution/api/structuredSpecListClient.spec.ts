import { afterEach, describe, expect, it, vi } from "vitest";
import { StructuredSpecListClient, StructuredSpecListError,
  parseStructuredSpecPage } from "./structuredSpecListClient";

const project = "01234567-89ab-4cde-8123-456789abcdef";
const newest = "71234567-89ab-7cde-8123-456789abcdef";
const older = "61234567-89ab-7cde-8123-456789abcdef";
const series = "11234567-89ab-4cde-8123-456789abcdef";
const actor = "21234567-89ab-4cde-8123-456789abcdef";
const trace = "31234567-89ab-4cde-8123-456789abcdef";
const next = `${"a".repeat(100)}.${"b".repeat(43)}`;
const item = { structured_solution_spec_id: newest, spec_series_id: series,
  project_id: project, spec_type: "MIGRATION_SPEC", version_no: 2,
  version_state: "DRAFT", content_fingerprint: "a".repeat(64),
  payload_fingerprint: "b".repeat(64), supersedes_version_ref: older,
  review_ref: null, review_round_ref: null, created_by: actor,
  created_at: "2026-10-16T00:00:00Z" };
function response(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(status === 200 ? { data, trace_id: trace }
    : { error: { code: data, message: "synthetic" }, trace_id: trace }), { status,
    headers: { "Content-Type": "application/json", "Cache-Control": "no-store",
      "X-Trace-Id": trace } });
}

describe("StructuredSpec list client", () => {
  afterEach(() => vi.restoreAllMocks());

  it("reads strict minimal summaries with a bound next page", async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(response({ items: [item],
      next_cursor: next, has_more: true })).mockResolvedValueOnce(response({ items: [{ ...item,
      structured_solution_spec_id: older, version_no: 1, supersedes_version_ref: null }],
      next_cursor: null, has_more: false }));
    const client = new StructuredSpecListClient(fetcher as typeof fetch);
    const first = await client.list(project, 1);
    expect(first.items[0]).toEqual(item);
    expect("payload" in first.items[0]!).toBe(false);
    const second = await client.list(project, 1, first.next_cursor);
    expect(second.items[0]?.structured_solution_spec_id).toBe(older);
    expect(fetcher.mock.calls[0]?.[0]).toBe(
      `/api/v1/projects/${project}/structured-solution-specs?page_size=1`);
    expect(fetcher.mock.calls[1]?.[0]).toContain(`cursor=${next}`);
    expect(fetcher.mock.calls[0]?.[1]).toMatchObject({ method: "GET",
      credentials: "same-origin", cache: "no-store", redirect: "error" });
  });

  it("fails closed on identity, ordering, state, review and cursor anomalies", () => {
    const invalid = [
      { items: [{ ...item, project_id: series }], next_cursor: null, has_more: false },
      { items: [{ ...item, version_state: "APPROVED", review_ref: series,
        review_round_ref: null }], next_cursor: null, has_more: false },
      { items: [{ ...item, structured_solution_spec_id: older }, item],
        next_cursor: null, has_more: false },
      { items: [item], next_cursor: next, has_more: true },
    ];
    for (const value of invalid) {
      expect(() => parseStructuredSpecPage(value, project, 2,
        value.next_cursor === next ? next : null)).toThrowError(StructuredSpecListError);
    }
  });

  it("maps only safe errors and rejects transport anomalies", async () => {
    await expect(new StructuredSpecListClient(vi.fn().mockResolvedValue(
      response("RESOURCE_NOT_FOUND", 404)) as typeof fetch).list(project))
      .rejects.toMatchObject({ code: "RESOURCE_NOT_FOUND" });
    await expect(new StructuredSpecListClient(vi.fn().mockResolvedValue(
      response("PRIVATE", 500)) as typeof fetch).list(project))
      .rejects.toMatchObject({ code: "STRUCTURED_SPEC_LIST_UNAVAILABLE" });
    const noStore = new Response(JSON.stringify({ data: { items: [], next_cursor: null,
      has_more: false }, trace_id: trace }), { headers: { "Content-Type": "application/json",
      "X-Trace-Id": trace } });
    await expect(new StructuredSpecListClient(vi.fn().mockResolvedValue(noStore) as typeof fetch)
      .list(project)).rejects.toMatchObject({ code: "STRUCTURED_SPEC_LIST_UNAVAILABLE" });
  });

  it("rejects invalid route inputs before network access", async () => {
    const fetcher = vi.fn(); const client = new StructuredSpecListClient(fetcher as typeof fetch);
    await expect(client.list("bad")).rejects.toMatchObject({ code: "STRUCTURED_SPEC_LIST_INVALID" });
    await expect(client.list(project, 0)).rejects.toBeInstanceOf(StructuredSpecListError);
    await expect(client.list(project, 50, "bad")).rejects.toBeInstanceOf(StructuredSpecListError);
    expect(fetcher).not.toHaveBeenCalled();
  });
});
