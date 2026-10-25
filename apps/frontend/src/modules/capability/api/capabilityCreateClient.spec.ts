import { afterEach, describe, expect, it, vi } from "vitest";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { CapabilityCreateClient, normalizeCapabilitySources } from "./capabilityCreateClient";

const actor = "01234567-89ab-4cde-8123-456789abcdef";
const baseline = "11234567-89ab-4cde-8123-456789abcdef";
const document = "21234567-89ab-4cde-8123-456789abcdef";
const version = "31234567-89ab-4cde-8123-456789abcdef";
const key = "synthetic-cap-create-0001";
const input = { baseline_code: "STD-01", name: "标准能力", description: null,
  source_documents: [{ document_id: document, document_version_id: version }] };
const receipt = { baseline_id: baseline, baseline_code: "STD-01", name: "标准能力",
  description: null, state: "ACTIVE", source_collection_ref: `sha256:${"a".repeat(64)}`,
  current_approved_version_ref: null, created_at: "2026-10-24T01:00:00Z", etag: '"v0"' };
function response(data: unknown, status = 201, headers: Record<string, string> = {}): Response {
  return new Response(JSON.stringify({ data, trace_id: actor }), { status, headers: {
    "Content-Type": "application/json", "Cache-Control": "no-store",
    ETag: '"v0"', Location: `/api/v1/global/capability-baselines/${baseline}`, ...headers } });
}
function auth(admin: boolean): Response { return response({ user: { user_id: actor, username_display: "合成用户" },
  deployment_role: admin ? "DEPLOYMENT_ADMIN" : "NONE", password_change_required: false,
  authorized_projects: admin ? [] : [{ project_id: baseline, name: "合成项目", role: "PROJECT_MANAGER" }],
  absolute_expires_at: "2030-01-01T12:00:00Z", idle_expires_at: "2030-01-01T11:00:00Z",
  csrf_token: "a".repeat(64) }, 200); }
function harness(admin: boolean, ...results: Response[]) {
  const fetcher = vi.fn(); [auth(admin), ...results].forEach(item => fetcher.mockResolvedValueOnce(item));
  const session = new SessionClient(fetcher as typeof fetch);
  return { session, client: new CapabilityCreateClient(session), fetcher };
}
describe("CapabilityCreateClient", () => {
  afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });
  it("creates only from fixed GLOBAL source references with private CSRF and strict first receipt", async () => {
    const { session, client, fetcher } = harness(true, response({ ...receipt, private_path: "secret" }));
    await session.login("synthetic", "synthetic-only");
    await expect(client.create(input, key)).rejects.toMatchObject({ code: "CAPABILITY_CREATE_UNCERTAIN" });
    expect(fetcher.mock.calls[1][0]).toBe("/api/v1/global/capability-baselines");
    expect(fetcher.mock.calls[1][1].headers["X-CSRF-Token"]).toBe("a".repeat(64));
    expect(fetcher.mock.calls[1][1].headers["Idempotency-Key"]).toBe(key);
    expect(JSON.parse(fetcher.mock.calls[1][1].body)).toEqual(input);
    const good = harness(true, response(receipt)); await good.session.login("synthetic", "synthetic-only");
    await expect(good.client.create(input, key)).resolves.toEqual(receipt);
  });
  it("rejects duplicate sources and malformed keys before any write", async () => {
    expect(() => normalizeCapabilitySources([{ document_id: document, document_version_id: version },
      { document_id: document, document_version_id: baseline }])).toThrowError();
    const { session, client, fetcher } = harness(true); await session.login("synthetic", "synthetic-only");
    await expect(client.create({ ...input, source_documents: [] }, key)).rejects.toMatchObject({ code: "CAPABILITY_CREATE_INVALID" });
    await expect(client.create(input, "short")).rejects.toMatchObject({ code: "CAPABILITY_CREATE_INVALID" });
    expect(fetcher).toHaveBeenCalledTimes(1);
  });
  it("blocks an ordinary project manager before the command", async () => {
    const { session, client, fetcher } = harness(false); await session.login("synthetic", "synthetic-only");
    await expect(client.create(input, key)).rejects.toMatchObject({ code: "RESOURCE_NOT_FOUND" });
    expect(fetcher).toHaveBeenCalledTimes(1);
  });
  it("maps known server failures but fails closed on wrong Location or no-store", async () => {
    const denied = harness(true, new Response(JSON.stringify({ error: { code: "VALIDATION_FAILED",
      message: "private" }, trace_id: actor }), { status: 422,
      headers: { "Content-Type": "application/json" } }));
    await denied.session.login("synthetic", "synthetic-only");
    await expect(denied.client.create(input, key)).rejects.toMatchObject({ code: "VALIDATION_FAILED" });
    const wrong = harness(true, response(receipt, 201, { Location: "/api/v1/projects/other" }));
    await wrong.session.login("synthetic", "synthetic-only");
    await expect(wrong.client.create(input, key)).rejects.toMatchObject({ code: "CAPABILITY_CREATE_UNCERTAIN" });
    const noStore = harness(true, response(receipt, 201, { "Cache-Control": "public" }));
    await noStore.session.login("synthetic", "synthetic-only");
    await expect(noStore.client.create(input, key)).rejects.toMatchObject({ code: "CAPABILITY_CREATE_UNCERTAIN" });
  });
});
