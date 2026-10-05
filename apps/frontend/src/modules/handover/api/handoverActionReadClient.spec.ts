import { afterEach, describe, expect, it, vi } from "vitest";
import { HandoverActionReadClient, HandoverActionReadError, parseHandoverActionDetail,
  type HandoverActionCursor } from "./handoverActionReadClient";
const project = "01234567-89ab-4cde-8123-456789abcdef"; const action = "11234567-89ab-4cde-8123-456789abcdef";
const actor = "21234567-89ab-4cde-8123-456789abcdef"; const version = "31234567-89ab-4cde-8123-456789abcdef";
const item = "41234567-89ab-4cde-8123-456789abcdef"; const document = "51234567-89ab-4cde-8123-456789abcdef";
const evidence = "61234567-89ab-4cde-8123-456789abcdef"; const trace = "71234567-89ab-4cde-8123-456789abcdef";
const now = "2026-10-05T12:00:00Z"; const token = `${"A".repeat(20)}.${"B".repeat(43)}`;
const summary = { action_item_id: action, source_kind: "ANALYSIS_ITEM", action_type: "CONFIRM_DECISION",
  title: "确认部署范围", owner_ref: actor, due_at: "2026-10-10T12:00:00Z", priority: "HIGH", action_state: "SUBMITTED",
  submitted_at: now, verified_at: null, closed_at: null, resolution_trace_ref: null, updated_at: now, etag: '"v2"' };
const detail = { ...summary, source_analysis_version_ref: version, source_item_id: item, human_source_reason: null,
  requested_input_spec: { fields: [{ name: "部署范围", format: "文本", example: "总部与工厂", required: true }] },
  responses: [{ document_id: document, document_version_id: version, ordinal: 0 }],
  evidence: [{ evidence_id: evidence, purpose: "SUBMISSION", ordinal: 0 }], created_by: actor, created_reason: "承接待确认项",
  created_at: "2026-10-04T12:00:00Z", verified_by: null, current_event: { action_state_event_id: trace, sequence_no: 2,
    from_state: "IN_PROGRESS", to_state: "SUBMITTED", actor_id: actor, reason: "已提交资料", occurred_at: now } };
function ok(data: unknown, tag?: string) { return new Response(JSON.stringify({ data, trace_id: trace }),
  { headers: { "Content-Type": "application/json", ...(tag ? { ETag: tag } : {}) } }); }
function failure(status: number, code: string) { return new Response(JSON.stringify({ error: { code, message: "private" }, trace_id: trace }),
  { status, headers: { "Content-Type": "application/json" } }); }
function client(...values: Response[]) { const fetcher = vi.fn(); values.forEach(v => fetcher.mockResolvedValueOnce(v));
  return { api: new HandoverActionReadClient(fetcher as typeof fetch), fetcher }; }
describe("HandoverActionReadClient", () => {
  afterEach(() => { vi.restoreAllMocks(); vi.useRealTimers(); });
  it("reads safe ordered summaries and passes opaque cursor", async () => { const { api, fetcher } = client(ok({ items: [summary], next_cursor: token, has_more: true }));
    const page = await api.list(project, 25); expect(page.next_cursor).toBe(token); expect(Object.isFrozen(page.items[0])).toBe(true);
    expect(fetcher.mock.calls[0][0]).toBe(`/api/v1/projects/${project}/handover-action-items?page_size=25`); });
  it("reads detail with strong ETag and explicit requested fields", async () => { const value = await client(ok(detail, '"v2"')).api.get(project, action);
    expect(value.requested_input_spec.fields[0]).toMatchObject({ name: "部署范围", required: true });
    expect(value.action_state).toBe("SUBMITTED"); expect(value.closed_at).toBeNull(); });
  it("passes the server cursor unchanged", async () => { const { api, fetcher } = client(ok({ items: [], next_cursor: null, has_more: false }));
    await api.list(project, 50, token as HandoverActionCursor); expect(fetcher.mock.calls[0][0]).toContain(`cursor=${token}`); });
  it.each([{ ...detail, private_text: "secret" }, { ...detail, source_item_id: null },
    { ...detail, requested_input_spec: {} }, { ...detail, responses: [{ ...detail.responses[0], ordinal: 2 }] },
    { ...detail, current_event: { ...detail.current_event, to_state: "CLOSED" } }])("rejects unsafe detail %#", bad => {
    expect(() => parseHandoverActionDetail(bad, action)).toThrowError(HandoverActionReadError); });
  it("rejects SUBMITTED as CLOSED and incomplete CLOSED", () => { expect(() => parseHandoverActionDetail({ ...detail,
    action_state: "CLOSED" }, action)).toThrowError(HandoverActionReadError); });
  it.each(["../admin", project.toUpperCase(), "00000000-0000-0000-0000-000000000000"])("rejects unsafe id %s", async bad => {
    const { api, fetcher } = client(ok({ items: [], next_cursor: null, has_more: false }));
    await expect(api.get(project, bad)).rejects.toMatchObject({ code: "HANDOVER_ACTION_INVALID_INPUT" }); expect(fetcher).not.toHaveBeenCalled(); });
  it.each([[401, "AUTH_SESSION_EXPIRED"], [403, "LICENSE_OPERATION_DENIED"], [404, "RESOURCE_NOT_FOUND"]] as const)(
    "maps safe error %s %s", async (status, code) => { await expect(client(failure(status, code)).api.get(project, action)).rejects.toMatchObject({ code }); });
  it("fails closed on ETag drift and mismatched error", async () => {
    await expect(client(ok(detail, '"v3"')).api.get(project, action)).rejects.toMatchObject({ code: "HANDOVER_ACTION_UNAVAILABLE" });
    await expect(client(failure(403, "RESOURCE_NOT_FOUND")).api.get(project, action)).rejects.toMatchObject({ code: "HANDOVER_ACTION_UNAVAILABLE" }); });
});
