import { describe, expect, it, vi } from "vitest";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { OutlineReviewSubmitError, OutlineVersionSubmitReviewClient } from
  "./outlineVersionSubmitReviewClient";

const project = "01234567-89ab-4cde-8123-456789abcdef";
const outline = "11234567-89ab-4cde-8123-456789abcdef";
const version = "21234567-89ab-4cde-8123-456789abcdef";
const reviewer = "31234567-89ab-4cde-8123-456789abcdef";
const actor = "41234567-89ab-4cde-8123-456789abcdef";
const review = "51234567-89ab-4cde-8123-456789abcdef";
const round = "61234567-89ab-4cde-8123-456789abcdef";
const trace = "71234567-89ab-4cde-8123-456789abcdef";
const receipt = { review_id: review, review_round_id: round,
  subject_type: "SOL-03", project_id: project, solution_outline_id: outline,
  solution_outline_version_id: version, policy_ref: "SOLUTION_OUTLINE_ALL_V1",
  reviewer_ids: [reviewer], state: "IN_REVIEW", round_no: 1,
  review_etag: '"v1"', submitted_by: actor,
  submitted_at: "2026-10-24T00:00:00Z" };
function response(data: unknown, status = 201, etag = '"v1"') {
  return new Response(JSON.stringify(status === 201
    ? { data, trace_id: trace }
    : { error: { code: data, message: "safe" }, trace_id: trace }),
  { status, headers: { "Content-Type": "application/json", "Cache-Control": "no-store",
    "X-Trace-Id": trace, ETag: etag } });
}
async function setup(role = "PROJECT_MANAGER", write = response(receipt)) {
  const login = new Response(JSON.stringify({ data: {
    user: { user_id: actor, username_display: "合成负责人" }, deployment_role: "NONE",
    password_change_required: false,
    authorized_projects: [{ project_id: project, name: "项目", role }],
    absolute_expires_at: "2030-01-01T12:00:00Z",
    idle_expires_at: "2030-01-01T11:00:00Z", csrf_token: "a".repeat(64),
  }, trace_id: trace }), { status: 200, headers: { "Content-Type": "application/json" } });
  const fetcher = vi.fn().mockResolvedValueOnce(login).mockResolvedValueOnce(write);
  const session = new SessionClient(fetcher as typeof fetch);
  await session.login("manager", "synthetic-only");
  return { api: new OutlineVersionSubmitReviewClient(session), fetcher };
}
describe("OutlineVersionSubmitReviewClient", () => {
  it("sends frozen SOL-03 request and accepts exact 201 receipt", async () => {
    const { api, fetcher } = await setup();
    await expect(api.submit(project, outline, version, [reviewer],
      "outline-review-0001")).resolves.toMatchObject(receipt);
    expect(fetcher.mock.calls[1]).toEqual([
      `/api/v1/projects/${project}/solution-outlines/${outline}/versions/${version}:submit-review`,
      expect.objectContaining({ method: "POST", credentials: "same-origin",
        body: JSON.stringify({ reviewer_ids: [reviewer],
          policy_ref: "SOLUTION_OUTLINE_ALL_V1", due_at: null, submission_note: null }),
        headers: expect.objectContaining({ "Idempotency-Key": "outline-review-0001" }) }),
    ]);
  });
  it("refuses non-manager, duplicate reviewer and wrong subject/policy/ETag", async () => {
    const customer = await setup("CUSTOMER_MEMBER");
    await expect(customer.api.submit(project, outline, version, [reviewer],
      "outline-review-0001")).rejects.toMatchObject({ code: "OUTLINE_REVIEW_INVALID" });
    expect(customer.fetcher).toHaveBeenCalledTimes(1);
    const manager = await setup();
    await expect(manager.api.submit(project, outline, version, [reviewer, reviewer],
      "outline-review-0001")).rejects.toMatchObject({ code: "OUTLINE_REVIEW_INVALID" });
    for (const write of [response({ ...receipt, subject_type: "SOL-05" }),
      response({ ...receipt, policy_ref: "SOLUTION_SECTION_ALL_V1" }),
      response(receipt, 201, '"v2"')]) {
      const wrong = await setup("PROJECT_MANAGER", write);
      await expect(wrong.api.submit(project, outline, version, [reviewer],
        "outline-review-0001")).rejects.toBeInstanceOf(OutlineReviewSubmitError);
    }
  });
  it("distinguishes confirmed eligibility denial from uncertain result", async () => {
    const denied = await setup("PROJECT_MANAGER", response("BUSINESS_REVIEW_NOT_ELIGIBLE", 422));
    await expect(denied.api.submit(project, outline, version, [reviewer],
      "outline-review-0001")).rejects.toMatchObject({
        code: "BUSINESS_REVIEW_NOT_ELIGIBLE", uncertain: false });
    const unavailable = await setup("PROJECT_MANAGER", response("SYSTEM_UNAVAILABLE", 503));
    await expect(unavailable.api.submit(project, outline, version, [reviewer],
      "outline-review-0001")).rejects.toMatchObject({
        code: "SYSTEM_UNAVAILABLE", uncertain: true });
  });
});
