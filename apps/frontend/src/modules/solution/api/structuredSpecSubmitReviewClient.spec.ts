import { afterEach, describe, expect, it, vi } from "vitest";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { StructuredSpecSubmitReviewClient, StructuredSpecSubmitReviewError } from
  "./structuredSpecSubmitReviewClient";

const project = "01234567-89ab-4cde-8123-456789abcdef";
const spec = "11234567-89ab-4cde-8123-456789abcdef";
const series = "21234567-89ab-4cde-8123-456789abcdef";
const actor = "31234567-89ab-4cde-8123-456789abcdef";
const reviewerA = "41234567-89ab-4cde-8123-456789abcdef";
const reviewerB = "51234567-89ab-4cde-8123-456789abcdef";
const review = "61234567-89ab-4cde-8123-456789abcdef";
const round = "71234567-89ab-4cde-8123-456789abcdef";
const trace = "81234567-89ab-4cde-8123-456789abcdef";
const key = "structured-spec-review-0001";
const receipt = { review_id: review, review_round_id: round, subject_type: "SOL-06",
  project_id: project, spec_series_id: series, structured_solution_spec_id: spec,
  policy_ref: "STRUCTURED_SPEC_ALL_V1", reviewer_ids: [reviewerA, reviewerB],
  state: "IN_REVIEW", round_no: 1, review_etag: '"v1"', submitted_by: actor,
  submitted_at: "2026-10-19T04:00:00Z" };

function reply(data: unknown = receipt, status = 201, headers: Record<string, string> = {}) {
  return new Response(JSON.stringify(status === 201 ? { data, trace_id: trace }
    : { error: { code: data, message: "safe" }, trace_id: trace }), { status,
    headers: { "Content-Type": "application/json", "Cache-Control": "no-store",
      "X-Trace-Id": trace, ...(status === 201 ? { ETag: '"v1"' } : {}), ...headers } });
}
async function setup(role = "PROJECT_MANAGER", result: Response | Error = reply()) {
  const login = new Response(JSON.stringify({ data: { user: { user_id: actor,
    username_display: "负责人" }, deployment_role: "NONE", password_change_required: false,
    authorized_projects: [{ project_id: project, name: "项目", role }],
    absolute_expires_at: "2030-01-01T12:00:00Z", idle_expires_at: "2030-01-01T11:00:00Z",
    csrf_token: "a".repeat(64) }, trace_id: trace }),
  { status: 200, headers: { "Content-Type": "application/json" } });
  const fetcher = vi.fn().mockResolvedValueOnce(login);
  if (result instanceof Error) fetcher.mockRejectedValueOnce(result);
  else fetcher.mockResolvedValueOnce(result);
  const session = new SessionClient(fetcher as typeof fetch);
  await session.login("manager", "synthetic-only");
  return { client: new StructuredSpecSubmitReviewClient(session), fetcher };
}

describe("StructuredSpecSubmitReviewClient", () => {
  afterEach(() => vi.restoreAllMocks());

  it("sends the frozen body with sorted reviewers and accepts the exact 201 receipt", async () => {
    const { client, fetcher } = await setup();
    await expect(client.submit(project, spec, series, [reviewerB, reviewerA], key))
      .resolves.toEqual(receipt);
    expect(fetcher.mock.calls[1]).toEqual([
      `/api/v1/projects/${project}/structured-solution-specs/${spec}:submit-review`,
      expect.objectContaining({ method: "POST", credentials: "same-origin", cache: "no-store",
        redirect: "error", headers: expect.objectContaining({ Accept: "application/json",
          "Content-Type": "application/json", "X-CSRF-Token": "a".repeat(64),
          "Idempotency-Key": key }), body: JSON.stringify({
          reviewer_ids: [reviewerA, reviewerB], policy_ref: "STRUCTURED_SPEC_ALL_V1",
          due_at: null, submission_note: null }) }),
    ]);
  });

  it("fails locally for non-managers, invalid identities, duplicate reviewers or keys", async () => {
    const member = await setup("IMPLEMENTATION_MEMBER");
    await expect(member.client.submit(project, spec, series, [reviewerA], key))
      .rejects.toMatchObject({ code: "STRUCTURED_SPEC_SUBMIT_INVALID" });
    expect(member.fetcher).toHaveBeenCalledTimes(1);
    const manager = await setup();
    for (const args of [
      ["bad", spec, series, [reviewerA], key],
      [project, "bad", series, [reviewerA], key],
      [project, spec, "bad", [reviewerA], key],
      [project, spec, series, [], key],
      [project, spec, series, [reviewerA, reviewerA], key],
      [project, spec, series, [reviewerA], "short"],
    ] as const) {
      const [candidateProject, candidateSpec, candidateSeries, candidateReviewers, candidateKey] = args;
      await expect(manager.client.submit(candidateProject, candidateSpec, candidateSeries,
        candidateReviewers, candidateKey)).rejects.toMatchObject({ code: "STRUCTURED_SPEC_SUBMIT_INVALID" });
    }
    expect(manager.fetcher).toHaveBeenCalledTimes(1);
  });

  it("maps every confirmed server refusal without turning it into an unknown result", async () => {
    for (const [code, status] of [["AUTH_SESSION_EXPIRED", 401], ["AUTH_CSRF_INVALID", 403],
      ["LICENSE_OPERATION_DENIED", 403], ["RESOURCE_NOT_FOUND", 404], ["PROJECT_ARCHIVED", 409],
      ["VALIDATION_FAILED", 422], ["BUSINESS_REVIEW_NOT_ELIGIBLE", 422],
      ["REVIEW_REVIEWER_INELIGIBLE", 422], ["REVIEW_SUBJECT_LOCKED", 409],
      ["CONFLICT_IDEMPOTENCY", 409], ["CONFLICT_VERSION", 409]] as const) {
      const { client } = await setup("PROJECT_MANAGER", reply(code, status));
      await expect(client.submit(project, spec, series, [reviewerA], key))
        .rejects.toMatchObject({ code, uncertain: false });
    }
  });

  it("retains uncertainty for disconnect, 503, malformed identity and response headers", async () => {
    const cases: (Response | Error)[] = [new Error("disconnect"), reply("SYSTEM_UNAVAILABLE", 503),
      reply({ ...receipt, spec_series_id: spec }), reply(receipt, 201, { "Cache-Control": "private" })];
    for (const result of cases) {
      const { client } = await setup("PROJECT_MANAGER", result);
      await expect(client.submit(project, spec, series, [reviewerA, reviewerB], key))
        .rejects.toSatisfy((error: unknown) => error instanceof StructuredSpecSubmitReviewError
          && error.uncertain);
    }
  });
});
