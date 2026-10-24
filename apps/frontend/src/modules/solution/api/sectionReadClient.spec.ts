import { afterEach, describe, expect, it, vi } from "vitest";
import { SectionReadClient, SectionReadError, parseSectionCurrent, parseSectionPage } from "./sectionReadClient";

const project = "01234567-89ab-4cde-8123-456789abcdef";
const outline = "11234567-89ab-4cde-8123-456789abcdef";
const section = "21234567-89ab-4cde-8123-456789abcdef";
const actor = "31234567-89ab-4cde-8123-456789abcdef";
const trace = "41234567-89ab-4cde-8123-456789abcdef";
const token = `${"a".repeat(40)}.${"b".repeat(43)}`;
const item = { solution_section_id: section, solution_outline_id: outline, project_id: project,
  section_key: "范围与目标", section_state: "ACTIVE", current_approved_version_ref: null,
  created_at: "2026-10-09T00:00:00Z", etag: '"v0"' };
const detail = { ...item, created_by: actor };
function success(data: unknown, header?: string): Response {
  return new Response(JSON.stringify({ data, trace_id: trace }), { status: 200,
    headers: { "Content-Type": "application/json", "Cache-Control": "no-store", "X-Trace-Id": trace,
      ...(header ? { ETag: header } : {}) } });
}
function failure(status: number, code: string): Response {
  return new Response(JSON.stringify({ error: { code, message: "internal" }, trace_id: trace }),
    { status, headers: { "Content-Type": "application/json", "Cache-Control": "no-store",
      "X-Trace-Id": trace } });
}
function client(...responses: Response[]) {
  const fetcher = vi.fn();
  for (const response of responses) fetcher.mockResolvedValueOnce(response);
  return { api: new SectionReadClient(fetcher as typeof fetch), fetcher };
}

describe("SectionReadClient", () => {
  afterEach(() => vi.restoreAllMocks());

  it("requests a project-only safe summary page with an opaque Section cursor", async () => {
    const { api, fetcher } = client(success({ items: [item], next_cursor: token, has_more: true }));
    const page = await api.list(project, 25);
    expect(fetcher).toHaveBeenCalledExactlyOnceWith(
      `/api/v1/projects/${project}/solution-sections?page_size=25`,
      expect.objectContaining({ method: "GET", credentials: "same-origin", cache: "no-store",
        redirect: "error" }));
    expect(page.items).toEqual([item]);
    expect(page.next_cursor).toBe(token);
    expect(Object.isFrozen(page.items[0])).toBe(true);
    const next = client(success({ items: [], next_cursor: null, has_more: false }));
    await next.api.list(project, 25, token);
    expect(next.fetcher.mock.calls[0]?.[0]).toBe(
      `/api/v1/projects/${project}/solution-sections?page_size=25&cursor=${token}`);
  });

  it("uses browser fetch without binding the client as receiver", async () => {
    const fetcher = vi.fn(function (this: unknown) {
      expect(this).toBeUndefined();
      return Promise.resolve(success({ items: [], next_cursor: null, has_more: false }));
    });
    await expect(new SectionReadClient(fetcher as typeof fetch).list(project))
      .resolves.toMatchObject({ items: [] });
  });

  it("requires exact detail, project, Section identity, source fields and matching strong ETag", async () => {
    const { api, fetcher } = client(success(detail, '"v0"'));
    expect(await api.current(project, section)).toEqual(detail);
    expect(fetcher.mock.calls[0]?.[0]).toBe(`/api/v1/projects/${project}/solution-sections/${section}`);
    await expect(client(success(detail, '"v1"')).api.current(project, section))
      .rejects.toMatchObject({ code: "SECTION_UNAVAILABLE" });
    for (const corrupt of [
      { ...detail, project_id: actor }, { ...detail, solution_section_id: actor },
      { ...detail, solution_outline_id: "bad" }, { ...detail, section_key: "  " },
      { ...detail, current_approved_version_ref: "DRAFT" },
      { ...detail, created_by: "invalid" }, { ...detail, document_body: "private" },
    ]) expect(() => parseSectionCurrent(corrupt, project, section)).toThrow(SectionReadError);
  });

  it("rejects unsorted, duplicate, malformed and cross-project pages", () => {
    const later = { ...item, solution_section_id: actor };
    for (const corrupt of [
      { items: [item, item], next_cursor: null, has_more: false },
      { items: [later, item], next_cursor: null, has_more: false },
      { items: [{ ...item, project_id: actor }], next_cursor: null, has_more: false },
      { items: [], next_cursor: token, has_more: true },
      { items: [item], next_cursor: token, has_more: false },
      { items: [item], next_cursor: null, has_more: false, body: "private" },
    ]) expect(() => parseSectionPage(corrupt, project, 50)).toThrow(SectionReadError);
    expect(() => parseSectionPage({ items: [item], next_cursor: token, has_more: true },
      project, 50, token)).toThrow(SectionReadError);
  });

  it("rejects bad input before network and maps only matching known errors", async () => {
    const { api, fetcher } = client();
    await expect(api.list("../global")).rejects.toMatchObject({ code: "SECTION_INVALID_INPUT" });
    await expect(api.current(project, "../global")).rejects.toMatchObject({ code: "SECTION_INVALID_INPUT" });
    await expect(api.list(project, 101)).rejects.toMatchObject({ code: "SECTION_INVALID_INPUT" });
    await expect(api.list(project, 50, "not-signed")).rejects.toMatchObject({ code: "SECTION_INVALID_INPUT" });
    expect(fetcher).not.toHaveBeenCalled();
    await expect(client(failure(404, "RESOURCE_NOT_FOUND")).api.current(project, section))
      .rejects.toMatchObject({ code: "RESOURCE_NOT_FOUND" });
    await expect(client(failure(403, "LICENSE_OPERATION_DENIED")).api.list(project))
      .rejects.toMatchObject({ code: "LICENSE_OPERATION_DENIED" });
    await expect(client(failure(403, "AUTH_SESSION_EXPIRED")).api.list(project))
      .rejects.toMatchObject({ code: "SECTION_UNAVAILABLE" });
  });

  it("fails closed on untrusted media, trace, cache or network outcome", async () => {
    const missingTrace = new Response(JSON.stringify({ data: { items: [], next_cursor: null,
      has_more: false }, trace_id: trace }), { status: 200,
      headers: { "Content-Type": "application/json", "Cache-Control": "no-store" } });
    await expect(client(missingTrace).api.list(project))
      .rejects.toMatchObject({ code: "SECTION_UNAVAILABLE" });
    const badMedia = new Response("text", { status: 200, headers: { "Content-Type": "text/plain" } });
    await expect(client(badMedia).api.list(project))
      .rejects.toMatchObject({ code: "SECTION_UNAVAILABLE" });
    const fetcher = vi.fn().mockRejectedValue(new Error("network"));
    await expect(new SectionReadClient(fetcher as typeof fetch).list(project))
      .rejects.toMatchObject({ code: "SECTION_UNAVAILABLE" });
  });
});
