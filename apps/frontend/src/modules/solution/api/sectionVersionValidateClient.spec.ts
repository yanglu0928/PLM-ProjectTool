import { afterEach, describe, expect, it, vi } from "vitest";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { SectionVersionValidateClient, parseSectionVersionValidationReport } from "./sectionVersionValidateClient";

const project = "01234567-89ab-4cde-8123-456789abcdef";
const section = "11234567-89ab-4cde-8123-456789abcdef";
const version = "21234567-89ab-4cde-8123-456789abcdef";
const audit = "31234567-89ab-4cde-8123-456789abcdef";
const trace = "41234567-89ab-4cde-8123-456789abcdef";
const observedTrace = "51234567-89ab-4cde-8123-456789abcdef";
const key = "61234567-89ab-4cde-8123-456789abcdef";
const facts = { integrity: "PASS", content: "PASS", requirements: "PASS", evidence: "PASS",
  trace: "UNAVAILABLE", spec: "UNAVAILABLE" };
const report = { audit_event_id: audit, observation_trace_id: observedTrace,
  project_id: project, solution_section_id: section, solution_section_version_id: version,
  version_no: 1, version_state: "DRAFT", content_fingerprint: "a".repeat(64),
  requirement_count: 1, evidence_count: 1, facts,
  valid: true, ready_for_review: false,
  issue_codes: ["TRACE_COVERAGE_UNAVAILABLE", "STRUCTURED_SPEC_UNAVAILABLE"],
  observed_at: "2026-10-12T00:00:00Z" };
function response(data: unknown = report, status = 200): Response {
  return new Response(JSON.stringify(status === 200 ? { data, trace_id: trace }
    : { error: { code: data, message: "synthetic" }, trace_id: trace }), { status,
    headers: { "Content-Type": "application/json", "Cache-Control": "no-store",
      "X-Trace-Id": trace } });
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
  return { client: new SectionVersionValidateClient(session), fetcher };
}

describe("SectionVersionValidateClient", () => {
  afterEach(() => vi.restoreAllMocks());

  it("sends a bodyless authorized POST and preserves audited six-dimension report", async () => {
    const { client, fetcher } = await setup();
    expect(await client.validate(project, section, version, key)).toEqual(report);
    expect(fetcher).toHaveBeenCalledTimes(2);
    expect(fetcher.mock.calls[1]?.[0]).toBe(
      `/api/v1/projects/${project}/solution-sections/${section}/versions/${version}:validate`);
    expect(fetcher.mock.calls[1]?.[1]).toMatchObject({ method: "POST",
      credentials: "same-origin", cache: "no-store", redirect: "error",
      headers: expect.objectContaining({ "Idempotency-Key": key, "X-CSRF-Token": "a".repeat(64) }) });
    expect(fetcher.mock.calls[1]?.[1].body).toBeUndefined();
    expect(fetcher.mock.calls[1]?.[1].headers["Content-Type"]).toBeUndefined();
  });

  it("rejects non-writers and malformed identities before network POST", async () => {
    const reader = await setup("CUSTOMER_MEMBER");
    await expect(reader.client.validate(project, section, version, key)).rejects.toMatchObject({
      code: "SECTION_VERSION_VALIDATE_INVALID" });
    expect(reader.fetcher).toHaveBeenCalledTimes(1);
    const member = await setup("IMPLEMENTATION_MEMBER");
    expect(await member.client.validate(project, section, version, key)).toEqual(report);
    const manager = await setup();
    for (const args of [["bad", section, version, key], [project, "bad", version, key],
      [project, section, "bad", key], [project, section, version, "short"]] as const) {
      await expect(manager.client.validate(args[0], args[1], args[2], args[3])).rejects.toMatchObject({
        code: "SECTION_VERSION_VALIDATE_INVALID" });
    }
    expect(manager.fetcher).toHaveBeenCalledTimes(1);
  });

  it("fails closed on contradictory or cross-project reports", () => {
    for (const bad of [
      { ...report, project_id: section },
      { ...report, facts: { ...facts, content: "UNAVAILABLE" } },
      { ...report, ready_for_review: true },
      { ...report, issue_codes: [] },
      { ...report, facts: { ...facts, trace: "MAYBE" } },
      { ...report, version_state: "APPROVED" },
      { ...report, content_fingerprint: "bad" },
      { ...report, observed_at: "2026-02-30T00:00:00Z" },
    ]) expect(() => parseSectionVersionValidationReport(bad, project, section, version))
      .toThrowError(expect.objectContaining({ code: "SECTION_VERSION_VALIDATE_UNCERTAIN" }));
  });

  it("maps confirmed errors; transport or malformed reply retains original key as uncertain", async () => {
    for (const [code, status] of [["LICENSE_OPERATION_DENIED", 403],
      ["RESOURCE_NOT_FOUND", 404], ["CONFLICT_IDEMPOTENCY", 409]] as const) {
      const { client } = await setup("PROJECT_MANAGER", response(code, status));
      await expect(client.validate(project, section, version, key)).rejects.toMatchObject({ code });
    }
    const unavailable = await setup("PROJECT_MANAGER", response("SYSTEM_UNAVAILABLE", 503));
    await expect(unavailable.client.validate(project, section, version, key)).rejects.toMatchObject({
      code: "SYSTEM_UNAVAILABLE", uncertain: true });
    const wrong = await setup("PROJECT_MANAGER", response({ ...report, valid: false }));
    await expect(wrong.client.validate(project, section, version, key)).rejects.toMatchObject({
      code: "SECTION_VERSION_VALIDATE_UNCERTAIN", uncertain: true });
    const failed = await setup();
    failed.fetcher.mockReset(); failed.fetcher.mockRejectedValueOnce(new Error("disconnect"));
    await expect(failed.client.validate(project, section, version, key)).rejects.toMatchObject({
      code: "SECTION_VERSION_VALIDATE_UNCERTAIN", uncertain: true });
    expect(failed.fetcher).toHaveBeenCalledTimes(1);
  });
});
