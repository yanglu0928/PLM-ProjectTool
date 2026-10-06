import { afterEach, describe, expect, it, vi } from "vitest";
import { SurveyReadClient, SurveyReadError, parseSurveyVersion,
  type SurveyCursor, type SurveyVersionCursor } from "./surveyReadClient";

const project = "01234567-89ab-4cde-8123-456789abcdef";
const survey = "11234567-89ab-4cde-8123-456789abcdef";
const version = "21234567-89ab-4cde-8123-456789abcdef";
const actor = "31234567-89ab-4cde-8123-456789abcdef";
const question = "41234567-89ab-4cde-8123-456789abcdef";
const department = "51234567-89ab-4cde-8123-456789abcdef";
const document = "61234567-89ab-4cde-8123-456789abcdef";
const documentVersion = "71234567-89ab-4cde-8123-456789abcdef";
const trace = "81234567-89ab-4cde-8123-456789abcdef";
const now = "2026-10-06T12:00:00.000000Z";
const token = `${"A".repeat(24)}.${"B".repeat(43)}`;
const surveyView = { survey_id: survey, project_id: project, name: "现状调研", state: "ACTIVE",
  current_approved_version_ref: null, created_by: actor, created_at: now, updated_by: null, updated_at: now, etag: '"v0"' };
const source = { source_kind: "TEMPLATE_DOCUMENT_VERSION", handover_item_row_id: null,
  handover_analysis_version_id: null, handover_analysis_id: null, capability_item_row_id: null,
  capability_baseline_version_id: null, capability_baseline_id: null,
  template_document_version_id: documentVersion, template_document_id: document, manual_source_note: null, ordinal: 0 };
const questionView = { question_id: question, sequence_no: 0, topic: "审批流程", question_text: "当前审批如何执行？",
  objective: "确认现状", answer_type: "SINGLE_CHOICE", validation_rule: {}, required: true,
  condition_rule: null, expected_output: "已确认的实际流程", evidence_required: true,
  options: [{ option_code: "MANUAL", label: "人工审批", description: null, ordinal: 0 },
    { option_code: "SYSTEM", label: "系统审批", description: "由系统执行", ordinal: 1 }], sources: [source] };
const versionView = { survey_version_id: version, survey_id: survey, project_id: project, version_no: 1,
  state: "DRAFT", content_fingerprint: "a".repeat(64), declared_question_count: 1, declared_option_count: 2,
  declared_source_count: 1, declared_target_department_count: 1, supersedes_version_ref: null,
  review_ref: null, review_round_ref: null, created_by: actor, created_at: now, questions: [questionView],
  target_departments: [{ department_id: department, ordinal: 0 }] };

function ok(data: unknown, headerEtag?: string): Response {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (headerEtag) headers.ETag = headerEtag;
  return new Response(JSON.stringify({ data, trace_id: trace }), { status: 200, headers });
}
function failure(status: number, code: string): Response {
  return new Response(JSON.stringify({ error: { code, message: "private" }, trace_id: trace }),
    { status, headers: { "Content-Type": "application/json" } });
}
function client(...responses: Response[]) {
  const fetcher = vi.fn(); for (const response of responses) fetcher.mockResolvedValueOnce(response);
  return { api: new SurveyReadClient(fetcher as typeof fetch), fetcher };
}

describe("SurveyReadClient", () => {
  afterEach(() => { vi.restoreAllMocks(); vi.useRealTimers(); });

  it("reads Survey page/detail with safe transport and matching ETag", async () => {
    const { api, fetcher } = client(ok({ items: [surveyView], next_cursor: token, has_more: true }),
      ok(surveyView, '"v0"'));
    const page = await api.listSurveys(project, 25);
    expect(fetcher.mock.calls[0]).toEqual([`/api/v1/projects/${project}/surveys?page_size=25`, expect.objectContaining({
      method: "GET", credentials: "same-origin", cache: "no-store", redirect: "error",
      headers: { Accept: "application/json" },
    })]);
    expect(page.next_cursor).toBe(token); expect(Object.isFrozen(page.items[0])).toBe(true);
    await expect(api.getSurvey(project, survey)).resolves.toMatchObject({ name: "现状调研", etag: '"v0"' });
  });

  it("passes both branded opaque cursors without decoding and keeps parent paths", async () => {
    const { api, fetcher } = client(ok({ items: [], next_cursor: null, has_more: false }),
      ok({ items: [], next_cursor: null, has_more: false }));
    await api.listSurveys(project, 50, token as SurveyCursor);
    await api.listVersions(project, survey, 50, token as SurveyVersionCursor);
    expect(fetcher.mock.calls.map(call => call[0])).toEqual([
      `/api/v1/projects/${project}/surveys?page_size=50&cursor=${token}`,
      `/api/v1/projects/${project}/surveys/${survey}/versions?page_size=50&cursor=${token}`,
    ]);
  });

  it("reads fixed Version detail including zero-based questions and typed source", async () => {
    const value = await client(ok(versionView)).api.getVersion(project, survey, version);
    expect(value.questions[0]).toMatchObject({ sequence_no: 0, answer_type: "SINGLE_CHOICE",
      sources: [{ source_kind: "TEMPLATE_DOCUMENT_VERSION", template_document_id: document }] });
    expect(value.target_departments).toEqual([{ department_id: department, ordinal: 0 }]);
    expect(Object.isFrozen(value.questions[0]!.sources)).toBe(true);
  });

  it("accepts bounded V1 validation and condition rule shapes", () => {
    const earlier = { ...questionView, question_id: actor, answer_type: "TEXT", options: [],
      validation_rule: { min_length: 1, max_length: 2000 }, sources: [{ ...source, source_kind: "MANUAL",
        template_document_version_id: null, template_document_id: null, manual_source_note: "客户现场访谈记录第3项" }] };
    const dependent = { ...questionView, sequence_no: 1, condition_rule: { all: [
      { question_ref: actor, operator: "ANSWERED" }, { question_ref: actor, operator: "NOT_EQUALS", value: "未说明" }] } };
    const view = { ...versionView, declared_question_count: 2, declared_option_count: 2,
      declared_source_count: 2, questions: [earlier, dependent] };
    const parsed = parseSurveyVersion(view, project, survey, version);
    expect(parsed.questions[1]!.condition_rule).toMatchObject({ all: expect.any(Array) });
    expect(Object.isFrozen(parsed.questions[1]!.condition_rule?.all)).toBe(true);
  });

  it.each([
    { ...versionView, private_path: "D:/secret" },
    { ...versionView, declared_option_count: 1 },
    { ...versionView, questions: [{ ...questionView, sequence_no: 1 }] },
    { ...versionView, questions: [{ ...questionView, validation_rule: { unknown: true } }] },
    { ...versionView, questions: [{ ...questionView, answer_type: "DATE", options: [],
      validation_rule: { minimum: "2026-02-31" } }], declared_option_count: 0 },
    { ...versionView, questions: [{ ...questionView, condition_rule: { question_ref: actor,
      operator: "IN", value: ["A", "A"] } }] },
    { ...versionView, questions: [{ ...questionView, sources: [{ ...source, manual_source_note: "copied body" }] }] },
    { ...versionView, target_departments: [{ department_id: department, ordinal: 2 }] },
  ])("rejects unsafe or inconsistent Version projection %#", bad => {
    expect(() => parseSurveyVersion(bad, project, survey, version)).toThrowError(SurveyReadError);
  });

  it("rejects page order, duplicate identities and cursor replay", async () => {
    const older = { ...surveyView, survey_id: actor, updated_at: "2026-10-06T11:00:00Z" };
    await expect(client(ok({ items: [older, surveyView], next_cursor: null, has_more: false })).api.listSurveys(project))
      .rejects.toMatchObject({ code: "SURVEY_READ_UNAVAILABLE" });
    await expect(client(ok({ items: [versionView, versionView], next_cursor: null, has_more: false })).api
      .listVersions(project, survey)).rejects.toMatchObject({ code: "SURVEY_READ_UNAVAILABLE" });
    await expect(client(ok({ items: [surveyView], next_cursor: token, has_more: true })).api
      .listSurveys(project, 50, token as SurveyCursor)).rejects.toMatchObject({ code: "SURVEY_READ_UNAVAILABLE" });
  });

  it.each(["../admin", project.toUpperCase(), "00000000-0000-0000-0000-000000000000"])(
    "rejects unsafe ids before network: %s", async bad => {
      const { api, fetcher } = client(ok({ items: [], next_cursor: null, has_more: false }));
      await expect(api.listSurveys(bad)).rejects.toMatchObject({ code: "SURVEY_READ_INVALID_INPUT" });
      await expect(api.getVersion(project, survey, bad)).rejects.toMatchObject({ code: "SURVEY_READ_INVALID_INPUT" });
      expect(fetcher).not.toHaveBeenCalled();
    });

  it.each([0, 201, 1.5, Number.NaN])("rejects invalid page size %s", async size => {
    const { api, fetcher } = client(ok({ items: [], next_cursor: null, has_more: false }));
    await expect(api.listVersions(project, survey, size)).rejects.toMatchObject({ code: "SURVEY_READ_INVALID_INPUT" });
    expect(fetcher).not.toHaveBeenCalled();
  });

  it.each([[401, "AUTH_SESSION_EXPIRED"], [403, "LICENSE_OPERATION_DENIED"], [404, "RESOURCE_NOT_FOUND"],
    [409, "PROJECT_ARCHIVED"]] as const)("maps only matching safe error %s %s", async (status, code) => {
    await expect(client(failure(status, code)).api.getSurvey(project, survey)).rejects.toMatchObject({ code });
  });

  it("fails closed on wrong ETag, extra envelope field, content type and timeout", async () => {
    await expect(client(ok(surveyView, '"v9"')).api.getSurvey(project, survey))
      .rejects.toMatchObject({ code: "SURVEY_READ_UNAVAILABLE" });
    const extra = new Response(JSON.stringify({ data: surveyView, trace_id: trace, private: true }),
      { status: 200, headers: { "Content-Type": "application/json", ETag: '"v0"' } });
    await expect(client(extra).api.getSurvey(project, survey)).rejects.toMatchObject({ code: "SURVEY_READ_UNAVAILABLE" });
    await expect(client(new Response("x", { status: 200, headers: { "Content-Type": "text/html" } })).api
      .getSurvey(project, survey)).rejects.toMatchObject({ code: "SURVEY_READ_UNAVAILABLE" });
    vi.useFakeTimers(); const api = new SurveyReadClient(vi.fn((_path, init) => new Promise((_resolve, reject) => {
      init?.signal?.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")));
    })) as typeof fetch, 5);
    const pending = api.getSurvey(project, survey); const assertion = expect(pending).rejects
      .toMatchObject({ code: "SURVEY_READ_UNAVAILABLE" });
    await vi.advanceTimersByTimeAsync(5); await assertion;
  });
});
