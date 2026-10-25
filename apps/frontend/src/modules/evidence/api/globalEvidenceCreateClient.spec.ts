import { afterEach, describe, expect, it, vi } from "vitest";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { GlobalEvidenceCreateClient, normalizeGlobalEvidenceCreate } from "./globalEvidenceCreateClient";

const actor = "01234567-89ab-4cde-8123-456789abcdef";
const document = "21234567-89ab-4cde-8123-456789abcdef";
const version = "31234567-89ab-4cde-8123-456789abcdef";
const evidence = "41234567-89ab-4cde-8123-456789abcdef";
const key = "synthetic-global-evidence-0001";
const input = { document_id: document, document_version_id: version,
  locator: { locator_type: "DOCUMENT" as const }, display_label: "整份标准能力资料", display_excerpt: null };
const receipt = { evidence_id: evidence, ...input, content_fingerprint: "a".repeat(64),
  eligibility_state: "CANDIDATE", created_at: "2026-10-24T01:00:00Z", etag: '"v0"' };
function response(data: unknown, status = 201, headers: Record<string, string> = {}): Response {
  return new Response(JSON.stringify({ data, trace_id: actor }), { status, headers: {
    "Content-Type": "application/json", "Cache-Control": "no-store", ETag: '"v0"',
    Location: `/api/v1/global/evidence/${evidence}`, ...headers } });
}
function auth(admin: boolean): Response { return response({ user: { user_id: actor, username_display: "合成用户" },
  deployment_role: admin ? "DEPLOYMENT_ADMIN" : "NONE", password_change_required: false,
  authorized_projects: admin ? [] : [{ project_id: document, name: "合成项目", role: "PROJECT_MANAGER" }],
  absolute_expires_at: "2030-01-01T12:00:00Z", idle_expires_at: "2030-01-01T11:00:00Z",
  csrf_token: "a".repeat(64) }, 200); }
function harness(admin: boolean, ...results: Response[]) {
  const fetcher = vi.fn(); [auth(admin), ...results].forEach(item => fetcher.mockResolvedValueOnce(item));
  const session = new SessionClient(fetcher as typeof fetch);
  return { session, client: new GlobalEvidenceCreateClient(session), fetcher };
}
describe("GlobalEvidenceCreateClient", () => {
  afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });
  it("creates only a CANDIDATE from a fixed whole GLOBAL document with private CSRF", async () => {
    const good = harness(true, response(receipt)); await good.session.login("synthetic", "synthetic-only");
    await expect(good.client.create(input, key)).resolves.toEqual(receipt);
    expect(good.fetcher.mock.calls[1][0]).toBe("/api/v1/global/evidence");
    expect(good.fetcher.mock.calls[1][1].headers["X-CSRF-Token"]).toBe("a".repeat(64));
    expect(good.fetcher.mock.calls[1][1].headers["Idempotency-Key"]).toBe(key);
    expect(JSON.parse(good.fetcher.mock.calls[1][1].body)).toEqual(input);
    const falseApproved = harness(true, response({ ...receipt, eligibility_state: "ELIGIBLE" }));
    await falseApproved.session.login("synthetic", "synthetic-only");
    await expect(falseApproved.client.create(input, key)).rejects.toMatchObject({ code: "EVIDENCE_CREATE_UNCERTAIN" });
  });
  it("rejects precise or malformed locators and keys before network write", async () => {
    expect(() => normalizeGlobalEvidenceCreate({ ...input, locator: { locator_type: "SECTION" } })).toThrowError();
    const result = harness(true); await result.session.login("synthetic", "synthetic-only");
    await expect(result.client.create({ ...input, document_version_id: "invalid" }, key))
      .rejects.toMatchObject({ code: "EVIDENCE_CREATE_INVALID" });
    await expect(result.client.create(input, "short")).rejects.toMatchObject({ code: "EVIDENCE_CREATE_INVALID" });
    expect(result.fetcher).toHaveBeenCalledTimes(1);
  });
  it("blocks ordinary project members before writing GLOBAL Evidence", async () => {
    const result = harness(false); await result.session.login("synthetic", "synthetic-only");
    await expect(result.client.create(input, key)).rejects.toMatchObject({ code: "RESOURCE_NOT_FOUND" });
    expect(result.fetcher).toHaveBeenCalledTimes(1);
  });
  it("maps known refusal and fails closed on receipt location, cache or extra fields", async () => {
    const denied = harness(true, new Response(JSON.stringify({ error: { code: "VALIDATION_FAILED",
      message: "private" }, trace_id: actor }), { status: 422,
      headers: { "Content-Type": "application/json" } }));
    await denied.session.login("synthetic", "synthetic-only");
    await expect(denied.client.create(input, key)).rejects.toMatchObject({ code: "VALIDATION_FAILED" });
    for (const bad of [response(receipt, 201, { Location: "/api/v1/projects/other" }),
      response(receipt, 201, { "Cache-Control": "public" }), response({ ...receipt, private_path: "hidden" })]) {
      const result = harness(true, bad); await result.session.login("synthetic", "synthetic-only");
      await expect(result.client.create(input, key)).rejects.toMatchObject({ code: "EVIDENCE_CREATE_UNCERTAIN" });
    }
  });
});
