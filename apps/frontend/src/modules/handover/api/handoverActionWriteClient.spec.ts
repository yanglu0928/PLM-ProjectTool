import { afterEach, describe, expect, it, vi } from "vitest";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { HandoverActionWriteClient, HandoverActionWriteError, type CreateHandoverActionInput } from "./handoverActionWriteClient";

const actor = "01234567-89ab-4cde-8123-456789abcdef"; const project = "11234567-89ab-4cde-8123-456789abcdef";
const action = "21234567-89ab-4cde-8123-456789abcdef"; const event = "31234567-89ab-4cde-8123-456789abcdef";
const document = "41234567-89ab-4cde-8123-456789abcdef"; const documentVersion = "51234567-89ab-4cde-8123-456789abcdef";
const evidence = "61234567-89ab-4cde-8123-456789abcdef"; const traceTarget = "71234567-89ab-4cde-8123-456789abcdef";
const versionRef = "81234567-89ab-4cde-8123-456789abcdef"; const itemRef = "91234567-89ab-4cde-8123-456789abcdef";
const now = "2026-10-05T12:00:00Z"; const due = "2026-10-10T12:00:00Z"; const key = "handover-action-attempt-0001";
const spec = { fields: [{ name: "部署范围", format: "文本", example: "总部与工厂", required: true }] } as const;
const input: CreateHandoverActionInput = { source_analysis_version_ref: versionRef, source_item_id: itemRef,
  human_source_reason: null, action_type: "CONFIRM_DECISION", title: "确认部署范围", requested_input_spec: spec,
  owner_ref: actor, due_at: due, priority: "HIGH", created_reason: "承接差异项" };
const createResult = { action_item_id: action, project_id: project, source_kind: "ANALYSIS_ITEM", ...input,
  created_by: actor, created_at: now, initial_event_id: event, action_state: "OPEN", etag: '"v0"' };
const stateBase = { action_item_id: action, project_id: project, action_state_event_id: event };
function envelope(data: unknown, status = 200, etag = '"v1"', location?: string) { return new Response(JSON.stringify({ data, trace_id: actor }),
  { status, headers: { "Content-Type": "application/json", ETag: etag, ...(location ? { Location: location } : {}) } }); }
function failure(status: number, code: string) { return new Response(JSON.stringify({ error: { code, message: "private" }, trace_id: actor }),
  { status, headers: { "Content-Type": "application/json" } }); }
async function setup(...responses: Response[]) { const session = { user: { user_id: actor, username_display: "负责人" }, deployment_role: "NONE",
  password_change_required: false, authorized_projects: [{ project_id: project, name: "项目", role: "PROJECT_MANAGER" }],
  absolute_expires_at: "2030-01-01T12:00:00Z", idle_expires_at: "2030-01-01T11:00:00Z", csrf_token: "a".repeat(64) };
  const fetcher = vi.fn().mockResolvedValueOnce(envelope(session)); responses.forEach(value => fetcher.mockResolvedValueOnce(value));
  const identity = new SessionClient(fetcher as typeof fetch); await identity.login("manager", "synthetic-only");
  return { api: new HandoverActionWriteClient(identity), fetcher }; }

describe("HandoverActionWriteClient", () => {
  afterEach(() => vi.restoreAllMocks());

  it("creates with session-owned CSRF and returns a non-current first receipt", async () => {
    const location = `/api/v1/projects/${project}/handover-action-items/${action}`;
    const { api, fetcher } = await setup(envelope(createResult, 201, '"v0"', location));
    const result = await api.create(project, input, key);
    expect(result.first_result).toMatchObject({ action_item_id: action, action_state: "OPEN", etag: '"v0"' });
    expect(result.is_current_state_proof).toBe(false); expect(Object.isFrozen(result.first_result.requested_input_spec.fields[0])).toBe(true);
    expect(fetcher.mock.calls[1][0]).toBe(`/api/v1/projects/${project}/handover-action-items`);
    expect(fetcher.mock.calls[1][1]).toMatchObject({ method: "POST", headers: {
      "X-CSRF-Token": "a".repeat(64), "Idempotency-Key": key, "Content-Type": "application/json" } });
  });

  it("patches only from the supplied ETag and verifies the changed fields", async () => {
    const result = { action_item_id: action, project_id: project, title: "新标题", requested_input_spec: spec, owner_ref: actor,
      due_at: due, priority: "URGENT", action_state: "OPEN", updated_at: now, etag: '"v1"' };
    const { api, fetcher } = await setup(envelope(result));
    const receipt = await api.patch(project, action, '"v0"', { title: "新标题", priority: "URGENT" });
    expect(receipt.first_result.priority).toBe("URGENT"); expect(fetcher.mock.calls[1][1]).toMatchObject({ method: "PATCH",
      headers: { "If-Match": '"v0"', "X-CSRF-Token": "a".repeat(64) } });
    expect((fetcher.mock.calls[1][1] as RequestInit).headers).not.toHaveProperty("Idempotency-Key");
  });

  it("runs START, SUBMIT, VERIFY, CLOSE and CANCEL with exact Key/ETag bindings", async () => {
    const docs = [{ document_id: document, document_version_id: documentVersion }]; const refs = [evidence];
    const replies = [
      envelope({ ...stateBase, action_state: "IN_PROGRESS", etag: '"v1"', occurred_at: now }),
      envelope({ ...stateBase, action_state: "SUBMITTED", etag: '"v2"', submitted_at: now, response_documents: docs, evidence_refs: refs }, 200, '"v2"'),
      envelope({ ...stateBase, action_state: "VERIFIED", etag: '"v3"', verified_by: actor, verified_at: now, evidence_refs: refs }, 200, '"v3"'),
      envelope({ ...stateBase, action_state: "CLOSED", etag: '"v4"', resolution_trace_ref: traceTarget, closed_at: now }, 200, '"v4"'),
      envelope({ ...stateBase, action_state: "CANCELLED", etag: '"v1"', previous_state: "OPEN", reason: "取消重复项", occurred_at: now }),
    ];
    const { api, fetcher } = await setup(...replies);
    expect((await api.start(project, action, '"v0"', key, "开始处理")).first_result.action_state).toBe("IN_PROGRESS");
    expect((await api.submit(project, action, '"v1"', key, docs, refs, "已提交")).first_result.action_state).toBe("SUBMITTED");
    expect((await api.verify(project, action, '"v2"', key, refs, "证据有效")).first_result.action_state).toBe("VERIFIED");
    expect((await api.close(project, action, '"v3"', key, traceTarget, "已形成追溯")).first_result.action_state).toBe("CLOSED");
    expect((await api.cancel(project, action, '"v0"', key, "取消重复项")).first_result.previous_state).toBe("OPEN");
    expect(fetcher.mock.calls.slice(1).map(call => call[0])).toEqual(["start", "submit", "verify", "close", "cancel"].map(operation =>
      `/api/v1/projects/${project}/handover-action-items/${action}:${operation}`));
    expect(fetcher.mock.calls[4][1]).toMatchObject({ headers: { "If-Match": '"v3"', "Idempotency-Key": key } });
  });

  it.each([
    ["create", () => ({ ...input, human_source_reason: "冲突来源" })],
    ["create", () => ({ ...input, requested_input_spec: { fields: [] } })],
    ["patch", () => ({})],
  ])("rejects unsafe %s input before transport", async (kind, make) => {
    const { api, fetcher } = await setup();
    const promise = kind === "create" ? api.create(project, make() as CreateHandoverActionInput, key)
      : api.patch(project, action, '"v0"', make());
    await expect(promise).rejects.toMatchObject({ code: "HANDOVER_ACTION_INVALID_INPUT", uncertain: false });
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it("rejects missing evidence and invalid reason before transport", async () => {
    const { api, fetcher } = await setup();
    await expect(api.submit(project, action, '"v0"', key, [{ document_id: document, document_version_id: documentVersion }], [], "提交"))
      .rejects.toMatchObject({ code: "HANDOVER_ACTION_INVALID_INPUT" });
    await expect(api.start(project, action, '"v0"', key, "  ")).rejects.toMatchObject({ code: "HANDOVER_ACTION_INVALID_INPUT" });
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it.each([[401, "AUTH_SESSION_EXPIRED"], [403, "AUTH_CSRF_INVALID"], [403, "LICENSE_OPERATION_DENIED"], [404, "RESOURCE_NOT_FOUND"],
    [409, "PROJECT_ARCHIVED"], [409, "CONFLICT_VERSION"], [409, "CONFLICT_IDEMPOTENCY"], [409, "HANDOVER_ACTION_STATE_INVALID"],
    [422, "HANDOVER_SOURCE_REQUIRED"], [422, "HANDOVER_ACTION_EVIDENCE_REQUIRED"], [422, "HANDOVER_ACTION_RESOLUTION_REQUIRED"]] as const)(
    "maps known status/code %s %s", async (status, code) => {
      const caught = await (await setup(failure(status, code))).api.start(project, action, '"v0"', key, "开始").catch(error => error);
      expect(caught).toBeInstanceOf(HandoverActionWriteError); expect(caught).toMatchObject({ code, uncertain: false });
      expect(String(caught)).not.toContain("private");
    });

  it("maps malformed requests to invalid input and unknown or drifted receipts to uncertainty", async () => {
    await expect((await setup(failure(422, "VALIDATION_FAILED"))).api.start(project, action, '"v0"', key, "开始"))
      .rejects.toMatchObject({ code: "HANDOVER_ACTION_INVALID_INPUT", uncertain: false });
    const drifted = { ...stateBase, action_state: "IN_PROGRESS", etag: '"v2"', occurred_at: now };
    await expect((await setup(envelope(drifted, 200, '"v2"'))).api.start(project, action, '"v0"', key, "开始"))
      .rejects.toMatchObject({ code: "HANDOVER_ACTION_UNCERTAIN", uncertain: true });
    await expect((await setup(failure(503, "SYSTEM_UNAVAILABLE"))).api.start(project, action, '"v0"', key, "开始"))
      .rejects.toMatchObject({ code: "HANDOVER_ACTION_UNCERTAIN", uncertain: true });
  });

  it("never retries a transport failure", async () => {
    const { api, fetcher } = await setup();
    await expect(api.start(project, action, '"v0"', key, "开始")).rejects.toMatchObject({ code: "HANDOVER_ACTION_UNCERTAIN", uncertain: true });
    expect(fetcher).toHaveBeenCalledTimes(2);
  });
});
