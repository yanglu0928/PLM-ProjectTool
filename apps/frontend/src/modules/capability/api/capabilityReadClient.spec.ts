import { describe, expect, it, vi } from "vitest";
import { CapabilityReadClient } from "./capabilityReadClient";

const baselineId = "01234567-89ab-4cde-8123-456789abcdef";
const versionId = "11234567-89ab-4cde-8123-456789abcdef";
const itemId = "21234567-89ab-4cde-8123-456789abcdef";
const traceId = "31234567-89ab-4cde-8123-456789abcdef";
const cursor = `${"a".repeat(36)}.${"b".repeat(43)}`;
const baseline = { baseline_id: baselineId, baseline_code: "STD-01", name: "标准能力", description: "",
  state: "ACTIVE", source_collection_ref: `sha256:${"a".repeat(64)}`,
  current_approved_version_ref: versionId, created_at: "2026-10-24T01:00:00Z",
  updated_at: "2026-10-24T01:00:00Z", etag: '"v1"' };
const version = { baseline_version_id: versionId, baseline_id: baselineId, version_no: 1,
  state: "APPROVED", source_collection_ref: baseline.source_collection_ref,
  content_fingerprint: "b".repeat(64), declared_item_count: 1,
  declared_document_ref_count: 0, declared_evidence_ref_count: 0,
  supersedes_version_ref: null, review_ref: null, review_round_ref: null,
  created_at: "2026-10-24T01:00:00Z" };
const item = { capability_item_id: itemId, baseline_version_id: versionId, baseline_id: baselineId,
  ordinal: 0, capability_code: "C-01", domain_name: "", module_name: "", feature_name: "",
  name: "能力", description: "", boundary: "", prerequisites: [], interface_refs: [],
  state: "AVAILABLE", document_version_refs: [], evidence_refs: [] };
function response(data: unknown): Response { return new Response(JSON.stringify({ data, trace_id: traceId }),
  { status: 200, headers: { "Content-Type": "application/json" } }); }
function error(status: number, code: string): Response { return new Response(JSON.stringify({
  error: { code, message: "private" }, trace_id: traceId }),
  { status, headers: { "Content-Type": "application/json" } }); }
function make(...responses: Response[]) {
  const fetcher = vi.fn(); responses.forEach(value => fetcher.mockResolvedValueOnce(value));
  return { client: new CapabilityReadClient(fetcher as typeof fetch), fetcher };
}
describe("CapabilityReadClient", () => {
  it("reads exact metadata without a constructor request", async () => {
    const { client, fetcher } = make(response({ items: [baseline], next_cursor: cursor, has_more: true }),
      response(baseline), response({ items: [version], next_cursor: null, has_more: false }),
      response(version), response({ items: [item], next_cursor: null, has_more: false }));
    expect(fetcher).not.toHaveBeenCalled();
    expect(await client.listBaselines()).toEqual({ items: [baseline], next_cursor: cursor, has_more: true });
    expect(await client.getBaseline(baselineId)).toEqual(baseline);
    expect(await client.listVersions(baselineId)).toEqual({ items: [version], next_cursor: null, has_more: false });
    expect(await client.getVersion(baselineId, versionId)).toEqual(version);
    expect(await client.listItems(baselineId, versionId)).toEqual({ items: [item], next_cursor: null, has_more: false });
    expect(fetcher.mock.calls.map(call => call[0])).toEqual([
      "/api/v1/global/capability-baselines?page_size=50",
      `/api/v1/global/capability-baselines/${baselineId}`,
      `/api/v1/global/capability-baselines/${baselineId}/versions?page_size=50`,
      `/api/v1/global/capability-baselines/${baselineId}/versions/${versionId}`,
      `/api/v1/global/capability-baselines/${baselineId}/versions/${versionId}/items?page_size=50`,
    ]);
    expect(fetcher.mock.calls[0]?.[1]).toMatchObject({ method: "GET", credentials: "same-origin",
      cache: "no-store", redirect: "error", headers: { Accept: "application/json" } });
  });
  it("keeps an opaque cursor and rejects invalid local identifiers", async () => {
    const { client, fetcher } = make(response({ items: [], next_cursor: null, has_more: false }));
    await client.listBaselines(cursor);
    expect(fetcher.mock.calls[0]?.[0]).toContain(`cursor=${cursor}`);
    expect(() => client.listBaselines("bad")).toThrowError(/列表位置无效/);
    await expect(client.getBaseline("../other")).rejects.toMatchObject({ code: "CAPABILITY_INVALID_ID" });
    expect(fetcher).toHaveBeenCalledTimes(1);
  });
  it("fails closed on foreign identities, extra fields and impossible pages", async () => {
    await expect(make(response({ ...baseline, private_path: "secret" })).client.getBaseline(baselineId))
      .rejects.toMatchObject({ code: "CAPABILITY_READ_UNAVAILABLE" });
    await expect(make(response({ ...version, baseline_id: traceId })).client.getVersion(baselineId, versionId))
      .rejects.toMatchObject({ code: "CAPABILITY_READ_UNAVAILABLE" });
    await expect(make(response({ items: [item, item], next_cursor: null, has_more: false }))
      .client.listItems(baselineId, versionId)).rejects.toMatchObject({ code: "CAPABILITY_READ_UNAVAILABLE" });
    await expect(make(response({ items: [], next_cursor: cursor, has_more: true })).client.listBaselines())
      .rejects.toMatchObject({ code: "CAPABILITY_READ_UNAVAILABLE" });
  });
  it("maps only known status/code pairs and never exposes server details", async () => {
    await expect(make(error(404, "RESOURCE_NOT_FOUND")).client.getBaseline(baselineId))
      .rejects.toMatchObject({ code: "RESOURCE_NOT_FOUND" });
    await expect(make(error(500, "RESOURCE_NOT_FOUND")).client.getBaseline(baselineId))
      .rejects.toMatchObject({ code: "CAPABILITY_READ_UNAVAILABLE" });
    await expect(make(new Response("<html>secret</html>", { status: 200,
      headers: { "Content-Type": "text/html" } })).client.getBaseline(baselineId))
      .rejects.toMatchObject({ code: "CAPABILITY_READ_UNAVAILABLE" });
  });
});
