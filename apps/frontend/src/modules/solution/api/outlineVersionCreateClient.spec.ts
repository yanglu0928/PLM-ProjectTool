import { afterEach, describe, expect, it, vi } from "vitest";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { OutlineVersionCreateClient, type OutlineVersionDraft } from "./outlineVersionCreateClient";

const project = "01234567-89ab-4cde-8123-456789abcdef";
const outline = "11234567-89ab-4cde-8123-456789abcdef";
const section = "21234567-89ab-4cde-8123-456789abcdef";
const requirement = "31234567-89ab-4cde-8123-456789abcdef";
const requirementVersion = "41234567-89ab-4cde-8123-456789abcdef";
const reference = "51234567-89ab-4cde-8123-456789abcdef";
const referenceVersion = "61234567-89ab-4cde-8123-456789abcdef";
const version = "71234567-89ab-4cde-8123-456789abcdef";
const trace = "81234567-89ab-4cde-8123-456789abcdef";
const key = "91234567-89ab-4cde-8123-456789abcdef";
const draft: OutlineVersionDraft = { section_ids: [section],
  requirement_refs: [{ requirement_id: requirement, requirement_version_id: requirementVersion }],
  reference_refs: [{ scope: "PROJECT", reference_solution_id: reference,
    reference_version_id: referenceVersion }], missing_declarations: [], conflict_declarations: [] };
const item = { solution_outline_version_id: version, solution_outline_id: outline, project_id: project,
  version_no: 1, version_state: "DRAFT", content_fingerprint: "a".repeat(64),
  missing_declarations: [], conflict_declarations: [], declared_section_count: 1,
  declared_requirement_count: 1, declared_reference_count: 1,
  supersedes_version_ref: null, review_ref: null, review_round_ref: null,
  created_by: project, created_at: "2026-10-09T00:00:00Z" };
function response(data: unknown = item, location = version): Response {
  return new Response(JSON.stringify({ data, trace_id: trace }), { status: 201,
    headers: { "Content-Type": "application/json", "X-Trace-Id": trace,
      Location: `/api/v1/projects/${project}/solution-outlines/${outline}/versions/${location}` } });
}
async function setup(role = "PROJECT_MANAGER", result: Response = response()) {
  const fetcher = vi.fn().mockResolvedValueOnce(new Response(JSON.stringify({ data: {
    user: { user_id: project, username_display: "合成用户" }, deployment_role: "NONE",
    password_change_required: false,
    authorized_projects: [{ project_id: project, name: "项目", role }],
    absolute_expires_at: "2030-01-01T12:00:00Z", idle_expires_at: "2030-01-01T11:00:00Z",
    csrf_token: "a".repeat(64),
  }, trace_id: trace }), { status: 200, headers: { "Content-Type": "application/json" } }))
    .mockResolvedValueOnce(result);
  const session = new SessionClient(fetcher as typeof fetch);
  await session.login("user", "synthetic-only");
  return { api: new OutlineVersionCreateClient(session), fetcher };
}

describe("OutlineVersionCreateClient", () => {
  afterEach(() => vi.restoreAllMocks());
  it("sends fixed refs and original key through the guarded session bridge", async () => {
    const { api, fetcher } = await setup();
    expect(await api.create(project, outline, draft, key)).toEqual(item);
    expect(fetcher).toHaveBeenCalledTimes(2);
    expect(fetcher.mock.calls[1]?.[0]).toBe(
      `/api/v1/projects/${project}/solution-outlines/${outline}/versions`);
    expect(fetcher.mock.calls[1]?.[1]).toMatchObject({ method: "POST", body: JSON.stringify(draft),
      credentials: "same-origin", redirect: "error", headers: expect.objectContaining({
        "Idempotency-Key": key, "X-CSRF-Token": "a".repeat(64) }) });
  });
  it("rejects invalid, duplicate and reader/cross-project input before writing", async () => {
    const { api, fetcher } = await setup("CUSTOMER_MEMBER");
    await expect(api.create(project, outline, draft, key)).rejects.toMatchObject({ code: "OUTLINE_VERSION_CREATE_INVALID" });
    expect(fetcher).toHaveBeenCalledTimes(1);
    const manager = await setup();
    for (const bad of [
      { ...draft, section_ids: [] },
      { ...draft, section_ids: [section, section] },
      { ...draft, requirement_refs: [] as [], reference_refs: [] as [] },
      { ...draft, reference_refs: [{ ...draft.reference_refs[0]!, scope: "INVALID" }] },
    ]) {
      await expect(manager.api.create(project, outline, bad as OutlineVersionDraft, key))
        .rejects.toMatchObject({ code: "OUTLINE_VERSION_CREATE_INVALID" });
    }
    await expect(manager.api.create(outline, outline, draft, key))
      .rejects.toMatchObject({ code: "OUTLINE_VERSION_CREATE_INVALID" });
    expect(manager.fetcher).toHaveBeenCalledTimes(1);
  });
  it("treats wrong receipt fields and Location as uncertain", async () => {
    for (const bad of [response({ ...item, project_id: outline }),
      response({ ...item, declared_reference_count: 0 }), response(item, section),
      response({ ...item, review_ref: section }), response({ ...item, content_fingerprint: "bad" })]) {
      const { api } = await setup("PROJECT_MANAGER", bad);
      await expect(api.create(project, outline, draft, key))
        .rejects.toMatchObject({ code: "OUTLINE_VERSION_CREATE_UNCERTAIN", uncertain: true });
    }
  });
  it("maps confirmed rejection and preserves uncertainty on transport failure", async () => {
    const rejected = new Response(JSON.stringify({ error: { code: "VALIDATION_FAILED", message: "invalid" },
      trace_id: trace }), { status: 422, headers: { "Content-Type": "application/json" } });
    const { api } = await setup("PROJECT_MANAGER", rejected);
    await expect(api.create(project, outline, draft, key)).rejects.toMatchObject({ code: "VALIDATION_FAILED" });
    const second = await setup();
    second.fetcher.mockReset();
    second.fetcher.mockRejectedValueOnce(new Error("disconnect"));
    await expect(second.api.create(project, outline, draft, key))
      .rejects.toMatchObject({ code: "OUTLINE_VERSION_CREATE_UNCERTAIN" });
  });
});
