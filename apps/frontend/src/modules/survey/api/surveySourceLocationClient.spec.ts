import { afterEach, describe, expect, it, vi } from "vitest";
import { SurveySourceLocationClient, SurveySourceLocationClientError,
  parseSurveySourceLocation } from "./surveySourceLocationClient";

const project = "01234567-89ab-4cde-8123-456789abcdef";
const survey = "11234567-89ab-4cde-8123-456789abcdef";
const version = "21234567-89ab-4cde-8123-456789abcdef";
const question = "31234567-89ab-4cde-8123-456789abcdef";
const analysis = "41234567-89ab-4cde-8123-456789abcdef";
const analysisVersion = "51234567-89ab-4cde-8123-456789abcdef";
const item = "61234567-89ab-4cde-8123-456789abcdef";
const evidence = "71234567-89ab-4cde-8123-456789abcdef";
const trace = "81234567-89ab-4cde-8123-456789abcdef";
const located = { source_kind: "HANDOVER_ITEM", source_ordinal: 0, resolution_state: "LOCATABLE",
  current_eligibility: true, record_ref: { record_kind: "HANDOVER_ITEM", handover_analysis_id: analysis,
    handover_analysis_version_id: analysisVersion, analysis_item_id: item }, locations: [
      { location_kind: "BUSINESS_RECORD", scope: "PROJECT", project_id: project, handover_analysis_id: analysis,
        handover_analysis_version_id: analysisVersion, analysis_item_id: item },
      { location_kind: "EVIDENCE", scope: "PROJECT", project_id: project, evidence_id: evidence }],
  unavailable_reason: null };
function response(data: unknown, status = 200): Response { return new Response(JSON.stringify(status === 200
  ? { data, trace_id: trace } : { error: { code: data, message: "private" }, trace_id: trace }),
  { status, headers: { "Content-Type": "application/json" } }); }

describe("SurveySourceLocationClient", () => {
  afterEach(() => { vi.restoreAllMocks(); vi.useRealTimers(); });
  it("uses the exact fixed-source path and parses public locations", async () => { const fetcher = vi.fn().mockResolvedValue(response(located));
    const result = await new SurveySourceLocationClient(fetcher as typeof fetch).get(
      project, survey, version, question, 0, "HANDOVER_ITEM");
    expect(fetcher).toHaveBeenCalledWith(`/api/v1/projects/${project}/surveys/${survey}/versions/${version}/questions/${question}/sources/0/location`,
      expect.objectContaining({ method: "GET", credentials: "same-origin", cache: "no-store", redirect: "error" }));
    expect(result.locations[1]).toEqual(expect.objectContaining({ location_kind: "EVIDENCE", evidence_id: evidence }));
    expect(Object.isFrozen(result.locations)).toBe(true);
  });
  it("accepts controlled partial and manual results", () => {
    expect(parseSurveySourceLocation({ source_kind: "CAPABILITY_ITEM", source_ordinal: 1,
      resolution_state: "PARTIALLY_LOCATABLE", current_eligibility: false,
      record_ref: { record_kind: "CAPABILITY_ITEM", baseline_id: analysis,
        baseline_version_id: analysisVersion, capability_item_id: item }, locations: [],
      unavailable_reason: "NO_AUTHORIZED_LOCATION" }, project, "CAPABILITY_ITEM", 1).current_eligibility).toBe(false);
    expect(parseSurveySourceLocation({ source_kind: "MANUAL", source_ordinal: 0,
      resolution_state: "UNAVAILABLE", current_eligibility: false, record_ref: null,
      locations: [], unavailable_reason: "MANUAL_SOURCE_NOT_FIXED" }, project, "MANUAL", 0).record_ref).toBeNull();
  });
  it.each([
    { ...located, private_path: "D:/secret" },
    { ...located, source_ordinal: 1 },
    { ...located, locations: [{ ...located.locations[1], project_id: survey }] },
    { ...located, record_ref: { ...located.record_ref, analysis_item_id: evidence } },
    { ...located, resolution_state: "UNAVAILABLE", locations: [], unavailable_reason: "SOURCE_TARGET_UNAVAILABLE" },
  ])("rejects unsafe or inconsistent projection %#", bad => {
    expect(() => parseSurveySourceLocation(bad, project, "HANDOVER_ITEM", 0)).toThrowError(SurveySourceLocationClientError);
  });
  it("rejects bad input before network and maps only safe errors", async () => { const fetcher = vi.fn(); const api = new SurveySourceLocationClient(fetcher as typeof fetch);
    await expect(api.get(project.toUpperCase(), survey, version, question, 0, "HANDOVER_ITEM"))
      .rejects.toMatchObject({ code: "SURVEY_SOURCE_LOCATION_INVALID_INPUT" }); expect(fetcher).not.toHaveBeenCalled();
    for (const [status, code] of [[401, "AUTH_SESSION_EXPIRED"], [403, "LICENSE_OPERATION_DENIED"],
      [404, "RESOURCE_NOT_FOUND"], [409, "PROJECT_ARCHIVED"]] as const) {
      fetcher.mockResolvedValueOnce(response(code, status));
      await expect(api.get(project, survey, version, question, 0, "HANDOVER_ITEM")).rejects.toMatchObject({ code });
    }
  });
  it("fails closed on envelope, content type and timeout", async () => {
    const extra = new Response(JSON.stringify({ data: located, trace_id: trace, private: true }),
      { headers: { "Content-Type": "application/json" } });
    await expect(new SurveySourceLocationClient(vi.fn().mockResolvedValue(extra) as typeof fetch)
      .get(project, survey, version, question, 0, "HANDOVER_ITEM"))
      .rejects.toMatchObject({ code: "SURVEY_SOURCE_LOCATION_UNAVAILABLE" });
    await expect(new SurveySourceLocationClient(vi.fn().mockResolvedValue(new Response("x",
      { headers: { "Content-Type": "text/html" } })) as typeof fetch)
      .get(project, survey, version, question, 0, "HANDOVER_ITEM"))
      .rejects.toMatchObject({ code: "SURVEY_SOURCE_LOCATION_UNAVAILABLE" });
    vi.useFakeTimers(); const api = new SurveySourceLocationClient(vi.fn((_path, init) => new Promise((_resolve, reject) => {
      init?.signal?.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")));
    })) as typeof fetch, 5); const pending = api.get(project, survey, version, question, 0, "HANDOVER_ITEM");
    const assertion = expect(pending).rejects.toMatchObject({ code: "SURVEY_SOURCE_LOCATION_UNAVAILABLE" });
    await vi.advanceTimersByTimeAsync(5); await assertion;
  });
});
