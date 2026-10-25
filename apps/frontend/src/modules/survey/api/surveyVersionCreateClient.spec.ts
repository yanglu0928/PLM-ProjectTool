import { describe, expect, it, vi } from "vitest";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { SurveyVersionCreateClient, handoverItemSource, manualSurveySource,
  type SurveyVersionCreateInput } from "./surveyVersionCreateClient";

const project = "01234567-89ab-4cde-8123-456789abcdef";
const survey = "11234567-89ab-4cde-8123-456789abcdef";
const version = "21234567-89ab-4cde-8123-456789abcdef";
const actor = "31234567-89ab-4cde-8123-456789abcdef";
const question = "41234567-89ab-4cde-8123-456789abcdef";
const department = "51234567-89ab-4cde-8123-456789abcdef";
const row = "61234567-89ab-4cde-8123-456789abcdef";
const analysis = "71234567-89ab-4cde-8123-456789abcdef";
const handoverVersion = "81234567-89ab-4cde-8123-456789abcdef";
const trace = "91234567-89ab-4cde-8123-456789abcdef";
const csrf = "a".repeat(64);
const key = "survey-version-create-001";
const path = `/api/v1/projects/${project}/surveys/${survey}/versions`;
const input: SurveyVersionCreateInput = { questions: [{ question_id: question,
  topic: "实施现状", question_text: "现场实际如何执行？", objective: "记录真实访谈结论",
  answer_type: "TEXT", validation_rule: {}, required: true, condition_rule: null,
  expected_output: "客户实际流程记录", evidence_required: false, options: [],
  sources: [handoverItemSource({ handover_item_row_id: row,
    handover_analysis_version_id: handoverVersion,
    handover_analysis_id: analysis })] }], target_department_ids: [department] };
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
function sessionData(role: string) {
  return { user: { user_id: actor, username_display: "合成负责人" }, deployment_role: "NONE",
    password_change_required: false, authorized_projects: [{ project_id: project,
      name: "合成项目", role }], absolute_expires_at: "2030-01-01T12:00:00Z",
    idle_expires_at: "2030-01-01T11:00:00Z", csrf_token: csrf };
}
function created(overrides: Record<string, unknown> = {}) {
  return { survey_version_id: version, survey_id: survey, project_id: project,
    version_no: 1, state: "DRAFT", content_fingerprint: "a".repeat(64),
    supersedes_version_ref: null, created_at: "2026-10-25T12:00:00Z",
    survey_etag: '"v1"', ...overrides };
}
async function fixture(result: Response | Error, role = "PROJECT_MANAGER") {
  const fetcher = vi.fn().mockResolvedValueOnce(response(sessionData(role)));
  if (result instanceof Error) fetcher.mockRejectedValueOnce(result);
  else fetcher.mockResolvedValueOnce(result);
  const session = new SessionClient(fetcher as typeof fetch);
  await session.login("synthetic", "synthetic-only");
  return { client: new SurveyVersionCreateClient(session), fetcher };
}

describe("SurveyVersionCreateClient", () => {
  it("sends frozen complete snapshot through private CSRF/If-Match/original key", async () => {
    const { client, fetcher } = await fixture(response(created(), 201,
      { ETag: '"v1"', Location: `${path}/${version}` }));
    await expect(client.create(project, survey, '"v0"', input, key)).resolves.toMatchObject({
      survey_version_id: version, state: "DRAFT", survey_etag: '"v1"' });
    expect(fetcher.mock.calls[1]).toEqual([path, expect.objectContaining({
      method: "POST", credentials: "same-origin", cache: "no-store", redirect: "error",
      body: JSON.stringify(input), headers: { Accept: "application/json",
        "Content-Type": "application/json", "X-CSRF-Token": csrf,
        "If-Match": '"v0"', "Idempotency-Key": key },
    })]);
  });

  it("supports explicit manual interview note without pretending fixed Handover", async () => {
    const note = manualSurveySource("访谈记录由实施顾问现场形成，待客户核对。");
    expect(note.source_kind).toBe("MANUAL");
    expect(note.handover_item_row_id).toBeNull();
    expect(() => manualSurveySource(" ")).toThrow();
    const { client } = await fixture(response(created(), 201,
      { ETag: '"v1"', Location: `${path}/${version}` }));
    const manual = { ...input, questions: [{ ...input.questions[0]!, sources: [note] }] };
    await expect(client.create(project, survey, '"v0"', manual, key)).resolves.toMatchObject({
      survey_version_id: version });
  });

  it("rejects customer role, malformed source and missing targets before write", async () => {
    const denied = await fixture(response(created(), 201,
      { ETag: '"v1"', Location: `${path}/${version}` }), "CUSTOMER_MEMBER");
    await expect(denied.client.create(project, survey, '"v0"', input, key)).rejects.toMatchObject({
      code: "RESOURCE_NOT_FOUND" });
    await expect(denied.client.create(project, survey, '"v0"',
      { ...input, target_department_ids: [] }, key)).rejects.toMatchObject({ code: "INVALID_INPUT" });
    const fakeSource = { ...input.questions[0]!.sources[0]!, handover_item_row_id: null };
    await expect(denied.client.create(project, survey, '"v0"',
      { ...input, questions: [{ ...input.questions[0]!, sources: [fakeSource] }] }, key))
      .rejects.toMatchObject({ code: "INVALID_INPUT" });
    expect(denied.fetcher).toHaveBeenCalledTimes(1);
  });

  it("maps known source rejection and preserves original key on transport uncertainty", async () => {
    const sourceLost = await fixture(failure(422, "VALIDATION_FAILED"));
    await expect(sourceLost.client.create(project, survey, '"v0"', input, key))
      .rejects.toMatchObject({ code: "VALIDATION_FAILED", uncertain: false });
    const lost = await fixture(new Error("synthetic network loss"));
    await expect(lost.client.create(project, survey, '"v0"', input, key))
      .rejects.toMatchObject({ code: "UNCERTAIN", uncertain: true });
    expect(lost.fetcher).toHaveBeenCalledTimes(2);
  });

  it("fails closed on wrong receipt identity, ETag, Location or trace", async () => {
    for (const result of [
      response(created({ survey_id: actor }), 201,
        { ETag: '"v1"', Location: `${path}/${version}` }),
      response(created(), 201, { ETag: '"v2"', Location: `${path}/${version}` }),
      response(created(), 201, { ETag: '"v1"', Location: `${path}/${actor}` }),
      response(created(), 201, { ETag: '"v1"', Location: `${path}/${version}`,
        "X-Trace-Id": actor }),
    ]) {
      const { client } = await fixture(result);
      await expect(client.create(project, survey, '"v0"', input, key))
        .rejects.toMatchObject({ code: "UNCERTAIN" });
    }
  });
});
