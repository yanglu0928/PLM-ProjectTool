import { describe, expect, it, vi } from "vitest";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { EvidenceEligibilityOperationLookupClient } from "./evidenceEligibilityOperationLookupClient";

const projectId = "01234567-89ab-4cde-8123-456789abcdef";
const evidenceId = "11234567-89ab-4cde-8123-456789abcdef";
const actorId = "21234567-89ab-4cde-8123-456789abcdef";
const traceId = "31234567-89ab-4cde-8123-456789abcdef";
const key = "original-key-0001";
function response(data: unknown, status = 200): Response {
  return new Response(JSON.stringify({ data, trace_id: traceId }), { status,
    headers: { "Content-Type": "application/json", "Cache-Control": "no-store" } });
}
function error(status: number, code: string): Response {
  return new Response(JSON.stringify({ error: { code }, trace_id: traceId }), { status,
    headers: { "Content-Type": "application/json", "Cache-Control": "no-store" } });
}
function sessionView(role = "PROJECT_MANAGER"): Response {
  return response({ user: { user_id: actorId, username_display: "复核员" },
    deployment_role: "NONE", password_change_required: false,
    authorized_projects: [{ project_id: projectId, name: "演示", role }],
    absolute_expires_at: "2030-01-01T12:00:00Z", idle_expires_at: "2030-01-01T11:00:00Z",
    csrf_token: "a".repeat(64) });
}
async function auth(fetcher: typeof fetch): Promise<SessionClient> {
  const session = new SessionClient(fetcher);
  await session.login("reviewer", "synthetic-only");
  return session;
}

describe("EvidenceEligibilityOperationLookupClient", () => {
  it("uses current Session/CSRF and body-only original key; completed is not current state", async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(sessionView("CUSTOMER_MANAGER"))
      .mockResolvedValueOnce(response({ status: "COMPLETED", evidence_id: evidenceId,
        first_status_code: 200 }));
    const client = new EvidenceEligibilityOperationLookupClient(await auth(fetcher as typeof fetch));
    expect(await client.lookup(projectId, evidenceId, key)).toEqual({ status: "COMPLETED",
      evidence_id: evidenceId, first_status_code: 200, is_current_state_proof: false });
    const [url, options] = fetcher.mock.calls[1] as [string, RequestInit];
    expect(url).toBe(`/api/v1/projects/${projectId}/evidence/${evidenceId}:lookup-eligibility-operation`);
    expect(url).not.toContain(key);
    expect(options).toEqual(expect.objectContaining({ method: "POST", credentials: "same-origin",
      cache: "no-store", redirect: "error", body: JSON.stringify({ operation_key: key }),
      headers: { Accept: "application/json", "Content-Type": "application/json",
        "X-CSRF-Token": "a".repeat(64) } }));
  });

  it("keeps unknown distinct from failure and does not resend", async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(sessionView())
      .mockResolvedValueOnce(response({ status: "UNCONFIRMED" }));
    const client = new EvidenceEligibilityOperationLookupClient(await auth(fetcher as typeof fetch));
    expect(await client.lookup(projectId, evidenceId, key)).toEqual({
      status: "UNCONFIRMED", is_current_state_proof: false });
    expect(fetcher).toHaveBeenCalledTimes(2);
  });

  it("rejects viewer role and invalid key before transport", async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(sessionView("CUSTOMER_MEMBER"));
    const client = new EvidenceEligibilityOperationLookupClient(await auth(fetcher as typeof fetch));
    await expect(client.lookup(projectId, evidenceId, key)).rejects.toMatchObject({
      code: "EVIDENCE_LOOKUP_DENIED" });
    expect(fetcher).toHaveBeenCalledTimes(1);
    const managerFetcher = vi.fn().mockResolvedValueOnce(sessionView());
    const manager = new EvidenceEligibilityOperationLookupClient(await auth(managerFetcher as typeof fetch));
    await expect(manager.lookup(projectId, evidenceId, "short")).rejects.toMatchObject({
      code: "EVIDENCE_LOOKUP_INVALID" });
    expect(managerFetcher).toHaveBeenCalledTimes(1);
  });

  it("fails closed on mismatched receipt, malformed envelope and transport failure", async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(sessionView())
      .mockResolvedValueOnce(response({ status: "COMPLETED", evidence_id: projectId,
        first_status_code: 200 }))
      .mockResolvedValueOnce(response({ status: "UNCONFIRMED", unexpected: true }))
      .mockRejectedValueOnce(new TypeError("network gone"));
    const client = new EvidenceEligibilityOperationLookupClient(await auth(fetcher as typeof fetch));
    for (let index = 0; index < 3; index += 1) {
      await expect(client.lookup(projectId, evidenceId, key)).rejects.toMatchObject({
        code: "EVIDENCE_LOOKUP_UNAVAILABLE" });
    }
    expect(fetcher).toHaveBeenCalledTimes(4);
  });

  it("maps known denial and keeps unknown server failures uncertain", async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(sessionView())
      .mockResolvedValueOnce(error(404, "RESOURCE_NOT_FOUND"))
      .mockResolvedValueOnce(error(503, "SYSTEM_UNAVAILABLE"));
    const client = new EvidenceEligibilityOperationLookupClient(await auth(fetcher as typeof fetch));
    await expect(client.lookup(projectId, evidenceId, key)).rejects.toMatchObject({
      code: "EVIDENCE_LOOKUP_DENIED" });
    await expect(client.lookup(projectId, evidenceId, key)).rejects.toMatchObject({
      code: "EVIDENCE_LOOKUP_UNAVAILABLE" });
  });
});
