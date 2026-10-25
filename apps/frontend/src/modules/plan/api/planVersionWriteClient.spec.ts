import { afterEach, describe, expect, it, vi } from "vitest";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { PlanVersionWriteClient } from "./planVersionWriteClient";

const actor = "01234567-89ab-4cde-8123-456789abcdef";
const project = "11234567-89ab-4cde-8123-456789abcdef";
const plan = "21234567-89ab-4cde-8123-456789abcdef";
const version = "31234567-89ab-4cde-8123-456789abcdef";
const reviewer = "41234567-89ab-4cde-8123-456789abcdef";
const trace = "51234567-89ab-4cde-8123-456789abcdef";
const key = "plan-version-original-key-0001";
const csrf = "a".repeat(64);
const draft = { approved_solution_refs: [], wbs_items: [], dependencies: [], milestones: [], calendar_ref: null, exclusions: [] };
const coverage = { requirement_total: 0, requirement_mapped: 0, requirement_excluded: 0, requirement_uncovered: 0,
  solution_total: 0, solution_mapped: 0, solution_excluded: 0, solution_uncovered: 0 };
const created = { plan_version_id: version, plan_id: plan, project_id: project, version_no: 1,
  version_state: "DRAFT", created_at: "2026-10-26T01:02:03Z" };
const report = { valid: false, blocking_issues: ["WBS_EMPTY"], warnings: [], coverage_summary: coverage,
  checked_at: "2026-10-26T01:02:03Z" };
const submission = { review_id: "61234567-89ab-4cde-8123-456789abcdef",
  review_round_id: "71234567-89ab-4cde-8123-456789abcdef", subject_type: "PLN-02", project_id: project,
  plan_id: plan, plan_version_id: version, policy_ref: "PLAN_VERSION_ALL_V1", reviewer_ids: [reviewer],
  state: "IN_REVIEW", round_no: 1, review_etag: '"v1"', submitted_by: actor, submitted_at: "2026-10-26T01:02:03Z" };
function response(data: unknown, status = 200, headers: Record<string, string> = {}) {
  return new Response(JSON.stringify({ data, trace_id: trace }), { status, headers: {
    "Content-Type": "application/json", "Cache-Control": "no-store", "X-Trace-Id": trace, ...headers,
  } });
}
function sessionResponse(role = "PROJECT_MANAGER") {
  return response({ user: { user_id: actor, username_display: "合成计划负责人" }, deployment_role: "NONE",
    password_change_required: false, authorized_projects: [{ project_id: project, name: "合成项目", role }],
    absolute_expires_at: "2030-01-01T12:00:00Z", idle_expires_at: "2030-01-01T11:00:00Z", csrf_token: csrf });
}
async function setup(responses: Response[], role = "PROJECT_MANAGER") {
  const fetcher = vi.fn(); fetcher.mockResolvedValueOnce(sessionResponse(role));
  for (const item of responses) fetcher.mockResolvedValueOnce(item);
  const session = new SessionClient(fetcher as typeof fetch);
  await session.login("user", "synthetic-only");
  return { client: new PlanVersionWriteClient(session), session, fetcher };
}

describe("PlanVersionWriteClient", () => {
  afterEach(() => vi.restoreAllMocks());

  it("creates one immutable snapshot through the bounded same-origin bridge", async () => {
    const { client, fetcher } = await setup([response(created, 201, { Location:
      `/api/v1/projects/${project}/plans/${plan}/versions/${version}` })]);
    await expect(client.create(project, plan, draft, key)).resolves.toMatchObject({ ...created, version_state: "DRAFT" });
    expect(fetcher.mock.calls[1]?.[0]).toBe(`/api/v1/projects/${project}/plans/${plan}/versions`);
    expect(fetcher.mock.calls[1]?.[1]).toMatchObject({ method: "POST", credentials: "same-origin",
      cache: "no-store", redirect: "error", body: JSON.stringify(draft), headers: {
        "X-CSRF-Token": csrf, "Idempotency-Key": key, "Content-Type": "application/json",
      } });
  });

  it("validates with a bodyless request and preserves the complete current-snapshot report", async () => {
    const { client, fetcher } = await setup([response(report)]);
    await expect(client.validate(project, plan, version, key)).resolves.toMatchObject(report);
    expect(fetcher.mock.calls[1]?.[0]).toBe(`/api/v1/projects/${project}/plans/${plan}/versions/${version}:validate`);
    expect(fetcher.mock.calls[1]?.[1]).toMatchObject({ method: "POST", credentials: "same-origin",
      headers: { "X-CSRF-Token": csrf, "Idempotency-Key": key } });
    expect(fetcher.mock.calls[1]?.[1]).not.toHaveProperty("body");
  });

  it("submits one fixed atomic review request and does not report approval", async () => {
    const { client, fetcher } = await setup([response(submission, 201, { ETag: '"v1"' })]);
    await expect(client.submitReview(project, plan, version, [reviewer], key)).resolves.toMatchObject(submission);
    expect(fetcher.mock.calls[1]?.[0]).toBe(`/api/v1/projects/${project}/plans/${plan}/versions/${version}:submit-review`);
    expect(fetcher.mock.calls[1]?.[1]).toMatchObject({ method: "POST", body: JSON.stringify({ reviewer_ids: [reviewer],
      policy_ref: "PLAN_VERSION_ALL_V1", due_at: null, submission_note: null }), headers: {
      "X-CSRF-Token": csrf, "Idempotency-Key": key,
    } });
  });

  it("rejects malformed contracts, unapproved roles and invalid request identities before write", async () => {
    const { client: reader, fetcher } = await setup([], "CUSTOMER_MEMBER");
    await expect(reader.create(project, plan, draft, key)).rejects.toMatchObject({ code: "PLAN_VERSION_WRITE_INVALID" });
    await expect(reader.validate(project, plan, version, key)).rejects.toMatchObject({ code: "PLAN_VERSION_WRITE_INVALID" });
    await expect(reader.submitReview(project, plan, version, [reviewer], key)).rejects.toMatchObject({ code: "PLAN_VERSION_WRITE_INVALID" });
    expect(fetcher).toHaveBeenCalledTimes(1);

    const { client: manager } = await setup([response({ ...created, plan_id: project }, 201, { Location:
      `/api/v1/projects/${project}/plans/${plan}/versions/${version}` })]);
    await expect(manager.create(project, plan, draft, key)).rejects.toMatchObject({ code: "PLAN_VERSION_WRITE_UNCERTAIN" });
  });

  it("keeps uncertain network writes single-attempt and rejects invalid validation reports", async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(sessionResponse());
    const session = new SessionClient(fetcher as typeof fetch); await session.login("user", "synthetic-only");
    fetcher.mockRejectedValueOnce(new Error("synthetic network interruption"));
    const client = new PlanVersionWriteClient(session);
    await expect(client.create(project, plan, draft, key)).rejects.toMatchObject({ code: "PLAN_VERSION_WRITE_UNCERTAIN", uncertain: true });
    expect(fetcher).toHaveBeenCalledTimes(2);

    const malformed = { ...report, coverage_summary: { ...coverage, solution_total: -1 } };
    const other = await setup([response(malformed)]);
    await expect(other.client.validate(project, plan, version, key)).rejects.toMatchObject({ code: "PLAN_VERSION_WRITE_UNCERTAIN" });
  });
});
