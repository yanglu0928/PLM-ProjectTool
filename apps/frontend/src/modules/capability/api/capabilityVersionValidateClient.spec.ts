import { afterEach, describe, expect, it, vi } from "vitest";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { CapabilityVersionValidateClient } from "./capabilityVersionValidateClient";

const actor = "01234567-89ab-4cde-8123-456789abcdef";
const baseline = "11234567-89ab-4cde-8123-456789abcdef";
const versionId = "21234567-89ab-4cde-8123-456789abcdef";
const audit = "31234567-89ab-4cde-8123-456789abcdef";
const version = { baseline_id: baseline, baseline_version_id: versionId, version_no: 1,
  state: "DRAFT" as const, source_collection_ref: `sha256:${"a".repeat(64)}`,
  content_fingerprint: "b".repeat(64), declared_item_count: 1, declared_document_ref_count: 1,
  declared_evidence_ref_count: 1, supersedes_version_ref: null, review_ref: null,
  review_round_ref: null, created_at: "2026-10-24T01:00:00Z" };
const report = { audit_event_id: audit, baseline_id: baseline, baseline_version_id: versionId,
  version_no: 1, state: "DRAFT", source_collection_ref: version.source_collection_ref,
  content_fingerprint: version.content_fingerprint, item_count: 1, document_ref_count: 1,
  evidence_ref_count: 1, valid: true, blocking_issues: [], warnings: [],
  checked_at: "2026-10-24T01:01:00Z" };
function json(data: unknown, status = 200, headers: Record<string, string> = {}): Response {
  return new Response(JSON.stringify({ data, trace_id: actor }), { status,
    headers: { "Content-Type": "application/json", "Cache-Control": "no-store", ...headers } });
}
function auth(admin: boolean): Response { return json({ user: { user_id: actor, username_display: "合成用户" },
  deployment_role: admin ? "DEPLOYMENT_ADMIN" : "NONE", password_change_required: false,
  authorized_projects: admin ? [] : [{ project_id: baseline, name: "合成项目", role: "PROJECT_MANAGER" }],
  absolute_expires_at: "2030-01-01T12:00:00Z", idle_expires_at: "2030-01-01T11:00:00Z",
  csrf_token: "a".repeat(64) }); }
function harness(admin: boolean, ...results: Response[]) {
  const fetcher = vi.fn(); [auth(admin), ...results].forEach(result => fetcher.mockResolvedValueOnce(result));
  const session = new SessionClient(fetcher as typeof fetch);
  return { session, client: new CapabilityVersionValidateClient(session), fetcher };
}
describe("CapabilityVersionValidateClient", () => {
  afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });
  it("validates a DRAFT through an empty-body POST with private CSRF and original key", async () => {
    const { session, client, fetcher } = harness(true, json(report));
    await session.login("synthetic", "synthetic-only");
    await expect(client.validate(version, "synthetic-cap-validate-001")).resolves.toMatchObject(report);
    expect(fetcher.mock.calls[1][0]).toBe(
      `/api/v1/global/capability-baselines/${baseline}/versions/${versionId}:validate`);
    expect(fetcher.mock.calls[1][1].body).toBeUndefined();
    expect(fetcher.mock.calls[1][1].headers).toMatchObject({
      "X-CSRF-Token": "a".repeat(64), "Idempotency-Key": "synthetic-cap-validate-001" });
  });
  it("keeps a failed validation report distinct from an approved version", async () => {
    const { session, client } = harness(true, json({ ...report, valid: false,
      blocking_issues: ["EVIDENCE_UNAVAILABLE"] }));
    await session.login("synthetic", "synthetic-only");
    await expect(client.validate(version, "synthetic-cap-validate-002"))
      .resolves.toMatchObject({ state: "DRAFT", valid: false,
        blocking_issues: ["EVIDENCE_UNAVAILABLE"] });
  });
  it("blocks ordinary users and non-DRAFT versions before network", async () => {
    const ordinary = harness(false); await ordinary.session.login("synthetic", "synthetic-only");
    await expect(ordinary.client.validate(version, "synthetic-cap-validate-003"))
      .rejects.toMatchObject({ code: "RESOURCE_NOT_FOUND" });
    expect(ordinary.fetcher).toHaveBeenCalledTimes(1);
    const admin = harness(true); await admin.session.login("synthetic", "synthetic-only");
    await expect(admin.client.validate({ ...version, state: "APPROVED" }, "synthetic-cap-validate-004"))
      .rejects.toMatchObject({ code: "CAP_VALIDATE_INVALID" });
    expect(admin.fetcher).toHaveBeenCalledTimes(1);
  });
  it("fails closed for inconsistent receipts and unknown network outcome", async () => {
    const mismatch = harness(true, json({ ...report, valid: true,
      blocking_issues: ["SOURCE_UNAVAILABLE"] }));
    await mismatch.session.login("synthetic", "synthetic-only");
    await expect(mismatch.client.validate(version, "synthetic-cap-validate-005"))
      .rejects.toMatchObject({ code: "CAP_VALIDATE_UNCERTAIN", uncertain: true });
    const lost = harness(true); await lost.session.login("synthetic", "synthetic-only");
    await expect(lost.client.validate(version, "synthetic-cap-validate-006"))
      .rejects.toMatchObject({ code: "CAP_VALIDATE_UNCERTAIN" });
    expect(lost.fetcher.mock.calls[1][1].headers["Idempotency-Key"]).toBe("synthetic-cap-validate-006");
  });
});
