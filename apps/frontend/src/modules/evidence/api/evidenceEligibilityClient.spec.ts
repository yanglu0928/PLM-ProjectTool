import { describe, expect, it, vi } from "vitest";

import { SessionClient } from "@/modules/auth/api/sessionClient";
import type { EvidenceViewerDescriptor } from "./evidenceViewerClient";
import { EvidenceEligibilityClient, EvidenceEligibilityClientError } from "./evidenceEligibilityClient";

const projectId = "01234567-89ab-4cde-8123-456789abcdef";
const evidenceId = "11234567-89ab-4cde-8123-456789abcdef";
const documentId = "21234567-89ab-4cde-8123-456789abcdef";
const versionId = "31234567-89ab-4cde-8123-456789abcdef";
const traceId = "41234567-89ab-4cde-8123-456789abcdef";
const viewer = { evidence_id: evidenceId, document_id: documentId,
  document_version_id: versionId, document_version_no: 1,
  detected_mime: "application/pdf", size_bytes: 10,
  locator: { locator_type: "DOCUMENT" }, precision: "DOCUMENT",
  display_label: "全文", short_preview: null,
  content_url: `/api/v1/projects/${projectId}/documents/${documentId}/versions/${versionId}/content`,
} as EvidenceViewerDescriptor;
const current = { evidence_id: evidenceId, document_id: documentId,
  document_version_id: versionId, eligibility_state: "CANDIDATE" as const,
  etag: '"v0"' };
function response(data: unknown, etag?: string): Response {
  return new Response(JSON.stringify({ data, trace_id: traceId }), { status: 200,
    headers: { "Content-Type": "application/json", ...(etag ? { ETag: etag } : {}) } });
}
function error(status: number, code: string): Response {
  return new Response(JSON.stringify({ error: { code }, trace_id: traceId }),
    { status, headers: { "Content-Type": "application/json" } });
}
async function auth(fetcher: typeof fetch): Promise<SessionClient> {
  const session = new SessionClient(fetcher);
  await session.login("reviewer", "synthetic-only");
  return session;
}
const sessionView = () => response({ user: { user_id: projectId, username_display: "复核员" },
  deployment_role: "NONE", password_change_required: false,
  authorized_projects: [{ project_id: projectId, name: "演示", role: "PROJECT_MANAGER" }],
  absolute_expires_at: "2030-01-01T12:00:00Z", idle_expires_at: "2030-01-01T11:00:00Z",
  csrf_token: "a".repeat(64),
});
const globalSessionView = () => response({ user: { user_id: projectId, username_display: "全局管理员" },
  deployment_role: "DEPLOYMENT_ADMIN", password_change_required: false,
  authorized_projects: [], absolute_expires_at: "2030-01-01T12:00:00Z",
  idle_expires_at: "2030-01-01T11:00:00Z", csrf_token: "a".repeat(64),
});

describe("EvidenceEligibilityClient", () => {
  it("reads global current Evidence only for a deployment admin with strong ETag", async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(globalSessionView())
      .mockResolvedValueOnce(response({ ...current, eligibility_state: "REVOKED",
        etag: '"v2"' }, '"v2"'));
    const client = new EvidenceEligibilityClient(await auth(fetcher as typeof fetch),
      fetcher as typeof fetch);
    expect(await client.currentGlobal(evidenceId)).toEqual({ ...current,
      eligibility_state: "REVOKED", etag: '"v2"' });
    expect(fetcher.mock.calls[1]?.[0]).toBe(`/api/v1/global/evidence/${evidenceId}`);
    expect(fetcher.mock.calls[1]?.[1]).toEqual(expect.objectContaining({
      method: "GET", credentials: "same-origin", cache: "no-store", redirect: "error" }));
  });

  it("refuses the global path for a project-only identity and mismatched ETag", async () => {
    const projectFetcher = vi.fn().mockResolvedValueOnce(sessionView());
    const projectClient = new EvidenceEligibilityClient(await auth(projectFetcher as typeof fetch),
      projectFetcher as typeof fetch);
    await expect(projectClient.currentGlobal(evidenceId)).rejects.toMatchObject({
      code: "EVIDENCE_ELIGIBILITY_INVALID" });
    expect(projectFetcher).toHaveBeenCalledTimes(1);

    const globalFetcher = vi.fn().mockResolvedValueOnce(globalSessionView())
      .mockResolvedValueOnce(response(current, '"v1"'));
    const globalClient = new EvidenceEligibilityClient(await auth(globalFetcher as typeof fetch),
      globalFetcher as typeof fetch);
    await expect(globalClient.currentGlobal(evidenceId)).rejects.toMatchObject({
      code: "EVIDENCE_ELIGIBILITY_UNCERTAIN" });
  });
  it("fetches current strong ETag and sends one bounded human decision", async () => {
    const post = response({ evidence_id: evidenceId, eligibility_state: "ELIGIBLE",
      eligibility_reason: "人工核对实际调研记录", etag: '"v1"' }, '"v1"');
    const fetcher = vi.fn().mockResolvedValueOnce(sessionView())
      .mockResolvedValueOnce(response(current, '"v0"')).mockResolvedValueOnce(post);
    const session = await auth(fetcher as typeof fetch);
    const client = new EvidenceEligibilityClient(session, fetcher as typeof fetch);
    const before = await client.current(projectId, evidenceId);
    const result = await client.set(projectId, before, viewer,
      "ELIGIBLE", "人工核对实际调研记录", "k".repeat(16));
    expect(result.is_current_state_proof).toBe(false);
    expect(result.etag).toBe('"v1"');
    expect(fetcher.mock.calls[1]?.[0]).toBe(`/api/v1/projects/${projectId}/evidence/${evidenceId}`);
    expect(fetcher.mock.calls[2]?.[0]).toBe(
      `/api/v1/projects/${projectId}/evidence/${evidenceId}:set-eligibility`);
    expect(fetcher.mock.calls[2]?.[1]).toEqual(expect.objectContaining({
      method: "POST", credentials: "same-origin", redirect: "error",
      headers: expect.objectContaining({ "If-Match": '"v0"', "Idempotency-Key": "k".repeat(16),
        "X-CSRF-Token": "a".repeat(64) }),
    }));
  });

  it("rejects mismatched fixed source and malformed current ETag before POST", async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(sessionView())
      .mockResolvedValueOnce(response(current, '"v2"'));
    const session = await auth(fetcher as typeof fetch);
    const client = new EvidenceEligibilityClient(session, fetcher as typeof fetch);
    await expect(client.current(projectId, evidenceId)).rejects.toMatchObject({
      code: "EVIDENCE_ELIGIBILITY_UNCERTAIN" });
    expect(fetcher).toHaveBeenCalledTimes(2);
    await expect(client.set(projectId, current, { ...viewer, document_version_id: projectId },
      "ELIGIBLE", "已核对", "k".repeat(16))).rejects.toMatchObject({
      code: "EVIDENCE_ELIGIBILITY_INVALID" });
    expect(fetcher).toHaveBeenCalledTimes(2);
  });

  it("maps version conflict and retains uncertainty on transport failure", async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(sessionView())
      .mockResolvedValueOnce(error(409, "CONFLICT_VERSION"));
    const session = await auth(fetcher as typeof fetch);
    const client = new EvidenceEligibilityClient(session, fetcher as typeof fetch);
    await expect(client.set(projectId, current, viewer, "ELIGIBLE", "已核对",
      "k".repeat(16))).rejects.toMatchObject({ code: "CONFLICT_VERSION" });
    fetcher.mockRejectedValueOnce(new TypeError("network lost"));
    await expect(client.set(projectId, current, viewer, "ELIGIBLE", "已核对",
      "k".repeat(16))).rejects.toMatchObject({ code: "EVIDENCE_ELIGIBILITY_UNCERTAIN" });
    expect(fetcher).toHaveBeenCalledTimes(3);
  });

  it("rejects terminal state, blank reason and invalid key locally", async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(sessionView());
    const client = new EvidenceEligibilityClient(await auth(fetcher as typeof fetch),
      fetcher as typeof fetch);
    for (const [before, reason, key] of [
      [{ ...current, eligibility_state: "ELIGIBLE" }, "已核对", "k".repeat(16)],
      [current, "  ", "k".repeat(16)],
      [current, "已核对", "short"],
    ] as const) {
      await expect(client.set(projectId, before as typeof current, viewer,
        "ELIGIBLE", reason, key)).rejects.toBeInstanceOf(EvidenceEligibilityClientError);
    }
    expect(fetcher).toHaveBeenCalledTimes(1);
  });
});
