import { afterEach, describe, expect, it, vi } from "vitest";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { StructuredSpecCreateClient, type StructuredSpecDraft } from "./structuredSpecCreateClient";

const project = "01234567-89ab-4cde-8123-456789abcdef";
const requirement = "11234567-89ab-4cde-8123-456789abcdef";
const requirementVersion = "21234567-89ab-4cde-8123-456789abcdef";
const section = "31234567-89ab-4cde-8123-456789abcdef";
const sectionVersion = "41234567-89ab-4cde-8123-456789abcdef";
const evidence = "51234567-89ab-4cde-8123-456789abcdef";
const version = "61234567-89ab-4cde-8123-456789abcdef";
const series = "71234567-89ab-4cde-8123-456789abcdef";
const trace = "81234567-89ab-4cde-8123-456789abcdef";
const key = "91234567-89ab-4cde-8123-456789abcdef";
const draft: StructuredSpecDraft = {
  spec_type: "MIGRATION_SPEC",
  payload: { assumptions: ["synthetic pending confirmation"], exclusions: [],
    source_system: "old", target_system: "new", scope: "parts",
    cleansing_rules: ["deduplicate"], field_mappings: [{ source: "old_id", target: "part_id" }],
    trial_plan: "trial", reconciliation_plan: "reconcile", rollback_plan: "snapshot",
    acceptance_criteria: "zero difference" },
  requirement_refs: [{ requirement_id: requirement, requirement_version_id: requirementVersion }],
  section_refs: [{ solution_section_id: section, solution_section_version_id: sectionVersion }],
  evidence_ids: [evidence], artifact_ids: [],
};
const item = { ...draft, structured_solution_spec_id: version, spec_series_id: series,
  project_id: project, version_no: 1, version_state: "DRAFT", content_fingerprint: "a".repeat(64),
  payload_fingerprint: "b".repeat(64), declared_requirement_count: 1,
  declared_section_count: 1, declared_evidence_count: 1, supersedes_version_ref: null,
  review_ref: null, review_round_ref: null, created_by: project,
  created_at: "2026-10-12T00:00:00Z" };
function response(data: unknown = item, location = version): Response {
  return new Response(JSON.stringify({ data, trace_id: trace }), { status: 201,
    headers: { "Content-Type": "application/json", "Cache-Control": "no-store",
      "X-Trace-Id": trace,
      Location: `/api/v1/projects/${project}/structured-solution-specs/${location}` } });
}
async function setup(role = "PROJECT_MANAGER", result: Response = response()) {
  const fetcher = vi.fn().mockResolvedValueOnce(new Response(JSON.stringify({ data: {
    user: { user_id: project, username_display: "synthetic user" }, deployment_role: "NONE",
    password_change_required: false,
    authorized_projects: [{ project_id: project, name: "project", role }],
    absolute_expires_at: "2030-01-01T12:00:00Z", idle_expires_at: "2030-01-01T11:00:00Z",
    csrf_token: "a".repeat(64),
  }, trace_id: trace }), { status: 200, headers: { "Content-Type": "application/json" } }))
    .mockResolvedValueOnce(result);
  const session = new SessionClient(fetcher as typeof fetch);
  await session.login("user", "synthetic-only");
  return { api: new StructuredSpecCreateClient(session), fetcher };
}

describe("StructuredSpecCreateClient", () => {
  afterEach(() => vi.restoreAllMocks());
  it("sends fixed DRAFT and key through guarded Session bridge", async () => {
    const { api, fetcher } = await setup();
    expect(await api.create(project, draft, key)).toEqual(item);
    expect(fetcher).toHaveBeenCalledTimes(2);
    expect(fetcher.mock.calls[1]?.[0]).toBe(`/api/v1/projects/${project}/structured-solution-specs`);
    expect(fetcher.mock.calls[1]?.[1]).toMatchObject({ method: "POST", body: JSON.stringify(draft),
      credentials: "same-origin", redirect: "error", headers: expect.objectContaining({
        "Idempotency-Key": key, "X-CSRF-Token": "a".repeat(64) }) });
  });
  it("rejects non-writers, wrong project and malformed fixed refs before POST", async () => {
    const reader = await setup("CUSTOMER_MEMBER");
    await expect(reader.api.create(project, draft, key)).rejects.toMatchObject({
      code: "STRUCTURED_SPEC_CREATE_INVALID" });
    expect(reader.fetcher).toHaveBeenCalledTimes(1);
    const manager = await setup();
    for (const bad of [
      { ...draft, artifact_ids: [evidence] },
      { ...draft, section_refs: [] },
      { ...draft, evidence_ids: [evidence, evidence] },
      { ...draft, requirement_refs: [...draft.requirement_refs, ...draft.requirement_refs] },
      { ...draft, payload: {} },
    ]) {
      await expect(manager.api.create(project, bad as StructuredSpecDraft, key))
        .rejects.toMatchObject({ code: "STRUCTURED_SPEC_CREATE_INVALID" });
    }
    await expect(manager.api.create(section, draft, key)).rejects.toMatchObject({
      code: "STRUCTURED_SPEC_CREATE_INVALID" });
    expect(manager.fetcher).toHaveBeenCalledTimes(1);
  });
  it("fails closed on mismatched original receipt and count", async () => {
    for (const bad of [response({ ...item, project_id: section }),
      response({ ...item, declared_evidence_count: 0 }), response(item, evidence),
      response({ ...item, payload: { scope: "other" } }),
      response({ ...item, section_refs: [] }),
      response({ ...item, review_ref: requirement }),
      response({ ...item, content_fingerprint: "bad" })]) {
      const { api } = await setup("PROJECT_MANAGER", bad);
      await expect(api.create(project, draft, key)).rejects.toMatchObject({
        code: "STRUCTURED_SPEC_CREATE_UNCERTAIN", uncertain: true });
    }
  });
  it("maps confirmed rejection but keeps network failures uncertain", async () => {
    const rejected = new Response(JSON.stringify({ error: { code: "VALIDATION_FAILED", message: "invalid" },
      trace_id: trace }), { status: 422,
      headers: { "Content-Type": "application/json", "Cache-Control": "no-store", "X-Trace-Id": trace } });
    const { api } = await setup("PROJECT_MANAGER", rejected);
    await expect(api.create(project, draft, key)).rejects.toMatchObject({ code: "VALIDATION_FAILED" });
    const second = await setup();
    second.fetcher.mockReset(); second.fetcher.mockRejectedValueOnce(new Error("disconnect"));
    await expect(second.api.create(project, draft, key)).rejects.toMatchObject({
      code: "STRUCTURED_SPEC_CREATE_UNCERTAIN", uncertain: true });
  });
});
