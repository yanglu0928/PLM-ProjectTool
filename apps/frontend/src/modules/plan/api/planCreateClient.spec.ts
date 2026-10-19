import { afterEach, describe, expect, it, vi } from "vitest";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { PlanCreateClient, normalizePlanName } from "./planCreateClient";

const project = "01234567-89ab-4cde-8123-456789abcdef";
const plan = "11234567-89ab-4cde-8123-456789abcdef";
const trace = "21234567-89ab-4cde-8123-456789abcdef";
const key = "31234567-89ab-4cde-8123-456789abcdef";
const item = { plan_id: plan, project_id: project, name: "实施计划",
  plan_state: "ACTIVE", current_approved_version_ref: null,
  created_at: "2026-10-19T00:00:00Z", etag: '"v0"' };
function response(data: unknown, status = 201, header = '"v0"'): Response {
  return new Response(JSON.stringify({ data, trace_id: trace }), { status,
    headers: { "Content-Type": "application/json", ETag: header, "X-Trace-Id": trace,
      Location: `/api/v1/projects/${project}/plans/${plan}` } });
}
async function setup(role = "PROJECT_MANAGER", result: Response = response(item)) {
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
  return { api: new PlanCreateClient(session), fetcher };
}

describe("PlanCreateClient", () => {
  afterEach(() => vi.restoreAllMocks());
  it("submits exact original key and verifies the full 201 navigation target", async () => {
    const { api, fetcher } = await setup();
    expect(await api.create(project, "实施计划", key)).toEqual(item);
    expect(fetcher).toHaveBeenCalledTimes(2);
    expect(fetcher.mock.calls[1]?.[0]).toBe(`/api/v1/projects/${project}/plans`);
    expect(fetcher.mock.calls[1]?.[1]).toMatchObject({ method: "POST", body: '{"name":"实施计划"}',
      credentials: "same-origin", redirect: "error", headers: expect.objectContaining({
        "Idempotency-Key": key, "X-CSRF-Token": "a".repeat(64) }) });
  });
  it("normalizes the backend NFKC name and refuses reader/external writes", async () => {
    expect(normalizePlanName("  ＡＢ  ")).toBe("AB");
    expect(() => normalizePlanName("\u0000")).toThrow();
    const { api, fetcher } = await setup("CUSTOMER_MEMBER");
    await expect(api.create(project, "实施计划", key)).rejects.toMatchObject({ code: "PLAN_CREATE_INVALID" });
    await expect(api.create(plan, "实施计划", key)).rejects.toMatchObject({ code: "PLAN_CREATE_INVALID" });
    expect(fetcher).toHaveBeenCalledTimes(1);
  });
  it("keeps malformed success, wrong Location/ETag and unknown errors uncertain", async () => {
    for (const bad of [response({ ...item, project_id: plan }), response(item, 201, '"v1"'),
      new Response(JSON.stringify({ data: item, trace_id: trace }), { status: 201,
        headers: { "Content-Type": "application/json", ETag: '"v0"', "X-Trace-Id": trace,
          Location: `/api/v1/projects/${project}/plans/${project}` } }),
      response({ error: { code: "UNKNOWN" } }, 500)]) {
      const { api } = await setup("PROJECT_MANAGER", bad);
      await expect(api.create(project, "实施计划", key)).rejects.toMatchObject({ code: "PLAN_CREATE_UNCERTAIN" });
    }
  });
  it("maps known rejection without assuming commit", async () => {
    const bad = new Response(JSON.stringify({ error: { code: "PROJECT_ARCHIVED" }, trace_id: trace }),
      { status: 409, headers: { "Content-Type": "application/json" } });
    const { api } = await setup("PROJECT_MANAGER", bad);
    await expect(api.create(project, "实施计划", key)).rejects.toMatchObject({ code: "PROJECT_ARCHIVED" });
  });
});
