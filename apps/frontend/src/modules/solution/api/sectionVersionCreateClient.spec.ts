import { afterEach, describe, expect, it, vi } from "vitest";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { SectionVersionCreateClient, type SectionVersionDraft } from "./sectionVersionCreateClient";

const project = "01234567-89ab-4cde-8123-456789abcdef";
const section = "11234567-89ab-4cde-8123-456789abcdef";
const document = "21234567-89ab-4cde-8123-456789abcdef";
const requirement = "31234567-89ab-4cde-8123-456789abcdef";
const requirementVersion = "41234567-89ab-4cde-8123-456789abcdef";
const evidence = "51234567-89ab-4cde-8123-456789abcdef";
const version = "61234567-89ab-4cde-8123-456789abcdef";
const trace = "71234567-89ab-4cde-8123-456789abcdef";
const key = "81234567-89ab-4cde-8123-456789abcdef";
const draft: SectionVersionDraft = { title: "章节草案", content_document_version_ref: document,
  content_artifact_ref: null,
  requirement_refs: [{ requirement_id: requirement, requirement_version_id: requirementVersion }],
  evidence_ids: [evidence], assumptions: [{ note: "待核查" }], exclusions: [] };
const item = { ...draft, solution_section_version_id: version, solution_section_id: section,
  project_id: project, version_no: 1, version_state: "DRAFT", content_fingerprint: "a".repeat(64),
  declared_requirement_count: 1, declared_evidence_count: 1,
  supersedes_version_ref: null, review_ref: null, review_round_ref: null,
  created_by: project, created_at: "2026-10-12T00:00:00Z" };
function response(data: unknown = item, location = version): Response {
  return new Response(JSON.stringify({ data, trace_id: trace }), { status: 201,
    headers: { "Content-Type": "application/json", "Cache-Control": "no-store",
      "X-Trace-Id": trace,
      Location: `/api/v1/projects/${project}/solution-sections/${section}/versions/${location}` } });
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
  return { api: new SectionVersionCreateClient(session), fetcher };
}

describe("SectionVersionCreateClient", () => {
  afterEach(() => vi.restoreAllMocks());
  it("sends original Document-only draft and key through guarded session bridge", async () => {
    const { api, fetcher } = await setup();
    expect(await api.create(project, section, draft, key)).toEqual(item);
    expect(fetcher).toHaveBeenCalledTimes(2);
    expect(fetcher.mock.calls[1]?.[0]).toBe(
      `/api/v1/projects/${project}/solution-sections/${section}/versions`);
    expect(fetcher.mock.calls[1]?.[1]).toMatchObject({ method: "POST", body: JSON.stringify(draft),
      credentials: "same-origin", redirect: "error", headers: expect.objectContaining({
        "Idempotency-Key": key, "X-CSRF-Token": "a".repeat(64) }) });
  });
  it("rejects non-writers, wrong project, Artifact, duplicate refs and malformed draft before POST", async () => {
    const reader = await setup("CUSTOMER_MEMBER");
    await expect(reader.api.create(project, section, draft, key)).rejects.toMatchObject({
      code: "SECTION_VERSION_CREATE_INVALID" });
    expect(reader.fetcher).toHaveBeenCalledTimes(1);
    const manager = await setup();
    for (const bad of [
      { ...draft, content_artifact_ref: evidence },
      { ...draft, content_document_version_ref: null },
      { ...draft, evidence_ids: [evidence, evidence] },
      { ...draft, requirement_refs: [...draft.requirement_refs, ...draft.requirement_refs] },
      { ...draft, title: " 章节草案" },
      { ...draft, assumptions: Array.from({ length: 101 }, () => ({ note: "x" })) },
    ]) {
      await expect(manager.api.create(project, section, bad as SectionVersionDraft, key))
        .rejects.toMatchObject({ code: "SECTION_VERSION_CREATE_INVALID" });
    }
    await expect(manager.api.create(section, section, draft, key)).rejects.toMatchObject({
      code: "SECTION_VERSION_CREATE_INVALID" });
    expect(manager.fetcher).toHaveBeenCalledTimes(1);
  });
  it("treats mismatched fixed receipt, count and Location as uncertain", async () => {
    for (const bad of [response({ ...item, project_id: section }),
      response({ ...item, declared_evidence_count: 0 }), response(item, evidence),
      response({ ...item, title: "other" }), response({ ...item, evidence_ids: [] }),
      response({ ...item, review_ref: requirement }),
      response({ ...item, content_fingerprint: "bad" })]) {
      const { api } = await setup("PROJECT_MANAGER", bad);
      await expect(api.create(project, section, draft, key)).rejects.toMatchObject({
        code: "SECTION_VERSION_CREATE_UNCERTAIN", uncertain: true });
    }
  });
  it("maps confirmed rejection and preserves uncertainty on transport failure", async () => {
    const rejected = new Response(JSON.stringify({ error: { code: "VALIDATION_FAILED", message: "invalid" },
      trace_id: trace }), { status: 422,
      headers: { "Content-Type": "application/json", "Cache-Control": "no-store", "X-Trace-Id": trace } });
    const { api } = await setup("PROJECT_MANAGER", rejected);
    await expect(api.create(project, section, draft, key)).rejects.toMatchObject({ code: "VALIDATION_FAILED" });
    const second = await setup();
    second.fetcher.mockReset(); second.fetcher.mockRejectedValueOnce(new Error("disconnect"));
    await expect(second.api.create(project, section, draft, key)).rejects.toMatchObject({
      code: "SECTION_VERSION_CREATE_UNCERTAIN" });
  });
});
