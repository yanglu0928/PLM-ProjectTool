import { afterEach, describe, expect, it, vi } from "vitest";
import { OutlineVersionReadClient, OutlineVersionReadError } from "./outlineVersionReadClient";

const project = "01234567-89ab-4cde-8123-456789abcdef";
const outline = "11234567-89ab-4cde-8123-456789abcdef";
const version = "21234567-89ab-4cde-8123-456789abcdef";
const other = "31234567-89ab-4cde-8123-456789abcdef";
const section = "41234567-89ab-4cde-8123-456789abcdef";
const trace = "51234567-89ab-4cde-8123-456789abcdef";
const cursor = `${"a".repeat(100)}.${"b".repeat(43)}`;
const item = { solution_outline_version_id: version, solution_outline_id: outline,
  project_id: project, version_no: 2, version_state: "DRAFT", content_fingerprint: "a".repeat(64),
  declared_section_count: 1, declared_requirement_count: 1, declared_reference_count: 1,
  missing_declaration_count: 1, conflict_declaration_count: 0,
  supersedes_version_ref: other, review_ref: null, review_round_ref: null,
  created_by: project, created_at: "2026-10-09T00:00:00Z" };
const detail = { ...item, section_ids: [section],
  requirement_refs: [{ requirement_id: other, requirement_version_id: version }],
  reference_refs: [{ scope: "GLOBAL", reference_solution_id: other, reference_version_id: version }],
  missing_declarations: [{ description: "待补充" }], conflict_declarations: [] };
function response(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(status === 200 ? { data, trace_id: trace }
    : { error: { code: data, message: "synthetic" }, trace_id: trace }), { status,
    headers: { "Content-Type": "application/json", "Cache-Control": "no-store",
      "X-Trace-Id": trace } });
}

describe("OutlineVersion history read client", () => {
  afterEach(() => vi.restoreAllMocks());

  it("reads metadata pages and exact ordered detail without claiming current eligibility", async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(response({ items: [item], next_cursor: cursor,
      has_more: true })).mockResolvedValueOnce(response({ items: [{ ...item,
      solution_outline_version_id: other, version_no: 1, supersedes_version_ref: null }],
      next_cursor: null, has_more: false })).mockResolvedValueOnce(response(detail));
    const client = new OutlineVersionReadClient(fetcher as typeof fetch);
    const first = await client.list(project, outline, 1);
    expect(first.items[0]?.version_no).toBe(2);
    expect("reference_refs" in first.items[0]!).toBe(false);
    expect((await client.list(project, outline, 1, first.next_cursor)).items[0]?.version_no).toBe(1);
    expect((await client.detail(project, outline, version)).reference_refs[0]?.scope).toBe("GLOBAL");
    expect(fetcher.mock.calls[0]?.[0]).toBe(
      `/api/v1/projects/${project}/solution-outlines/${outline}/versions?page_size=1`);
    expect(fetcher.mock.calls[1]?.[0]).toContain(`cursor=${cursor}`);
    expect(fetcher.mock.calls[2]?.[1]).toMatchObject({ method: "GET", credentials: "same-origin",
      cache: "no-store", redirect: "error" });
  });

  it("rejects mismatched identity, count, order and repeated cursor", async () => {
    const invalid = [
      { items: [{ ...item, project_id: other }], next_cursor: null, has_more: false },
      { items: [{ ...item, version_no: 1 }, item], next_cursor: null, has_more: false },
      { items: [item], next_cursor: cursor, has_more: true },
    ];
    for (const data of invalid) {
      const client = new OutlineVersionReadClient(vi.fn().mockResolvedValue(response(data)) as typeof fetch);
      await expect(client.list(project, outline, 2, data.next_cursor === cursor ? cursor : null))
        .rejects.toMatchObject({ code: "OUTLINE_VERSION_UNAVAILABLE" });
    }
    const client = new OutlineVersionReadClient(vi.fn().mockResolvedValue(response({
      ...detail, declared_reference_count: 2 })) as typeof fetch);
    await expect(client.detail(project, outline, version)).rejects.toMatchObject({
      code: "OUTLINE_VERSION_UNAVAILABLE" });
  });

  it("maps only known safe errors and fails closed on transport anomalies", async () => {
    const missing = new OutlineVersionReadClient(vi.fn().mockResolvedValue(
      response("RESOURCE_NOT_FOUND", 404)) as typeof fetch);
    await expect(missing.detail(project, outline, version)).rejects.toMatchObject({
      code: "RESOURCE_NOT_FOUND" });
    const unknown = new OutlineVersionReadClient(vi.fn().mockResolvedValue(
      response("OTHER", 500)) as typeof fetch);
    await expect(unknown.list(project, outline)).rejects.toMatchObject({
      code: "OUTLINE_VERSION_UNAVAILABLE" });
    const noStoreMissing = new Response(JSON.stringify({ data: { items: [], next_cursor: null,
      has_more: false }, trace_id: trace }), { headers: { "Content-Type": "application/json",
      "X-Trace-Id": trace } });
    await expect(new OutlineVersionReadClient(vi.fn().mockResolvedValue(noStoreMissing) as typeof fetch)
      .list(project, outline)).rejects.toMatchObject({ code: "OUTLINE_VERSION_UNAVAILABLE" });
  });

  it("rejects bad route inputs before network access", async () => {
    const fetcher = vi.fn();
    const client = new OutlineVersionReadClient(fetcher as typeof fetch);
    await expect(client.list("bad", outline)).rejects.toBeInstanceOf(OutlineVersionReadError);
    await expect(client.list(project, outline, 0)).rejects.toBeInstanceOf(OutlineVersionReadError);
    await expect(client.detail(project, outline, "bad")).rejects.toBeInstanceOf(OutlineVersionReadError);
    expect(fetcher).not.toHaveBeenCalled();
  });

  it("calls a browser-style fetch without binding the client as this", async () => {
    let bound: unknown = "unobserved";
    const fetcher = function (this: unknown) {
      bound = this;
      return Promise.resolve(response({ items: [], next_cursor: null, has_more: false }));
    } as typeof fetch;
    await new OutlineVersionReadClient(fetcher).list(project, outline);
    expect(bound).toBeUndefined();
  });
});
