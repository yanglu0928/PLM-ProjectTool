import { afterEach, describe, expect, it, vi } from "vitest";
import { OutlineReadClient, OutlineReadError, parseOutlineCurrent, parseOutlinePage } from "./outlineReadClient";

const project = "01234567-89ab-4cde-8123-456789abcdef";
const outline = "11234567-89ab-4cde-8123-456789abcdef";
const actor = "21234567-89ab-4cde-8123-456789abcdef";
const trace = "31234567-89ab-4cde-8123-456789abcdef";
const token = `${"a".repeat(40)}.${"b".repeat(43)}`;
const item = { solution_outline_id: outline, project_id: project, name: "项目方案目录",
  outline_state: "ACTIVE", current_approved_version_ref: null,
  created_at: "2026-10-09T00:00:00Z", etag: '"v0"' };
const detail = { ...item, created_by: actor };
function success(data: unknown, header?: string): Response {
  return new Response(JSON.stringify({ data, trace_id: trace }), { status: 200,
    headers: { "Content-Type": "application/json", ...(header ? { ETag: header } : {}) } });
}
function failure(status: number, code: string): Response {
  return new Response(JSON.stringify({ error: { code, message: "internal" }, trace_id: trace }),
    { status, headers: { "Content-Type": "application/json" } });
}
function client(...responses: Response[]) {
  const fetcher = vi.fn();
  for (const response of responses) fetcher.mockResolvedValueOnce(response);
  return { api: new OutlineReadClient(fetcher as typeof fetch), fetcher };
}

describe("OutlineReadClient", () => {
  afterEach(() => vi.restoreAllMocks());

  it("requests a project-only safe summary page with opaque cursor", async () => {
    const { api, fetcher } = client(success({ items: [item], next_cursor: token, has_more: true }));
    const page = await api.list(project, 25);
    expect(fetcher).toHaveBeenCalledExactlyOnceWith(
      `/api/v1/projects/${project}/solution-outlines?page_size=25`,
      expect.objectContaining({ method: "GET", credentials: "same-origin", cache: "no-store", redirect: "error" }));
    expect(page.items).toEqual([item]);
    expect(page.next_cursor).toBe(token);
    expect(Object.isFrozen(page.items[0])).toBe(true);
    expect(() => parseOutlinePage({ items: [item, item], next_cursor: null, has_more: false }, project, 50))
      .toThrow(OutlineReadError);
  });

  it("uses browser fetch without binding the client as receiver", async () => {
    const fetcher = vi.fn(function (this: unknown) {
      expect(this).toBeUndefined();
      return Promise.resolve(success({ items: [], next_cursor: null, has_more: false }));
    });
    await expect(new OutlineReadClient(fetcher as typeof fetch).list(project))
      .resolves.toMatchObject({ items: [] });
  });

  it("requires exact root, project, approved pointer shape and ETag", async () => {
    const { api, fetcher } = client(success(detail, '"v0"'));
    expect(await api.current(project, outline)).toEqual(detail);
    expect(fetcher.mock.calls[0]?.[0]).toBe(`/api/v1/projects/${project}/solution-outlines/${outline}`);
    await expect(client(success(detail, '"v1"')).api.current(project, outline))
      .rejects.toMatchObject({ code: "OUTLINE_UNAVAILABLE" });
    for (const corrupt of [
      { ...detail, project_id: actor },
      { ...detail, solution_outline_id: actor },
      { ...detail, current_approved_version_ref: "DRAFT" },
      { ...detail, created_by: "invalid" },
      { ...detail, storage_path: "private" },
    ]) expect(() => parseOutlineCurrent(corrupt, project, outline)).toThrow(OutlineReadError);
  });

  it("rejects malformed input before network and only maps known errors", async () => {
    const { api, fetcher } = client();
    await expect(api.list("../global")).rejects.toMatchObject({ code: "OUTLINE_INVALID_INPUT" });
    await expect(api.current(project, "../global")).rejects.toMatchObject({ code: "OUTLINE_INVALID_INPUT" });
    await expect(api.list(project, 101)).rejects.toMatchObject({ code: "OUTLINE_INVALID_INPUT" });
    expect(fetcher).not.toHaveBeenCalled();
    await expect(client(failure(404, "RESOURCE_NOT_FOUND")).api.current(project, outline))
      .rejects.toMatchObject({ code: "RESOURCE_NOT_FOUND" });
    await expect(client(failure(403, "AUTH_SESSION_EXPIRED")).api.list(project))
      .rejects.toMatchObject({ code: "OUTLINE_UNAVAILABLE" });
  });
});
