import { afterEach, describe, expect, it, vi } from "vitest";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { CapabilityVersionCreateClient } from "./capabilityVersionCreateClient";

const actor = "01234567-89ab-4cde-8123-456789abcdef";
const baseline = "11234567-89ab-4cde-8123-456789abcdef";
const version = "21234567-89ab-4cde-8123-456789abcdef";
const itemId = "31234567-89ab-4cde-8123-456789abcdef";
const documentId = "41234567-89ab-4cde-8123-456789abcdef";
const documentVersionId = "51234567-89ab-4cde-8123-456789abcdef";
const evidenceId = "61234567-89ab-4cde-8123-456789abcdef";
const key = "synthetic-cap-version-001";
const item = { stable_item_id: itemId, capability_code: "PLM.CORE.ITEM", domain_name: "PLM",
  module_name: "Core", feature_name: "Identity", name: "Identity", description: "Synthetic",
  boundary: "Synthetic only", prerequisites: ["CONFIGURED"], interface_refs: ["IF-01"],
  document_refs: [{ document_id: documentId, document_version_id: documentVersionId }],
  evidence_refs: [evidenceId], item_state: "AVAILABLE" as const };
const receipt = { baseline_version_id: version, baseline_id: baseline, version_no: 1,
  state: "DRAFT", source_collection_ref: `sha256:${"a".repeat(64)}`,
  content_fingerprint: "b".repeat(64), supersedes_version_ref: null,
  created_at: "2026-10-24T01:00:00Z", baseline_etag: '"v1"' };
function response(data: unknown, status = 201, headers: Record<string, string> = {}): Response {
  return new Response(JSON.stringify({ data, trace_id: actor }), { status, headers: {
    "Content-Type": "application/json", "Cache-Control": "no-store", ETag: '"v1"',
    Location: `/api/v1/global/capability-baselines/${baseline}/versions/${version}`, ...headers } });
}
function auth(admin: boolean): Response { return response({
  user: { user_id: actor, username_display: "合成用户" },
  deployment_role: admin ? "DEPLOYMENT_ADMIN" : "NONE", password_change_required: false,
  authorized_projects: admin ? [] : [{ project_id: baseline, name: "合成项目", role: "PROJECT_MANAGER" }],
  absolute_expires_at: "2030-01-01T12:00:00Z", idle_expires_at: "2030-01-01T11:00:00Z",
  csrf_token: "a".repeat(64) }, 200); }
function harness(admin: boolean, ...results: Response[]) {
  const fetcher = vi.fn(); [auth(admin), ...results].forEach(result => fetcher.mockResolvedValueOnce(result));
  const session = new SessionClient(fetcher as typeof fetch);
  return { session, client: new CapabilityVersionCreateClient(session), fetcher };
}
describe("CapabilityVersionCreateClient", () => {
  afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });
  it("posts exact DRAFT items with private CSRF, baseline If-Match and original idempotency key", async () => {
    const { session, client, fetcher } = harness(true, response(receipt));
    await session.login("synthetic", "synthetic-only");
    await expect(client.create(baseline, '"v0"', [item], key)).resolves.toEqual(receipt);
    const [path, options] = fetcher.mock.calls[1];
    expect(path).toBe(`/api/v1/global/capability-baselines/${baseline}/versions`);
    expect(options.headers["X-CSRF-Token"]).toBe("a".repeat(64));
    expect(options.headers["If-Match"]).toBe('"v0"');
    expect(options.headers["Idempotency-Key"]).toBe(key);
    expect(JSON.parse(options.body)).toEqual({ items: [item] });
  });
  it("rejects missing, duplicate and malformed references before the command", async () => {
    const { session, client, fetcher } = harness(true);
    await session.login("synthetic", "synthetic-only");
    await expect(client.create(baseline, '"v0"', [], key)).rejects.toMatchObject({ code: "CAP_VERSION_INVALID" });
    await expect(client.create(baseline, '"v0"', [{ ...item, evidence_refs: [] }], key))
      .rejects.toMatchObject({ code: "CAP_VERSION_INVALID" });
    await expect(client.create(baseline, '"v0"', [item, item], key))
      .rejects.toMatchObject({ code: "CAP_VERSION_INVALID" });
    await expect(client.create(baseline, '"v01"', [item], key))
      .rejects.toMatchObject({ code: "CAP_VERSION_INVALID" });
    await expect(client.create(baseline, '"v0"', [item], "short"))
      .rejects.toMatchObject({ code: "CAP_VERSION_INVALID" });
    expect(fetcher).toHaveBeenCalledTimes(1);
  });
  it("blocks a project member from the GLOBAL write", async () => {
    const { session, client, fetcher } = harness(false);
    await session.login("synthetic", "synthetic-only");
    await expect(client.create(baseline, '"v0"', [item], key))
      .rejects.toMatchObject({ code: "RESOURCE_NOT_FOUND" });
    expect(fetcher).toHaveBeenCalledTimes(1);
  });
  it("maps known source qualification and version conflicts", async () => {
    for (const [code, status] of [["CAPABILITY_EVIDENCE_REQUIRED", 422], ["CONFLICT_VERSION", 409]] as const) {
      const denied = new Response(JSON.stringify({ error: { code }, trace_id: actor }), { status,
        headers: { "Content-Type": "application/json" } });
      const { session, client } = harness(true, denied);
      await session.login("synthetic", "synthetic-only");
      await expect(client.create(baseline, '"v0"', [item], key)).rejects.toMatchObject({ code });
    }
  });
  it("treats receipt mismatch and lost response as uncertain, never rotating the key", async () => {
    const wrong = harness(true, response({ ...receipt, state: "APPROVED" }));
    await wrong.session.login("synthetic", "synthetic-only");
    await expect(wrong.client.create(baseline, '"v0"', [item], key))
      .rejects.toMatchObject({ code: "CAP_VERSION_UNCERTAIN", uncertain: true });
    const wrongEtag = harness(true, response(receipt, 201, { ETag: '"v2"' }));
    await wrongEtag.session.login("synthetic", "synthetic-only");
    await expect(wrongEtag.client.create(baseline, '"v0"', [item], key))
      .rejects.toMatchObject({ code: "CAP_VERSION_UNCERTAIN" });
    const lost = harness(true); await lost.session.login("synthetic", "synthetic-only");
    await expect(lost.client.create(baseline, '"v0"', [item], key))
      .rejects.toMatchObject({ code: "CAP_VERSION_UNCERTAIN" });
    expect(lost.fetcher.mock.calls[1][1].headers["Idempotency-Key"]).toBe(key);
  });
});
