import { afterEach, describe, expect, it, vi } from "vitest";
import { PlanReadClient, PlanReadError, parsePlanCurrent, parsePlanPage } from "./planReadClient";

const project = "01234567-89ab-4cde-8123-456789abcdef";
const first = "21234567-89ab-4cde-8123-456789abcdef";
const second = "11234567-89ab-4cde-8123-456789abcdef";
const actor = "31234567-89ab-4cde-8123-456789abcdef";
const trace = "41234567-89ab-4cde-8123-456789abcdef";
const token = `${"a".repeat(40)}.${"b".repeat(43)}`;
const item = { plan_id: first, project_id: project, name: "实施计划",
  plan_state: "ACTIVE", current_approved_version_ref: null,
  created_at: "2026-10-19T00:00:00Z", etag: '"v0"' };
const detail = { ...item, created_by: actor };
function success(data: unknown, header?: string): Response {
  return new Response(JSON.stringify({ data, trace_id: trace }), { status: 200,
    headers: { "Content-Type": "application/json", ...(header ? { ETag: header } : {}) } });
}
function failure(status: number, code: string): Response {
  return new Response(JSON.stringify({ error: { code }, trace_id: trace }),
    { status, headers: { "Content-Type": "application/json" } });
}
function client(...responses: Response[]) {
  const fetcher = vi.fn();
  for (const response of responses) fetcher.mockResolvedValueOnce(response);
  return { api: new PlanReadClient(fetcher as typeof fetch), fetcher };
}

describe("PlanReadClient", () => {
  afterEach(() => vi.restoreAllMocks());

  it("requests project-only summaries with bounded opaque cursor", async () => {
    const { api, fetcher } = client(success({ items: [item], next_cursor: token, has_more: true }));
    const page = await api.list(project, 200);
    expect(fetcher).toHaveBeenCalledExactlyOnceWith(`/api/v1/projects/${project}/plans?page_size=200`,
      expect.objectContaining({ method: "GET", credentials: "same-origin", cache: "no-store",
        redirect: "error" }));
    expect(page.items).toEqual([item]);
    expect(page.next_cursor).toBe(token);
    expect(Object.isFrozen(page.items[0])).toBe(true);
  });

  it("enforces created-time DESC and Plan ID DESC including microseconds", () => {
    expect(parsePlanPage({ items: [
      { ...item, created_at: "2026-10-19T00:00:00.000001Z" },
      { ...item, plan_id: second, created_at: "2026-10-19T00:00:00Z" },
    ], next_cursor: null, has_more: false }, project, 50).items).toHaveLength(2);
    for (const corrupt of [
      [item, { ...item, plan_id: second, created_at: "2026-10-19T00:00:00.000001Z" }],
      [{ ...item, plan_id: second }, item],
      [item, item],
    ]) expect(() => parsePlanPage({ items: corrupt, next_cursor: null, has_more: false },
      project, 50)).toThrow(PlanReadError);
  });

  it("requires exact current identity, null approval pointer and ETag", async () => {
    const { api, fetcher } = client(success(detail, '"v0"'));
    expect(await api.current(project, first)).toEqual(detail);
    expect(fetcher.mock.calls[0]?.[0]).toBe(`/api/v1/projects/${project}/plans/${first}`);
    await expect(client(success(detail, '"v1"')).api.current(project, first))
      .rejects.toMatchObject({ code: "PLAN_UNAVAILABLE" });
    for (const corrupt of [
      { ...detail, project_id: actor }, { ...detail, plan_id: actor },
      { ...detail, current_approved_version_ref: second },
      { ...detail, created_by: "invalid" }, { ...detail, storage_path: "private" },
    ]) expect(() => parsePlanCurrent(corrupt, project, first)).toThrow(PlanReadError);
  });

  it("rejects malformed input before network and maps only known errors", async () => {
    const { api, fetcher } = client();
    await expect(api.list("../global")).rejects.toMatchObject({ code: "PLAN_INVALID_INPUT" });
    await expect(api.current(project, "../global")).rejects.toMatchObject({ code: "PLAN_INVALID_INPUT" });
    await expect(api.list(project, 201)).rejects.toMatchObject({ code: "PLAN_INVALID_INPUT" });
    await expect(api.list(project, 1, "bad")).rejects.toMatchObject({ code: "PLAN_INVALID_INPUT" });
    expect(fetcher).not.toHaveBeenCalled();
    await expect(client(failure(404, "RESOURCE_NOT_FOUND")).api.current(project, first))
      .rejects.toMatchObject({ code: "RESOURCE_NOT_FOUND" });
    await expect(client(failure(403, "AUTH_SESSION_EXPIRED")).api.list(project))
      .rejects.toMatchObject({ code: "PLAN_UNAVAILABLE" });
  });
});
