import { afterEach, describe, expect, it, vi } from "vitest";
import {
  OutputRequestListClient, OutputRequestListError, outputRequestFollows,
  parseOutputRequestPage,
} from "./outputRequestListClient";

const project = "01234567-89ab-4cde-8123-456789abcdef";
const first = "21234567-89ab-4cde-8123-456789abcdef";
const second = "11234567-89ab-4cde-8123-456789abcdef";
const source = "31234567-89ab-4cde-8123-456789abcdef";
const template = "41234567-89ab-4cde-8123-456789abcdef";
const context = "51234567-89ab-4cde-8123-456789abcdef";
const trace = "61234567-89ab-4cde-8123-456789abcdef";
const token = "a".repeat(40) + "." + "b".repeat(43);
const item = {
  output_request_id: first, project_id: project, output_type: "DOCX",
  template_version_ref: template, source_version_refs: [source],
  output_policy_ref: "output.policy.synthetic.v1", plugin_operation: "word.generate",
  context_snapshot_ref: context, context_fingerprint: "a".repeat(64),
  state: "QUEUED", job_ref: null, execution_ref: null, generation_no: 1,
  requested_at: "2026-10-19T00:00:00Z", completed_at: null, etag: '"v0"',
};
function success(data: unknown): Response {
  return new Response(JSON.stringify({ data, trace_id: trace }), {
    status: 200, headers: { "Content-Type": "application/json" },
  });
}
function failure(status: number, code: string): Response {
  return new Response(JSON.stringify({ error: { code, message: "private" }, trace_id: trace }), {
    status, headers: { "Content-Type": "application/json" },
  });
}
function client(...responses: Response[]) {
  const fetcher = vi.fn();
  for (const response of responses) fetcher.mockResolvedValueOnce(response);
  return { api: new OutputRequestListClient(fetcher as typeof fetch), fetcher };
}

describe("OutputRequestListClient", () => {
  afterEach(() => vi.restoreAllMocks());

  it("uses same-origin GET and bounded cursor pagination", async () => {
    const { api, fetcher } = client(success({ items: [item], next_cursor: token, has_more: true }));
    const page = await api.list(project, 50);
    expect(fetcher).toHaveBeenCalledExactlyOnceWith(
      "/api/v1/projects/" + project + "/output-requests?page_size=50",
      expect.objectContaining({ method: "GET", credentials: "same-origin", cache: "no-store",
        redirect: "error" }),
    );
    expect(page.items).toEqual([{
      output_request_id: first, project_id: project, output_type: "DOCX", state: "QUEUED",
      requested_at: "2026-10-19T00:00:00Z", completed_at: null,
    }]);
    expect(Object.isFrozen(page.items[0])).toBe(true);
    const next = client(success({ items: [{ ...item, output_request_id: second,
      requested_at: "2026-10-18T00:00:00Z" }], next_cursor: null, has_more: false }));
    await next.api.list(project, 50, token);
    expect(next.fetcher.mock.calls[0]?.[0]).toContain("&cursor=" + token);
  });

  it("orders pages by request timestamp and id descending, including microseconds", () => {
    const later = { ...item, requested_at: "2026-10-19T00:00:00.000001Z" };
    const sameTimeLowerId = { ...item, output_request_id: second,
      requested_at: "2026-10-19T00:00:00Z" };
    const parsed = parseOutputRequestPage({ items: [later, sameTimeLowerId],
      next_cursor: null, has_more: false }, project, 50);
    expect(parsed.items).toHaveLength(2);
    expect(outputRequestFollows(parsed.items[0]!, parsed.items[1]!)).toBe(true);
    for (const corrupt of [
      [item, { ...item, output_request_id: second, requested_at: "2026-10-19T00:00:00.000001Z" }],
      [item, item],
      [{ ...item, output_request_id: second }, item],
    ]) expect(() => parseOutputRequestPage({ items: corrupt, next_cursor: null,
      has_more: false }, project, 50)).toThrow(OutputRequestListError);
  });

  it("validates the complete wire projection and discards sensitive implementation fields", () => {
    const parsed = parseOutputRequestPage({ items: [item], next_cursor: null,
      has_more: false }, project, 50);
    expect(parsed.items[0]).not.toHaveProperty("context_fingerprint");
    expect(parsed.items[0]).not.toHaveProperty("plugin_operation");
    for (const corrupt of [
      { ...item, project_id: source }, { ...item, context_fingerprint: "bad" },
      { ...item, state: "UNKNOWN" }, { ...item, source_version_refs: [] },
      { ...item, source_version_refs: [source, source] }, { ...item, extra: "private" },
    ]) expect(() => parseOutputRequestPage({ items: [corrupt], next_cursor: null,
      has_more: false }, project, 50)).toThrow(OutputRequestListError);
  });

  it("rejects malformed paging state before network access and maps only frozen errors", async () => {
    const { api, fetcher } = client();
    await expect(api.list("../global")).rejects.toMatchObject({ code: "OUTPUT_INVALID_INPUT" });
    await expect(api.list(project, 201)).rejects.toMatchObject({ code: "OUTPUT_INVALID_INPUT" });
    await expect(api.list(project, 1, "bad")).rejects.toMatchObject({ code: "OUTPUT_INVALID_INPUT" });
    expect(fetcher).not.toHaveBeenCalled();
    await expect(client(failure(404, "RESOURCE_NOT_FOUND")).api.list(project))
      .rejects.toMatchObject({ code: "RESOURCE_NOT_FOUND" });
    await expect(client(failure(403, "AUTH_SESSION_EXPIRED")).api.list(project))
      .rejects.toMatchObject({ code: "OUTPUT_UNAVAILABLE" });
  });
});
