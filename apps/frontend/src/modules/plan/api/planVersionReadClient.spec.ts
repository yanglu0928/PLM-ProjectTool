import { describe, expect, it, vi } from "vitest";
import { PlanVersionReadClient, PlanVersionReadError } from "./planVersionReadClient";
const project = "01234567-89ab-4cde-8123-456789abcdef";
const plan = "11234567-89ab-4cde-8123-456789abcdef";
const version = "21234567-89ab-4cde-8123-456789abcdef";
const user = "31234567-89ab-4cde-8123-456789abcdef";
const trace = "41234567-89ab-4cde-8123-456789abcdef";
const row = { plan_version_id: version, plan_id: plan, project_id: project, version_no: 1,
  version_state: "DRAFT", created_by: user, supersedes_version_ref: null, review_ref: null,
  review_round_ref: null, created_at: "2026-10-26T00:00:00Z" };
function response(data: unknown, status = 200) { return new Response(JSON.stringify({ data, trace_id: trace }), { status,
  headers: { "Content-Type": "application/json", "Cache-Control": "no-store", "X-Trace-Id": trace } }); }
describe("PlanVersionReadClient", () => {
  it("calls the fetcher without binding the client as its receiver", async () => {
    const fetcher = vi.fn(function (this: unknown) {
      expect(this).toBeUndefined();
      return Promise.resolve(response({ items: [], next_cursor: null, has_more: false }));
    }) as unknown as typeof fetch;
    await new PlanVersionReadClient(fetcher).list(project, plan);
    expect(fetcher).toHaveBeenCalledOnce();
  });
  it("reads frozen list and fixed snapshot endpoints with strict envelopes", async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(response({ items: [row], next_cursor: null, has_more: false }))
      .mockResolvedValueOnce(response({ ...row, calendar_ref: "WORKING_DAYS", approved_solution_refs: [], wbs_items: [], dependencies: [], milestones: [], exclusions: [] }));
    const client = new PlanVersionReadClient(fetcher as typeof fetch);
    expect((await client.list(project, plan)).items[0]?.plan_version_id).toBe(version);
    expect(fetcher.mock.calls[0]?.[0]).toContain(`/projects/${project}/plans/${plan}/versions?page_size=50`);
    const detail = await client.detail(project, plan, version);
    expect(detail.calendar_ref).toBe("WORKING_DAYS"); expect(detail.wbs_items).toEqual([]);
    expect(fetcher.mock.calls[1]?.[0]).toBe(`/api/v1/projects/${project}/plans/${plan}/versions/${version}`);
  });
  it("fails closed on unexpected fixed snapshot fields or invalid path identity", async () => {
    const client = new PlanVersionReadClient(vi.fn().mockResolvedValue(response({ ...row, calendar_ref: null,
      approved_solution_refs: [], wbs_items: [], dependencies: [], milestones: [], exclusions: [], unexpected: true })) as typeof fetch);
    await expect(client.detail(project, plan, version)).rejects.toBeInstanceOf(PlanVersionReadError);
    await expect(client.list("bad", plan)).rejects.toMatchObject({ code: "PLAN_VERSION_READ_INVALID" });
  });
});
