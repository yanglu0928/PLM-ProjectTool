import { describe, expect, it, vi } from "vitest";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { HandoverCreateClient, HandoverCreateError, normalizeHandoverPurpose,
  normalizeHandoverSources } from "./handoverCreateClient";

const project = "01234567-89ab-4cde-8123-456789abcdef";
const document = "11234567-89ab-4cde-8123-456789abcdef";
const version = "21234567-89ab-4cde-8123-456789abcdef";
const analysis = "31234567-89ab-4cde-8123-456789abcdef";
const actor = "41234567-89ab-4cde-8123-456789abcdef";
const trace = "51234567-89ab-4cde-8123-456789abcdef";
const token = "a".repeat(64);
const path = `/api/v1/projects/${project}/handover-analyses`;
const input = { analysis_purpose: "交接差异分析", source_documents: [{ document_id: document,
  document_version_id: version }] };
function response(data: unknown, status = 200, headers: Record<string, string> = {}): Response {
  return new Response(JSON.stringify({ data, trace_id: trace }), { status,
    headers: { "Content-Type": "application/json", ...headers } });
}
function failure(status: number, code: string): Response {
  return new Response(JSON.stringify({ error: { code, message: "private" }, trace_id: trace }),
    { status, headers: { "Content-Type": "application/json" } });
}
function sessionData(role = "PROJECT_MANAGER") {
  return { user: { user_id: actor, username_display: "合成负责人" }, deployment_role: "NONE",
    password_change_required: false, authorized_projects: [{ project_id: project,
      name: "合成项目", role }], absolute_expires_at: "2030-01-01T12:00:00Z",
    idle_expires_at: "2030-01-01T11:00:00Z", csrf_token: token };
}
function created(overrides: Record<string, unknown> = {}) {
  return { handover_analysis_id: analysis, project_id: project, analysis_purpose: input.analysis_purpose,
    source_set_ref: `sha256:${"a".repeat(64)}`, state: "ACTIVE",
    current_approved_version_ref: null, created_at: "2026-10-24T12:00:00Z", etag: '"v0"', ...overrides };
}
async function fixture(result: Response | Error, role = "PROJECT_MANAGER") {
  const fetcher = vi.fn().mockResolvedValueOnce(response(sessionData(role)));
  if (result instanceof Error) fetcher.mockRejectedValueOnce(result);
  else fetcher.mockResolvedValueOnce(result);
  const session = new SessionClient(fetcher as typeof fetch);
  await session.login("synthetic", "synthetic-only");
  return { client: new HandoverCreateClient(session), fetcher };
}

describe("HandoverCreateClient", () => {
  it("posts exact fixed references with session CSRF/key and validates the first receipt", async () => {
    const { client, fetcher } = await fixture(response(created(), 201,
      { ETag: '"v0"', Location: `${path}/${analysis}` }));
    await expect(client.create(project, input, "handover-create-key-001"))
      .resolves.toMatchObject({ handover_analysis_id: analysis, state: "ACTIVE" });
    expect(fetcher.mock.calls[1]).toEqual([path, expect.objectContaining({
      method: "POST", credentials: "same-origin", cache: "no-store", redirect: "error",
      body: JSON.stringify(input), headers: { Accept: "application/json", "Content-Type": "application/json",
        "X-CSRF-Token": token, "Idempotency-Key": "handover-create-key-001" },
    })]);
  });

  it("normalizes purpose and sorts distinct sources, rejecting empty/duplicate/invalid refs", () => {
    expect(normalizeHandoverPurpose("  ＰＬＭ交接  ")).toBe("PLM交接");
    expect(normalizeHandoverSources([{ document_id: version, document_version_id: document },
      { document_id: document, document_version_id: version }])[0]?.document_version_id).toBe(document);
    expect(() => normalizeHandoverSources([])).toThrow(HandoverCreateError);
    expect(() => normalizeHandoverSources([input.source_documents[0], input.source_documents[0]])).toThrow(HandoverCreateError);
    expect(() => normalizeHandoverPurpose("\u0000")).toThrow(HandoverCreateError);
  });

  it("refuses a non-manager and malformed source before network mutation", async () => {
    const { client, fetcher } = await fixture(response(created(), 201,
      { ETag: '"v0"', Location: `${path}/${analysis}` }), "CUSTOMER_MEMBER");
    await expect(client.create(project, input, "handover-create-key-001"))
      .rejects.toMatchObject({ code: "RESOURCE_NOT_FOUND" });
    await expect(client.create(project, { ...input, source_documents: [] }, "handover-create-key-001"))
      .rejects.toMatchObject({ code: "HANDOVER_CREATE_INVALID" });
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it("maps a revoked source and distinguishes an uncertain transport result", async () => {
    const denied = await fixture(failure(422, "HANDOVER_SOURCE_REQUIRED"));
    await expect(denied.client.create(project, input, "handover-create-key-001"))
      .rejects.toMatchObject({ code: "HANDOVER_SOURCE_REQUIRED", uncertain: false });
    const timedOut = await fixture(new Error("private transport"));
    await expect(timedOut.client.create(project, input, "handover-create-key-001"))
      .rejects.toMatchObject({ code: "HANDOVER_CREATE_UNCERTAIN", uncertain: true });
  });

  it("fails closed on a mismatched Location or body even when HTTP says 201", async () => {
    const badLocation = await fixture(response(created(), 201,
      { ETag: '"v0"', Location: `${path}/${actor}` }));
    await expect(badLocation.client.create(project, input, "handover-create-key-001"))
      .rejects.toMatchObject({ code: "HANDOVER_CREATE_UNCERTAIN" });
    const badBody = await fixture(response(created({ project_id: actor }), 201,
      { ETag: '"v0"', Location: `${path}/${analysis}` }));
    await expect(badBody.client.create(project, input, "handover-create-key-001"))
      .rejects.toMatchObject({ code: "HANDOVER_CREATE_UNCERTAIN" });
  });
});
