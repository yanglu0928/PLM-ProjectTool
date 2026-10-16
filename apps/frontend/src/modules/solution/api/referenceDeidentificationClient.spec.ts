import { describe, expect, it, vi } from "vitest";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { ReferenceDeidentificationClient, type DeidentificationSources } from "./referenceDeidentificationClient";

const actor = "01234567-89ab-4cde-8123-456789abcdef";
const document = "11234567-89ab-4cde-8123-456789abcdef";
const version = "21234567-89ab-4cde-8123-456789abcdef";
const evidence = "31234567-89ab-4cde-8123-456789abcdef";
const confirmation = "41234567-89ab-4cde-8123-456789abcdef";
const trace = "51234567-89ab-4cde-8123-456789abcdef";
const source: DeidentificationSources = { document_version_ids: [version], evidence_ids: [evidence],
  source_project_class: "PLM", deidentification_class: "HUMAN_REVIEWED",
  applicability: { industry: "synthetic" } };
const fingerprint = "f".repeat(64);
const expiry = new Date(Date.now() + 86_400_000).toISOString().replace(".000Z", "Z");
function envelope(data: unknown, status = 200): Response {
  return new Response(JSON.stringify({ data, trace_id: trace }), { status,
    headers: { "Content-Type": "application/json" } });
}
function failure(code: string, status: number): Response {
  return new Response(JSON.stringify({ error: { code }, trace_id: trace }), { status,
    headers: { "Content-Type": "application/json" } });
}
function sessionResponse(role: "NONE" | "DEPLOYMENT_ADMIN" = "DEPLOYMENT_ADMIN"): Response {
  return envelope({ user: { user_id: actor, username_display: "合成管理员" },
    deployment_role: role, password_change_required: false, authorized_projects: [],
    absolute_expires_at: "2030-01-11T00:00:00Z", idle_expires_at: "2030-01-10T01:00:00Z",
    csrf_token: "a".repeat(64) });
}
async function setup(...responses: Response[]) {
  const fetcher = vi.fn().mockResolvedValueOnce(sessionResponse());
  for (const response of responses) fetcher.mockResolvedValueOnce(response);
  const session = new SessionClient(fetcher as typeof fetch);
  await session.login("admin", "synthetic-only");
  return { client: new ReferenceDeidentificationClient(session), fetcher };
}
const preview = { source_fingerprint: fingerprint,
  document_refs: [{ document_id: document, document_version_id: version }],
  evidence_ids: [evidence], previewed_at: "2026-10-09T00:00:00Z" };

describe("ReferenceDeidentificationClient", () => {
  it("uses the browser fetch with no class receiver for preview", async () => {
    let calls = 0;
    const nativeLike = function (this: unknown): Promise<Response> {
      expect(this).toBeUndefined();
      calls += 1;
      return Promise.resolve(calls === 1 ? sessionResponse() : envelope(preview));
    } as typeof fetch;
    const authenticated = new SessionClient(nativeLike);
    await authenticated.login("admin", "synthetic-only");
    expect(await new ReferenceDeidentificationClient(authenticated).preview(source)).toEqual(preview);
    expect(calls).toBe(2);
  });
  it("previews fixed identities via CSRF but no idempotency key", async () => {
    const { client, fetcher } = await setup(envelope(preview));
    expect(await client.preview(source)).toEqual(preview);
    const [path, options] = fetcher.mock.calls[1] as [string, RequestInit];
    expect(path).toBe("/api/v1/global/reference-deidentification-confirmations:preview");
    expect(options).toEqual(expect.objectContaining({ method: "POST", credentials: "same-origin",
      cache: "no-store", redirect: "error", headers: expect.objectContaining({
        "X-CSRF-Token": "a".repeat(64), "Content-Type": "application/json" }) }));
    expect(options.headers).not.toHaveProperty("Idempotency-Key");
  });

  it("posts an explicit statement with preview fingerprint and preserves operation key", async () => {
    const receipt = { confirmation_id: confirmation, source_fingerprint: fingerprint,
      confirmed_by: actor, confirmed_at: "2026-10-09T00:00:00Z", expires_at: expiry,
      trace_id: trace };
    const { client, fetcher } = await setup(envelope(receipt, 201),
      envelope({ confirmation_id: confirmation, revoked_at: "2026-10-09T00:01:00Z", trace_id: trace }));
    expect(await client.confirm(source, fingerprint, expiry, "k".repeat(16))).toEqual(receipt);
    const [path, options] = fetcher.mock.calls[1] as [string, RequestInit];
    expect(path).toBe("/api/v1/global/reference-deidentification-confirmations");
    expect(options.headers).toEqual(expect.objectContaining({ "Idempotency-Key": "k".repeat(16),
      "X-CSRF-Token": "a".repeat(64) }));
    expect(JSON.parse(options.body as string)).toEqual({ ...source,
      expected_source_fingerprint: fingerprint,
      attestation_statement: "I_VERIFIED_DEIDENTIFICATION", expires_at: expiry });
    expect(await client.revoke(confirmation, "ADMIN_REVIEW", "r".repeat(16))).toEqual({
      confirmation_id: confirmation, revoked_at: "2026-10-09T00:01:00Z", trace_id: trace });
    expect(fetcher.mock.calls[2]![0]).toBe(
      `/api/v1/global/reference-deidentification-confirmations/${confirmation}:revoke`);
  });

  it("accepts the same expiry instant serialized at PostgreSQL microsecond precision", async () => {
    const microsecondExpiry = expiry.replace(/\.(\d{3})Z$/, ".$1000Z");
    const receipt = { confirmation_id: confirmation, source_fingerprint: fingerprint,
      confirmed_by: actor, confirmed_at: "2026-10-09T00:00:00.123456Z",
      expires_at: microsecondExpiry, trace_id: trace };
    const { client } = await setup(envelope(receipt, 201));
    expect(await client.confirm(source, fingerprint, expiry, "k".repeat(16)))
      .toEqual(receipt);
  });

  it("rejects mismatched preview, drift and ambiguous write without retry", async () => {
    const mismatch = await setup(envelope({ ...preview,
      document_refs: [{ document_id: document, document_version_id: actor }] }));
    await expect(mismatch.client.preview(source)).rejects.toMatchObject({ code: "DEIDENTIFICATION_UNCERTAIN" });
    const drift = await setup(failure("SOURCE_SNAPSHOT_CHANGED", 409));
    await expect(drift.client.confirm(source, fingerprint, expiry, "k".repeat(16)))
      .rejects.toMatchObject({ code: "SOURCE_SNAPSHOT_CHANGED" });
    const network = await setup();
    network.fetcher.mockRejectedValueOnce(new TypeError("network lost"));
    await expect(network.client.confirm(source, fingerprint, expiry, "k".repeat(16)))
      .rejects.toMatchObject({ code: "DEIDENTIFICATION_UNCERTAIN" });
    expect(network.fetcher).toHaveBeenCalledTimes(2);
  });

  it("denies malformed source or non-admin before POST", async () => {
    const { client, fetcher } = await setup();
    await expect(client.preview({ ...source, document_version_ids: [] }))
      .rejects.toMatchObject({ code: "DEIDENTIFICATION_INVALID" });
    expect(fetcher).toHaveBeenCalledTimes(1);
    const projectFetcher = vi.fn().mockResolvedValueOnce(sessionResponse("NONE"));
    const projectSession = new SessionClient(projectFetcher as typeof fetch);
    await projectSession.login("reviewer", "synthetic-only");
    await expect(new ReferenceDeidentificationClient(projectSession).preview(source))
      .rejects.toMatchObject({ code: "DEIDENTIFICATION_INVALID" });
    expect(projectFetcher).toHaveBeenCalledTimes(1);
  });

  it("recovers only a same-kind completed operation and treats missing receipt as inconclusive", async () => {
    const { client, fetcher } = await setup(envelope({ status: "UNCONFIRMED" }),
      envelope({ status: "COMPLETED", confirmation_id: confirmation,
        first_status_code: 201, current_state: "REVOKED" }));
    expect(await client.lookup("CONFIRM", "k".repeat(16))).toEqual({ status: "UNCONFIRMED" });
    expect(await client.lookup("CONFIRM", "k".repeat(16))).toEqual({ status: "COMPLETED",
      confirmation_id: confirmation, first_status_code: 201, current_state: "REVOKED" });
    expect(fetcher.mock.calls[1]![0]).toBe(
      "/api/v1/global/reference-deidentification-confirmations:lookup-operation");
    expect((fetcher.mock.calls[1]![1] as RequestInit).headers).not.toHaveProperty("Idempotency-Key");
    const wrong = await setup(envelope({ status: "COMPLETED", confirmation_id: confirmation,
      first_status_code: 200, current_state: "REVOKED" }));
    await expect(wrong.client.lookup("CONFIRM", "k".repeat(16)))
      .rejects.toMatchObject({ code: "DEIDENTIFICATION_UNCERTAIN" });
  });
});
