import { afterEach, describe, expect, it, vi } from "vitest";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { JobCancelClient, JobCancelError } from "./jobCancelClient";
import type { JobListItem } from "./jobListClient";

const actor = "01234567-89ab-4cde-8123-456789abcdef";
const project = "11234567-89ab-4cde-8123-456789abcdef";
const job = "21234567-89ab-4cde-8123-456789abcdef";
const other = "31234567-89ab-4cde-8123-456789abcdef";
const key = "synthetic-job-cancel-0001";
const before: JobListItem = { job_id: job, job_type: "DOCUMENT_PARSE", owner_module: "document",
  scope: "PROJECT", project_id: project, state: "RUNNING", attempt_count: 1, retryable: false,
  result_ref: null, created_at: "2026-10-02T00:00:00Z", completed_at: null, etag: '"v1"' };
const statusUrl = `/api/v1/projects/${project}/jobs/${job}`;
const receipt = { job_id: job, state: "CANCEL_REQUESTED", changed: true, etag: '"v2"', status_url: statusUrl };
function envelope(data: unknown, status = 200, etag = '"v2"'): Response {
  return new Response(JSON.stringify({ data, trace_id: actor }), { status,
    headers: { "Content-Type": "application/json", ETag: etag } });
}
function failure(status: number, code: string): Response {
  return new Response(JSON.stringify({ error: { code, message: "private server detail" }, trace_id: actor }),
    { status, headers: { "Content-Type": "application/json" } });
}
async function setup(...responses: Response[]) {
  const session = { user: { user_id: actor, username_display: "负责人" }, deployment_role: "NONE",
    password_change_required: false,
    authorized_projects: [{ project_id: project, name: "项目", role: "PROJECT_MANAGER" }],
    absolute_expires_at: "2030-01-01T12:00:00Z", idle_expires_at: "2030-01-01T11:00:00Z",
    csrf_token: "a".repeat(64) };
  const fetcher = vi.fn().mockResolvedValueOnce(envelope(session));
  for (const reply of responses) fetcher.mockResolvedValueOnce(reply);
  const identity = new SessionClient(fetcher as typeof fetch);
  await identity.login("manager", "synthetic-only");
  return { api: new JobCancelClient(identity), identity, fetcher };
}

describe("JobCancelClient", () => {
  afterEach(() => vi.restoreAllMocks());

  it("accepts only a bound first-result receipt, not current state proof", async () => {
    const { api, fetcher } = await setup(envelope({ ...receipt, private: "hidden" }));
    const result = await api.cancel(project, before, key, "用户请求取消");
    expect(result).toEqual({ first_result: receipt, is_current_state_proof: false });
    expect(Object.isFrozen(result)).toBe(true);
    expect(Object.isFrozen(result.first_result)).toBe(true);
    expect(JSON.stringify(result)).not.toContain("hidden");
    expect(fetcher.mock.calls[1][1]).toMatchObject({ headers: {
      "If-Match": '"v1"', "Idempotency-Key": key, "X-CSRF-Token": "a".repeat(64),
    } });
  });

  it("preserves original request on replay even when current Job may be v3", async () => {
    const { api, fetcher } = await setup(envelope(receipt), envelope(receipt));
    const first = await api.cancel(project, before, key, "reason");
    const replay = await api.cancel(project, before, key, "reason");
    expect(replay).toEqual(first);
    expect(replay.is_current_state_proof).toBe(false);
    expect(fetcher.mock.calls[2][1]).toMatchObject({ headers: { "If-Match": '"v1"', "Idempotency-Key": key } });
  });

  it.each([
    [other, before, key, "reason"], [project, { ...before, project_id: other }, key, "reason"],
    [project, { ...before, scope: "GLOBAL" }, key, "reason"],
    [project, { ...before, etag: 'W/"v1"' }, key, "reason"],
    [project, before, "short", "reason"], [project, before, key, "  "],
    [project, before, key, "reason\u200binside"],
  ])("rejects unsafe source before network %#", async (target, source, attemptKey, reason) => {
    const { api, fetcher } = await setup();
    await expect(api.cancel(target, source as JobListItem, attemptKey, reason))
      .rejects.toMatchObject({ code: "JOB_CANCEL_INVALID_INPUT", uncertain: false });
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it.each([
    [401, "AUTH_SESSION_EXPIRED"], [403, "AUTH_CSRF_INVALID"], [403, "LICENSE_OPERATION_DENIED"],
    [404, "RESOURCE_NOT_FOUND"], [409, "CONFLICT_VERSION"], [409, "CONFLICT_IDEMPOTENCY"],
    [400, "REQUEST_MALFORMED"], [422, "VALIDATION_FAILED"], [428, "CONFLICT_VERSION_REQUIRED"],
  ] as const)("maps only known status and code %s %s", async (status, code) => {
    const { api } = await setup(failure(status, code));
    const caught = await api.cancel(project, before, key, "reason").catch((error: unknown) => error);
    expect(caught).toBeInstanceOf(JobCancelError);
    expect(caught).toMatchObject({ code: ["REQUEST_MALFORMED", "VALIDATION_FAILED", "CONFLICT_VERSION_REQUIRED"].includes(code)
      ? "JOB_CANCEL_INVALID_INPUT" : code, uncertain: false });
    expect(String(caught)).not.toContain("private");
  });

  it.each([
    { ...receipt, job_id: other }, { ...receipt, state: "RUNNING" },
    { ...receipt, changed: "true" }, { ...receipt, etag: '"v0"' },
    { ...receipt, status_url: `/api/v1/admin/jobs/${job}` },
    { ...receipt, state: "SUCCEEDED", changed: true },
  ])("rejects mismatched receipt %#", async value => {
    await expect((await setup(envelope(value, 200, value.etag))).api.cancel(project, before, key, "reason"))
      .rejects.toMatchObject({ code: "JOB_CANCEL_UNCERTAIN", uncertain: true });
  });

  it("rejects mismatched ETag, unsafe HTTP and unknown errors without leaking server text", async () => {
    for (const reply of [envelope(receipt, 200, '"v3"'), failure(503, "SYSTEM_UNAVAILABLE"),
      failure(403, "RESOURCE_NOT_FOUND"), new Response("private", { status: 200, headers: { "Content-Type": "text/html" } })]) {
      const caught = await (await setup(reply)).api.cancel(project, before, key, "reason").catch((error: unknown) => error);
      expect(caught).toMatchObject({ code: "JOB_CANCEL_UNCERTAIN", uncertain: true });
      expect(String(caught)).not.toContain("private");
    }
  });

  it("marks transport failure uncertain and never retries", async () => {
    const { api, fetcher } = await setup();
    await expect(api.cancel(project, before, key, "reason"))
      .rejects.toMatchObject({ code: "JOB_CANCEL_UNCERTAIN", uncertain: true });
    expect(fetcher).toHaveBeenCalledTimes(2);
  });
});
