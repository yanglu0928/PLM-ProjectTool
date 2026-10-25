import { afterEach, describe, expect, it, vi } from "vitest";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import type { HandoverAnalysisVersionView } from "./handoverReadClient";
import { HandoverVersionValidateClient } from "./handoverVersionValidateClient";

const actor = "01234567-89ab-4cde-8123-456789abcdef";
const project = "11234567-89ab-4cde-8123-456789abcdef";
const analysis = "21234567-89ab-4cde-8123-456789abcdef";
const versionId = "31234567-89ab-4cde-8123-456789abcdef";
const audit = "41234567-89ab-4cde-8123-456789abcdef";
const version: HandoverAnalysisVersionView = {
  handover_analysis_version_id: versionId, handover_analysis_id: analysis, project_id: project,
  version_no: 1, state: "DRAFT", source_set_ref: `sha256:${"a".repeat(64)}`,
  capability_baseline_id: "51234567-89ab-4cde-8123-456789abcdef",
  capability_baseline_version_ref: "61234567-89ab-4cde-8123-456789abcdef",
  content_fingerprint: "b".repeat(64), declared_source_count: 1, declared_item_count: 2,
  declared_evidence_count: 2, declared_capability_ref_count: 0, declared_ai_task_count: 0,
  supersedes_version_ref: null, review_ref: null, review_round_ref: null,
  created_by: actor, created_at: "2026-10-25T01:00:00Z",
  source_documents: [{ document_id: "71234567-89ab-4cde-8123-456789abcdef",
    document_version_id: "81234567-89ab-4cde-8123-456789abcdef", ordinal: 0 }], ai_tasks: [],
};
const report = { audit_event_id: audit, handover_analysis_id: analysis,
  handover_analysis_version_id: versionId, project_id: project, version_no: 1, state: "DRAFT",
  item_count: 2, source_count: 1, evidence_count: 2, capability_ref_count: 0, ai_task_count: 0,
  valid: true, blocking_issues: [], warnings: [], checked_at: "2026-10-25T01:01:00Z" };
function json(data: unknown, status = 200): Response {
  return new Response(JSON.stringify({ data, trace_id: actor }), { status,
    headers: { "Content-Type": "application/json", "Cache-Control": "no-store" } });
}
function error(code: string, status: number): Response {
  return new Response(JSON.stringify({ error: { code, message: "synthetic" }, trace_id: actor }), {
    status, headers: { "Content-Type": "application/json", "Cache-Control": "no-store" },
  });
}
function auth(role: "PROJECT_MANAGER" | "IMPLEMENTATION_MEMBER" | "CUSTOMER_MANAGER" | null): Response {
  return json({ user: { user_id: actor, username_display: "合成用户" }, deployment_role: "NONE",
    password_change_required: false, authorized_projects: role ? [{ project_id: project,
      name: "合成项目", role }] : [], absolute_expires_at: "2030-01-01T12:00:00Z",
    idle_expires_at: "2030-01-01T11:00:00Z", csrf_token: "a".repeat(64) });
}
function harness(role: "PROJECT_MANAGER" | "IMPLEMENTATION_MEMBER" | "CUSTOMER_MANAGER" | null,
  ...results: Response[]) {
  const fetcher = vi.fn(); [auth(role), ...results].forEach(result => fetcher.mockResolvedValueOnce(result));
  const session = new SessionClient(fetcher as typeof fetch);
  return { session, client: new HandoverVersionValidateClient(session), fetcher };
}
describe("HandoverVersionValidateClient", () => {
  afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });
  it("sends an empty-body POST with private CSRF and original key", async () => {
    const { session, client, fetcher } = harness("PROJECT_MANAGER", json(report));
    await session.login("synthetic", "synthetic-only");
    await expect(client.validate(version, "synthetic-hnd-validate-001")).resolves.toMatchObject(report);
    expect(fetcher.mock.calls[1][0]).toBe(
      `/api/v1/projects/${project}/handover-analyses/${analysis}/versions/${versionId}:validate`);
    expect(fetcher.mock.calls[1][1].body).toBeUndefined();
    expect(fetcher.mock.calls[1][1].headers).toMatchObject({
      "X-CSRF-Token": "a".repeat(64), "Idempotency-Key": "synthetic-hnd-validate-001" });
  });
  it("keeps blocking issues and DRAFT status distinct from approval", async () => {
    const { session, client } = harness("IMPLEMENTATION_MEMBER", json({ ...report, valid: false,
      blocking_issues: ["SOURCE_UNAVAILABLE", "ACTION_ITEM_REQUIRED"] }));
    await session.login("synthetic", "synthetic-only");
    await expect(client.validate(version, "synthetic-hnd-validate-002"))
      .resolves.toMatchObject({ state: "DRAFT", valid: false,
        blocking_issues: ["SOURCE_UNAVAILABLE", "ACTION_ITEM_REQUIRED"] });
  });
  it("rejects wrong project role and malformed version before network", async () => {
    const ordinary = harness("CUSTOMER_MANAGER"); await ordinary.session.login("synthetic", "synthetic-only");
    await expect(ordinary.client.validate(version, "synthetic-hnd-validate-003"))
      .rejects.toMatchObject({ code: "RESOURCE_NOT_FOUND" });
    expect(ordinary.fetcher).toHaveBeenCalledTimes(1);
    const admin = harness("PROJECT_MANAGER"); await admin.session.login("synthetic", "synthetic-only");
    await expect(admin.client.validate({ ...version, declared_item_count: 0 }, "synthetic-hnd-validate-004"))
      .rejects.toMatchObject({ code: "HND_VALIDATE_INVALID" });
    expect(admin.fetcher).toHaveBeenCalledTimes(1);
  });
  it("fails closed on inconsistent reports and unknown network outcome", async () => {
    const mismatch = harness("PROJECT_MANAGER", json({ ...report, item_count: 3 }));
    await mismatch.session.login("synthetic", "synthetic-only");
    await expect(mismatch.client.validate(version, "synthetic-hnd-validate-005"))
      .rejects.toMatchObject({ code: "HND_VALIDATE_UNCERTAIN", uncertain: true });
    const lost = harness("PROJECT_MANAGER"); await lost.session.login("synthetic", "synthetic-only");
    await expect(lost.client.validate(version, "synthetic-hnd-validate-006"))
      .rejects.toMatchObject({ code: "HND_VALIDATE_UNCERTAIN" });
    expect(lost.fetcher.mock.calls[1][1].headers["Idempotency-Key"]).toBe("synthetic-hnd-validate-006");
  });
  it.each([
    ["AUTH_SESSION_EXPIRED", 401], ["LICENSE_OPERATION_DENIED", 403],
    ["RESOURCE_NOT_FOUND", 404], ["CONFLICT_IDEMPOTENCY", 409],
    ["VALIDATION_FAILED", 422], ["SYSTEM_UNAVAILABLE", 503],
  ])("maps frozen error %s only at its status", async (code, status) => {
    const { session, client } = harness("PROJECT_MANAGER", error(code, status));
    await session.login("synthetic", "synthetic-only");
    await expect(client.validate(version, "synthetic-hnd-validate-error"))
      .rejects.toMatchObject({ code, uncertain: false });
  });
  it.each([
    { ...report, valid: true, blocking_issues: ["SOURCE_UNAVAILABLE"] },
    { ...report, valid: false, blocking_issues: ["ACTION_ITEM_REQUIRED", "SOURCE_UNAVAILABLE"] },
    { ...report, warnings: ["unfrozen-warning"] },
  ])("rejects a contradictory or unfamiliar report", async invalid => {
    const { session, client } = harness("PROJECT_MANAGER", json(invalid));
    await session.login("synthetic", "synthetic-only");
    await expect(client.validate(version, "synthetic-hnd-validate-report"))
      .rejects.toMatchObject({ code: "HND_VALIDATE_UNCERTAIN", uncertain: true });
  });
});
