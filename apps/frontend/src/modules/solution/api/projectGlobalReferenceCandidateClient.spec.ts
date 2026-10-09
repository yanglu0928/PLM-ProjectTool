import { describe, expect, it, vi } from "vitest";
import { ProjectGlobalReferenceCandidateClient, ProjectGlobalReferenceCandidateError,
  parseProjectGlobalReferenceCandidatePage } from "./projectGlobalReferenceCandidateClient";

const project = "01234567-89ab-4cde-8123-456789abcdef";
const reference = "11234567-89ab-4cde-8123-456789abcdef";
const version = "21234567-89ab-4cde-8123-456789abcdef";
const trace = "31234567-89ab-4cde-8123-456789abcdef";
const cursor = `${"a".repeat(40)}.${"b".repeat(43)}`;
const item = { reference_solution_id: reference, reference_version_id: version,
  display_label: "已审定通用方案", version_no: 2, eligibility_state: "ELIGIBLE" };
function success(data: unknown, headers: Record<string, string> = {}): Response {
  return new Response(JSON.stringify({ data, trace_id: trace }), { status: 200,
    headers: { "Content-Type": "application/json", "Cache-Control": "no-store", ...headers } });
}
function failure(status: number, code: string): Response {
  return new Response(JSON.stringify({ error: { code, message: "internal" }, trace_id: trace }),
    { status, headers: { "Content-Type": "application/json", "Cache-Control": "no-store" } });
}
function client(...responses: Response[]) {
  const fetcher = vi.fn();
  for (const response of responses) fetcher.mockResolvedValueOnce(response);
  return { api: new ProjectGlobalReferenceCandidateClient(fetcher as typeof fetch), fetcher };
}

describe("ProjectGlobalReferenceCandidateClient", () => {
  it("uses only the project candidate endpoint and freezes its five-field projection", async () => {
    const { api, fetcher } = client(success({ items: [item], next_cursor: null, has_more: false }));
    const page = await api.list(project, 25);
    expect(fetcher).toHaveBeenCalledExactlyOnceWith(
      `/api/v1/projects/${project}/global-reference-candidates?page_size=25`,
      expect.objectContaining({ method: "GET", credentials: "same-origin", cache: "no-store", redirect: "error" }));
    expect(page.items).toEqual([item]);
    expect(Object.isFrozen(page.items[0])).toBe(true);
    expect(Object.isFrozen(page)).toBe(true);
  });

  it("accepts an empty visible page with a continuation cursor", async () => {
    const { api, fetcher } = client(success({ items: [], next_cursor: cursor, has_more: true }),
      success({ items: [item], next_cursor: null, has_more: false }));
    expect((await api.list(project, 50)).next_cursor).toBe(cursor);
    expect((await api.list(project, 50, cursor)).items).toEqual([item]);
    expect(fetcher.mock.calls[1]?.[0]).toContain(`cursor=${encodeURIComponent(cursor)}`);
  });

  it("rejects unknown fields, unsafe labels, duplicate roots, and invalid page states", () => {
    const page = (items: unknown[], next_cursor: string | null = null, has_more = false) =>
      ({ items, next_cursor, has_more });
    for (const bad of [
      { ...item, name: "raw" }, { ...item, display_label: " 原名" },
      { ...item, display_label: "秘密\n" }, { ...item, eligibility_state: "RESTRICTED" },
      { ...item, reference_version_id: project, source_fingerprint: "a".repeat(64) },
    ]) expect(() => parseProjectGlobalReferenceCandidatePage(page([bad]), 50))
      .toThrow(ProjectGlobalReferenceCandidateError);
    for (const badPage of [page([item, item]), page([], cursor, false),
      page([], null, true), page([], cursor, true)]) {
      expect(() => parseProjectGlobalReferenceCandidatePage(badPage, 50, cursor))
        .toThrow(ProjectGlobalReferenceCandidateError);
    }
  });

  it("rejects malformed inputs before fetch, mismatched errors and non-no-store responses", async () => {
    const { api, fetcher } = client();
    for (const input of ["../global", "00000000-0000-0000-0000-000000000000"]) {
      await expect(api.list(input)).rejects.toMatchObject({ code: "CANDIDATE_INVALID_INPUT" });
    }
    await expect(api.list(project, 101)).rejects.toMatchObject({ code: "CANDIDATE_INVALID_INPUT" });
    await expect(api.list(project, 20, "raw")).rejects.toMatchObject({ code: "CANDIDATE_INVALID_INPUT" });
    expect(fetcher).not.toHaveBeenCalled();
    await expect(client(failure(404, "RESOURCE_NOT_FOUND")).api.list(project))
      .rejects.toMatchObject({ code: "RESOURCE_NOT_FOUND" });
    await expect(client(failure(403, "LICENSE_OPERATION_DENIED")).api.list(project))
      .rejects.toMatchObject({ code: "LICENSE_OPERATION_DENIED" });
    await expect(client(failure(403, "AUTH_SESSION_EXPIRED")).api.list(project))
      .rejects.toMatchObject({ code: "CANDIDATE_UNAVAILABLE" });
    await expect(client(success({ items: [], next_cursor: null, has_more: false },
      { "Cache-Control": "public" })).api.list(project))
      .rejects.toMatchObject({ code: "CANDIDATE_UNAVAILABLE" });
  });
});
