import { describe, expect, it, vi } from "vitest";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { SurveyCreateClient, SurveyCreateError, normalizeSurveyName } from "./surveyCreateClient";

const project = "01234567-89ab-4cde-8123-456789abcdef";
const survey = "11234567-89ab-4cde-8123-456789abcdef";
const actor = "21234567-89ab-4cde-8123-456789abcdef";
const trace = "31234567-89ab-4cde-8123-456789abcdef";
const token = "a".repeat(64);
const path = `/api/v1/projects/${project}/surveys`;
const name = "面对面访谈调研";
const key = "survey-create-key-001";
function response(data: unknown, status = 200, headers: Record<string, string> = {}): Response {
  return new Response(JSON.stringify({ data, trace_id: trace }), { status,
    headers: { "Content-Type": "application/json", "Cache-Control": "no-store",
      "X-Trace-Id": trace, ...headers } });
}
function failure(status: number, code: string): Response {
  return new Response(JSON.stringify({ error: { code, message: "private" }, trace_id: trace }),
    { status, headers: { "Content-Type": "application/json", "Cache-Control": "no-store",
      "X-Trace-Id": trace } });
}
function sessionData(role = "PROJECT_MANAGER") {
  return { user: { user_id: actor, username_display: "合成负责人" }, deployment_role: "NONE",
    password_change_required: false, authorized_projects: [{ project_id: project,
      name: "合成项目", role }], absolute_expires_at: "2030-01-01T12:00:00Z",
    idle_expires_at: "2030-01-01T11:00:00Z", csrf_token: token };
}
function created(overrides: Record<string, unknown> = {}) {
  return { survey_id: survey, project_id: project, name, state: "ACTIVE",
    current_approved_version_ref: null, created_at: "2026-10-25T12:00:00Z",
    etag: '"v0"', ...overrides };
}
async function fixture(result: Response | Error, role = "PROJECT_MANAGER") {
  const fetcher = vi.fn().mockResolvedValueOnce(response(sessionData(role)));
  if (result instanceof Error) fetcher.mockRejectedValueOnce(result);
  else fetcher.mockResolvedValueOnce(result);
  const session = new SessionClient(fetcher as typeof fetch);
  await session.login("synthetic", "synthetic-only");
  return { client: new SurveyCreateClient(session), fetcher };
}

describe("SurveyCreateClient", () => {
  it("posts exact name through private Session CSRF/key and verifies receipt", async () => {
    const { client, fetcher } = await fixture(response(created(), 201,
      { ETag: '"v0"', Location: `${path}/${survey}` }));
    await expect(client.create(project, name, key)).resolves.toMatchObject({
      survey_id: survey, project_id: project, state: "ACTIVE" });
    expect(fetcher.mock.calls[1]).toEqual([path, expect.objectContaining({
      method: "POST", credentials: "same-origin", cache: "no-store", redirect: "error",
      body: JSON.stringify({ name }), headers: { Accept: "application/json",
        "Content-Type": "application/json", "X-CSRF-Token": token, "Idempotency-Key": key },
    })]);
  });

  it("accepts an implementation member but rejects read-only roles and invalid input before write", async () => {
    const allowed = await fixture(response(created(), 201,
      { ETag: '"v0"', Location: `${path}/${survey}` }), "IMPLEMENTATION_MEMBER");
    await expect(allowed.client.create(project, name, key)).resolves.toMatchObject({ survey_id: survey });
    const denied = await fixture(response(created(), 201,
      { ETag: '"v0"', Location: `${path}/${survey}` }), "CUSTOMER_MEMBER");
    await expect(denied.client.create(project, name, key)).rejects.toMatchObject({ code: "RESOURCE_NOT_FOUND" });
    await expect(denied.client.create(project, "  ", key)).rejects.toMatchObject({ code: "SURVEY_CREATE_INVALID" });
    await expect(denied.client.create(actor, name, key)).rejects.toMatchObject({ code: "RESOURCE_NOT_FOUND" });
    await expect(denied.client.create(project, name, "short")).rejects.toMatchObject({ code: "SURVEY_CREATE_INVALID" });
    expect(denied.fetcher).toHaveBeenCalledTimes(1);
    expect(normalizeSurveyName(" 访谈记录 ")).toBe("访谈记录");
    expect(() => normalizeSurveyName("\u0000")).toThrow(SurveyCreateError);
    expect(() => normalizeSurveyName("字".repeat(256))).toThrow(SurveyCreateError);
  });

  it("maps known denial exactly and treats transport loss as uncertain without retry", async () => {
    const archived = await fixture(failure(409, "PROJECT_ARCHIVED"));
    await expect(archived.client.create(project, name, key)).rejects.toMatchObject({
      code: "PROJECT_ARCHIVED", uncertain: false });
    const conflict = await fixture(failure(409, "CONFLICT_IDEMPOTENCY"));
    await expect(conflict.client.create(project, name, key)).rejects.toMatchObject({
      code: "CONFLICT_IDEMPOTENCY", uncertain: false });
    const lost = await fixture(new Error("synthetic transport loss"));
    await expect(lost.client.create(project, name, key)).rejects.toMatchObject({
      code: "SURVEY_CREATE_UNCERTAIN", uncertain: true });
    expect(lost.fetcher).toHaveBeenCalledTimes(2);
  });

  it("fails closed on wrong project/name/Location/ETag and missing trace binding", async () => {
    for (const result of [
      response(created({ project_id: actor }), 201, { ETag: '"v0"', Location: `${path}/${survey}` }),
      response(created({ name: "Other" }), 201, { ETag: '"v0"', Location: `${path}/${survey}` }),
      response(created(), 201, { ETag: '"v0"', Location: `${path}/${actor}` }),
      response(created(), 201, { ETag: '"v1"', Location: `${path}/${survey}` }),
      response(created(), 201, { ETag: '"v0"', Location: `${path}/${survey}`, "X-Trace-Id": actor }),
    ]) {
      const { client } = await fixture(result);
      await expect(client.create(project, name, key)).rejects.toMatchObject({
        code: "SURVEY_CREATE_UNCERTAIN" });
    }
  });
});
