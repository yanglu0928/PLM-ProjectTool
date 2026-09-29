import { afterEach, describe, expect, it, vi } from "vitest";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { ProjectDepartmentCreateClient, ProjectDepartmentCreateError } from "./projectDepartmentCreateClient";

const actor = "01234567-89ab-4cde-8123-456789abcdef";
const project = "11234567-89ab-4cde-8123-456789abcdef";
const departmentId = "21234567-89ab-4cde-8123-456789abcdef";
const traceId = "31234567-89ab-4cde-8123-456789abcdef";
const key = "synthetic-department-create-0001";
const input = { code: "RD", name: "研发部" };
const created = { department_id: departmentId, ...input, state: "ACTIVE",
  created_at: "2026-09-29T03:00:00.123456Z", etag: '"v0"' };
const location = `/api/v1/projects/${project}/departments/${departmentId}`;
function envelope(data: unknown, status = 201, etag = '"v0"', where = location): Response {
  return new Response(JSON.stringify({ data, trace_id: traceId }), { status,
    headers: { "Content-Type": "application/json", ETag: etag, Location: where } });
}
function failure(status: number, code: string): Response {
  return new Response(JSON.stringify({ error: { code, message: "private details" }, trace_id: traceId }),
    { status, headers: { "Content-Type": "application/json" } });
}
function session() {
  return { user: { user_id: actor, username_display: "负责人" }, deployment_role: "NONE",
    password_change_required: false,
    authorized_projects: [{ project_id: project, name: "项目", role: "PROJECT_MANAGER" }],
    absolute_expires_at: "2030-01-01T12:00:00Z", idle_expires_at: "2030-01-01T11:00:00Z",
    csrf_token: "a".repeat(64) };
}
async function client(...results: Response[]) {
  const fetcher = vi.fn().mockResolvedValueOnce(envelope(session(), 200));
  for (const result of results) fetcher.mockResolvedValueOnce(result);
  const identity = new SessionClient(fetcher as typeof fetch);
  await identity.login("manager", "synthetic-only");
  return { api: new ProjectDepartmentCreateClient(identity), fetcher, identity };
}

describe("ProjectDepartmentCreateClient", () => {
  afterEach(() => { vi.restoreAllMocks(); vi.useRealTimers(); });

  it("binds a normalized request to the first 201 receipt, not current state", async () => {
    const { api, fetcher } = await client(envelope(created));
    const result = await api.create(project, { code: " ＲＤ ", name: " 研发部 " }, key);
    expect(result).toEqual({ first_result: created, is_current_state_proof: false });
    expect(Object.isFrozen(result)).toBe(true);
    expect(fetcher.mock.calls[1]?.[0]).toBe(`/api/v1/projects/${project}/departments`);
    expect((fetcher.mock.calls[1]?.[1] as RequestInit).body).toBe(JSON.stringify(input));
    expect(JSON.stringify(result)).not.toContain("csrf_token");
  });

  it("accepts same-key first result replay without claiming current state", async () => {
    const { api, fetcher } = await client(envelope(created), envelope(created));
    const first = await api.create(project, input, key);
    const replay = await api.create(project, input, key);
    expect(replay).toEqual(first);
    expect(replay.is_current_state_proof).toBe(false);
    expect(fetcher.mock.calls[1]?.[1]).toMatchObject({ headers: expect.objectContaining({ "Idempotency-Key": key }) });
    expect(fetcher.mock.calls[2]?.[1]).toMatchObject({ headers: expect.objectContaining({ "Idempotency-Key": key }) });
  });

  it.each([
    ["bad", input, key], [project.toUpperCase(), input, key],
    [project, { code: " ", name: "研发部" }, key],
    [project, { code: "RD", name: "\u0000" }, key],
    [project, { code: "x".repeat(65), name: "研发部" }, key],
    [project, input, "short"],
  ])("rejects invalid request before network %#", async (target, value, operation) => {
    const { api, fetcher } = await client();
    await expect(api.create(target, value, operation))
      .rejects.toMatchObject({ code: "PROJECT_DEPARTMENT_CREATE_INVALID_INPUT" });
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it.each([
    [{ ...created, department_id: "bad" }, '"v0"', location],
    [{ ...created, code: "OTHER" }, '"v0"', location],
    [{ ...created, name: "别的部门" }, '"v0"', location],
    [{ ...created, state: "INACTIVE" }, '"v0"', location],
    [{ ...created, etag: '"v1"' }, '"v1"', location],
    [created, '"v1"', location],
    [created, '"v0"', `/api/v1/projects/${actor}/departments/${departmentId}`],
  ] as const)("rejects forged first success %#", async (row, etag, where) => {
    const { api } = await client(envelope(row, 201, etag, where));
    await expect(api.create(project, input, key))
      .rejects.toMatchObject({ code: "PROJECT_DEPARTMENT_CREATE_UNCERTAIN", uncertain: true });
  });

  it.each([
    [401, "AUTH_SESSION_EXPIRED"], [403, "AUTH_CSRF_INVALID"], [403, "LICENSE_OPERATION_DENIED"],
    [404, "RESOURCE_NOT_FOUND"], [409, "PROJECT_ARCHIVED"], [409, "CONFLICT_DUPLICATE"],
    [409, "CONFLICT_IDEMPOTENCY"], [422, "VALIDATION_FAILED"], [400, "REQUEST_MALFORMED"],
  ] as const)("maps known refusal %s %s", async (status, code) => {
    const { api } = await client(failure(status, code));
    const error = await api.create(project, input, key).catch((value: unknown) => value);
    expect(error).toBeInstanceOf(ProjectDepartmentCreateError);
    expect(error).toMatchObject({ code: code === "VALIDATION_FAILED" || code === "REQUEST_MALFORMED"
      ? "PROJECT_DEPARTMENT_CREATE_INVALID_INPUT" : code, uncertain: false });
    expect(String(error)).not.toContain("private");
  });

  it.each([failure(503, "SYSTEM_UNAVAILABLE"), failure(403, "RESOURCE_NOT_FOUND"),
    new Response("<html>private</html>", { status: 201, headers: { "Content-Type": "text/html" } }),
    new Response("invalid json", { status: 201, headers: { "Content-Type": "application/json" } })])(
    "classifies ambiguous response as unknown %#", async (result) => {
      const { api } = await client(result);
      await expect(api.create(project, input, key))
        .rejects.toMatchObject({ code: "PROJECT_DEPARTMENT_CREATE_UNCERTAIN", uncertain: true });
    });

  it("requires fresh in-memory write proof", async () => {
    const readOnly = session(); delete (readOnly as Partial<typeof readOnly>).csrf_token;
    const fetcher = vi.fn().mockResolvedValueOnce(envelope(readOnly, 200));
    const identity = new SessionClient(fetcher as typeof fetch);
    await identity.current();
    await expect(new ProjectDepartmentCreateClient(identity).create(project, input, key))
      .rejects.toMatchObject({ code: "AUTH_RELOGIN_REQUIRED", uncertain: false });
    expect(fetcher).toHaveBeenCalledTimes(1);
  });
});
