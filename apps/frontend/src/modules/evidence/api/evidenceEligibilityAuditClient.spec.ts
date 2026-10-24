import { describe, expect, it, vi } from "vitest";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { EvidenceEligibilityAuditClient, EvidenceEligibilityAuditError } from "./evidenceEligibilityAuditClient";

const projectId = "01234567-89ab-4cde-8123-456789abcdef";
const evidenceId = "11234567-89ab-4cde-8123-456789abcdef";
const actorId = "21234567-89ab-4cde-8123-456789abcdef";
const auditId = "31234567-89ab-4cde-8123-456789abcdef";
const traceId = "41234567-89ab-4cde-8123-456789abcdef";
const cursor = "eyJ2IjoxfQ." + "a".repeat(43);
const event = { audit_event_id: auditId, occurred_at: "2026-10-01T04:00:00Z",
  event_scope: "PROJECT", project_id: projectId,
  actor: { type: "USER", user_id: actorId, original_user_id: null },
  action: "EVIDENCE_ELIGIBILITY_SET", outcome: "SUCCESS",
  target: { owner_module: "evidence", object_type: "EVD-01", object_id: evidenceId,
    version_id: null },
  summary: { reason_code: null, before_state: "CANDIDATE", after_state: "ELIGIBLE" },
  trace_id: traceId };
function response(data: unknown, status = 200): Response {
  return new Response(JSON.stringify({ data, trace_id: traceId }), { status,
    headers: { "Content-Type": "application/json" } });
}
async function session(role = "PROJECT_MANAGER"): Promise<SessionClient> {
  const client = new SessionClient(vi.fn().mockResolvedValue(response({
    user: { user_id: actorId, username_display: "合成用户" }, deployment_role: "NONE",
    password_change_required: false,
    authorized_projects: [{ project_id: projectId, name: "演示项目", role }],
    absolute_expires_at: "2030-01-01T12:00:00Z", idle_expires_at: "2030-01-01T11:00:00Z",
    csrf_token: "a".repeat(64),
  })) as typeof fetch);
  await client.login("user", "synthetic-only");
  return client;
}

describe("EvidenceEligibilityAuditClient", () => {
  it("reads only current PM's project/evidence success audit without treating it as key proof", async () => {
    const fetcher = vi.fn().mockResolvedValue(response({ items: [event],
      next_cursor: null, has_more: false }));
    const client = new EvidenceEligibilityAuditClient(await session(), fetcher as typeof fetch);
    const page = await client.list(projectId, evidenceId);
    expect(fetcher).toHaveBeenCalledOnce();
    const url = new URL(fetcher.mock.calls[0]![0], "http://localhost");
    expect(url.pathname).toBe(`/api/v1/projects/${projectId}/audit-events`);
    expect(Object.fromEntries(url.searchParams)).toEqual({ page_size: "50",
      action: "EVIDENCE_ELIGIBILITY_SET", outcome: "SUCCESS", actor_id: actorId,
      target_object_type: "EVD-01", target_object_id: evidenceId });
    expect(fetcher.mock.calls[0]![1]).toMatchObject({ method: "GET", credentials: "same-origin",
      cache: "no-store", redirect: "error" });
    expect(page.items).toEqual([{ audit_event_id: auditId, occurred_at: event.occurred_at,
      trace_id: traceId, after_state: "ELIGIBLE" }]);
    expect(page.items[0]).not.toHaveProperty("operation_key");
  });

  it("keeps signed pagination and never interprets an empty page as operation failure", async () => {
    const fetcher = vi.fn().mockResolvedValue(response({ items: [], next_cursor: null,
      has_more: false }));
    const client = new EvidenceEligibilityAuditClient(await session(), fetcher as typeof fetch);
    const page = await client.list(projectId, evidenceId, cursor);
    expect(new URL(fetcher.mock.calls[0]![0], "http://localhost").searchParams.get("cursor"))
      .toBe(cursor);
    expect(page).toEqual({ items: [], next_cursor: null, has_more: false });
    await expect(client.list(projectId, evidenceId, "bad cursor"))
      .rejects.toMatchObject({ code: "EVIDENCE_AUDIT_INVALID" });
  });

  it("denies CustomerManager locally and rejects cross-scope or mismatched audit rows", async () => {
    const fetcher = vi.fn().mockResolvedValue(response({ items: [event],
      next_cursor: null, has_more: false }));
    await expect(new EvidenceEligibilityAuditClient(await session("CUSTOMER_MANAGER"),
      fetcher as typeof fetch).list(projectId, evidenceId))
      .rejects.toMatchObject({ code: "EVIDENCE_AUDIT_DENIED" });
    expect(fetcher).not.toHaveBeenCalled();
    fetcher.mockResolvedValue(response({ items: [{ ...event, project_id: actorId }],
      next_cursor: null, has_more: false }));
    await expect(new EvidenceEligibilityAuditClient(await session(),
      fetcher as typeof fetch).list(projectId, evidenceId))
      .rejects.toBeInstanceOf(EvidenceEligibilityAuditError);
    fetcher.mockResolvedValue(response({ items: [{ ...event,
      target: { ...event.target, object_id: actorId } }], next_cursor: null, has_more: false }));
    await expect(new EvidenceEligibilityAuditClient(await session(),
      fetcher as typeof fetch).list(projectId, evidenceId))
      .rejects.toMatchObject({ code: "EVIDENCE_AUDIT_UNAVAILABLE" });
  });

  it("fails closed on malformed response and permission errors", async () => {
    const fetcher = vi.fn().mockResolvedValue(response({ items: [event, event],
      next_cursor: null, has_more: false }));
    const client = new EvidenceEligibilityAuditClient(await session(), fetcher as typeof fetch);
    await expect(client.list(projectId, evidenceId))
      .rejects.toMatchObject({ code: "EVIDENCE_AUDIT_UNAVAILABLE" });
    fetcher.mockResolvedValue(new Response(JSON.stringify({ error: { code: "RESOURCE_NOT_FOUND" },
      trace_id: traceId }), { status: 404, headers: { "Content-Type": "application/json" } }));
    await expect(client.list(projectId, evidenceId))
      .rejects.toMatchObject({ code: "EVIDENCE_AUDIT_DENIED" });
  });
});
