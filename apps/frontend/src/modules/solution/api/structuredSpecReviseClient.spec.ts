import { afterEach, describe, expect, it, vi } from "vitest";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { StructuredSpecReviseClient } from "./structuredSpecReviseClient";
import type { StructuredSpecDraft } from "./structuredSpecCreateClient";

const project = "01234567-89ab-4cde-8123-456789abcdef";
const predecessor = "11234567-89ab-4cde-8123-456789abcdef";
const version = "21234567-89ab-4cde-8123-456789abcdef";
const requirement = "31234567-89ab-4cde-8123-456789abcdef";
const requirementVersion = "41234567-89ab-4cde-8123-456789abcdef";
const section = "51234567-89ab-4cde-8123-456789abcdef";
const sectionVersion = "61234567-89ab-4cde-8123-456789abcdef";
const evidence = "71234567-89ab-4cde-8123-456789abcdef";
const series = "81234567-89ab-4cde-8123-456789abcdef";
const trace = "91234567-89ab-4cde-8123-456789abcdef";
const key = "a1234567-89ab-4cde-8123-456789abcdef";
const draft: StructuredSpecDraft = { spec_type: "MIGRATION_SPEC",
  payload: { assumptions: [], exclusions: [], source_system: "old", target_system: "new",
    scope: "parts", cleansing_rules: ["deduplicate"],
    field_mappings: [{ source: "old_id", target: "part_id" }], trial_plan: "trial",
    reconciliation_plan: "reconcile", rollback_plan: "snapshot",
    acceptance_criteria: "zero difference" },
  requirement_refs: [{ requirement_id: requirement, requirement_version_id: requirementVersion }],
  section_refs: [{ solution_section_id: section, solution_section_version_id: sectionVersion }],
  evidence_ids: [evidence], artifact_ids: [] };
const item = { ...draft, structured_solution_spec_id: version, spec_series_id: series,
  project_id: project, version_no: 2, version_state: "DRAFT", content_fingerprint: "a".repeat(64),
  payload_fingerprint: "b".repeat(64), declared_requirement_count: 1,
  declared_section_count: 1, declared_evidence_count: 1, supersedes_version_ref: predecessor,
  review_ref: null, review_round_ref: null, created_by: project,
  created_at: "2026-10-16T00:00:00Z" };
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
  return { api: new StructuredSpecReviseClient(session), fetcher };
}

describe("StructuredSpecReviseClient", () => {
  afterEach(() => vi.restoreAllMocks());
  it("sends the exact predecessor, DRAFT and key through the guarded session bridge", async () => {
    const { api, fetcher } = await setup();
    expect(await api.revise(project, predecessor, draft, key)).toEqual(item);
    expect(fetcher.mock.calls[1]?.[0]).toBe(
      `/api/v1/projects/${project}/structured-solution-specs/${predecessor}:revise`);
    expect(fetcher.mock.calls[1]?.[1]).toMatchObject({ method: "POST", body: JSON.stringify(draft),
      credentials: "same-origin", redirect: "error", headers: expect.objectContaining({
        "Idempotency-Key": key, "X-CSRF-Token": "a".repeat(64) }) });
  });
  it("rejects non-writers, wrong identities and malformed drafts before POST", async () => {
    const reader = await setup("CUSTOMER_MEMBER");
    await expect(reader.api.revise(project, predecessor, draft, key)).rejects.toMatchObject({
      code: "STRUCTURED_SPEC_REVISE_INVALID" });
    expect(reader.fetcher).toHaveBeenCalledTimes(1);
    const writer = await setup();
    for (const args of [[section, predecessor, draft, key], [project, "bad", draft, key],
      [project, predecessor, { ...draft, section_refs: [] }, key],
      [project, predecessor, draft, "short"]] as const) {
      await expect(writer.api.revise(args[0], args[1], args[2] as StructuredSpecDraft, args[3]))
        .rejects.toMatchObject({ code: "STRUCTURED_SPEC_REVISE_INVALID" });
    }
    expect(writer.fetcher).toHaveBeenCalledTimes(1);
  });
  it("fails closed when the new revision receipt is not bound to the request", async () => {
    for (const bad of [response({ ...item, supersedes_version_ref: section }),
      response({ ...item, project_id: section }), response({ ...item, version_no: 1 }),
      response({ ...item, payload: { ...draft.payload, scope: "other" } }),
      response({ ...item, review_ref: requirement, review_round_ref: requirementVersion }),
      response(item, evidence)]) {
      const { api } = await setup("PROJECT_MANAGER", bad);
      await expect(api.revise(project, predecessor, draft, key)).rejects.toMatchObject({
        code: "STRUCTURED_SPEC_REVISE_UNCERTAIN", uncertain: true });
    }
  });
  it("maps confirmed conflicts while retaining the original operation after transport failure", async () => {
    for (const code of ["CONFLICT_VERSION", "CONFLICT_STATE", "CONFLICT_IDEMPOTENCY"] as const) {
      const rejected = new Response(JSON.stringify({ error: { code, message: "conflict" },
        trace_id: trace }), { status: 409, headers: { "Content-Type": "application/json",
          "Cache-Control": "no-store", "X-Trace-Id": trace } });
      const { api } = await setup("PROJECT_MANAGER", rejected);
      await expect(api.revise(project, predecessor, draft, key)).rejects.toMatchObject({ code });
    }
    const failed = await setup();
    failed.fetcher.mockReset(); failed.fetcher.mockRejectedValueOnce(new Error("disconnect"));
    await expect(failed.api.revise(project, predecessor, draft, key)).rejects.toMatchObject({
      code: "STRUCTURED_SPEC_REVISE_UNCERTAIN", uncertain: true });
  });
});
