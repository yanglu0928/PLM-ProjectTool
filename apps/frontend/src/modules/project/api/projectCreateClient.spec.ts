import { afterEach, describe, expect, it, vi } from "vitest";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { ProjectCreateClient, ProjectCreateError, type ProjectCreateInput } from "./projectCreateClient";

const id = "01234567-89ab-4cde-8123-456789abcdef";
const projectId = "11234567-89ab-4cde-8123-456789abcdef";
const key = "synthetic-create-0001";
const input: ProjectCreateInput = { code: " DEMO ", name: " 演示项目 ", initial_manager_user_id: id };
const project = { project_id: projectId, code: "DEMO", name: "演示项目", state: "ACTIVE",
  created_at: "2026-09-28T08:30:00Z", etag: '"v0"' };
function response(data: unknown, status = 201, headers: Record<string, string> = {}): Response {
  return new Response(JSON.stringify({ data, trace_id: id }), { status,
    headers: { "Content-Type": "application/json", ETag: '"v0"',
      Location: `/api/v1/projects/${projectId}`, ...headers } });
}
function error(status: number, code: string): Response {
  return new Response(JSON.stringify({ error: { code, message: "private details" }, trace_id: id }),
    { status, headers: { "Content-Type": "application/json" } });
}
function auth(replies: Response[]) {
  const login = response({ user: { user_id: id, username_display: "Synthetic Admin" },
    deployment_role: "DEPLOYMENT_ADMIN", password_change_required: false, authorized_projects: [],
    absolute_expires_at: "2030-01-01T12:00:00Z", idle_expires_at: "2030-01-01T11:00:00Z",
    csrf_token: "a".repeat(64) }, 200);
  const fetcher = vi.fn();
  for (const reply of [login, ...replies]) fetcher.mockResolvedValueOnce(reply);
  const session = new SessionClient(fetcher as typeof fetch);
  return { session, api: new ProjectCreateClient(session), fetcher };
}

describe("ProjectCreateClient", () => {
  afterEach(() => vi.restoreAllMocks());

  it("submits the normalized frozen body once, with caller key and only safe created projection", async () => {
    const { session, api, fetcher } = auth([response({ ...project, internal: "not-public" })]);
    await session.login("Synthetic Admin", "synthetic-only");
    const view = await api.create(input, key);
    expect(view).toEqual(project);
    expect(Object.isFrozen(view)).toBe(true);
    expect(view).not.toHaveProperty("internal");
    expect(fetcher.mock.calls[1]).toEqual(["/api/v1/projects", expect.objectContaining({
      method: "POST", credentials: "same-origin", cache: "no-store", redirect: "error",
      body: JSON.stringify({ code: "DEMO", name: "演示项目", initial_manager_user_id: id }),
      headers: { Accept: "application/json", "Content-Type": "application/json",
        "X-CSRF-Token": "a".repeat(64), "Idempotency-Key": key },
    })]);
    expect(fetcher).toHaveBeenCalledTimes(2);
  });

  it("includes a normalized optional department without inventing it when omitted", async () => {
    const { session, api, fetcher } = auth([response(project)]);
    await session.login("Synthetic Admin", "synthetic-only");
    await api.create({ ...input, department: { code: " Ｄ１ ", name: " 交付组 " } }, key);
    expect(JSON.parse(fetcher.mock.calls[1][1].body)).toEqual({ code: "DEMO", name: "演示项目",
      initial_manager_user_id: id, department: { code: "D1", name: "交付组" } });
  });

  it.each([
    { ...input, code: "" }, { ...input, code: "x".repeat(65) },
    { ...input, name: "\u0000" }, { ...input, initial_manager_user_id: "bad" },
    { ...input, department: { code: "", name: "部门" } },
  ])("rejects invalid input before network %j", async (bad) => {
    const { api, fetcher } = auth([]);
    await expect(api.create(bad, key)).rejects.toMatchObject({ code: "PROJECT_CREATE_INVALID_INPUT", uncertain: false });
    expect(fetcher).not.toHaveBeenCalled();
  });

  it("rejects invalid key locally and read-only recovery cannot create", async () => {
    const { session, api, fetcher } = auth([response({
      user: { user_id: id, username_display: "Synthetic Admin" },
      deployment_role: "DEPLOYMENT_ADMIN", password_change_required: false, authorized_projects: [],
      absolute_expires_at: "2030-01-01T12:00:00Z", idle_expires_at: "2030-01-01T11:00:00Z",
    }, 200)]);
    await session.login("Synthetic Admin", "synthetic-only");
    await expect(api.create(input, "short")).rejects.toMatchObject({ code: "PROJECT_CREATE_INVALID_INPUT" });
    await session.current();
    expect(session.view?.deployment_role).toBe("DEPLOYMENT_ADMIN");
    expect(session.canSubmit).toBe(false);
    await expect(api.create(input, key)).rejects.toMatchObject({ code: "AUTH_RELOGIN_REQUIRED", uncertain: false });
    expect(fetcher).toHaveBeenCalledTimes(2);
  });

  it.each([[401, "AUTH_SESSION_EXPIRED"], [403, "AUTH_CSRF_INVALID"],
    [403, "LICENSE_OPERATION_DENIED"], [404, "RESOURCE_NOT_FOUND"],
    [422, "PROJECT_ROLE_INVALID"], [409, "PROJECT_USER_ALREADY_ASSIGNED"],
    [409, "CONFLICT_DUPLICATE"], [409, "CONFLICT_IDEMPOTENCY"]] as const)(
    "maps definite rejection %s %s without raw details", async (status, code) => {
      const { session, api, fetcher } = auth([error(status, code)]);
      await session.login("Synthetic Admin", "synthetic-only");
      const failure = await api.create(input, key).catch((value: unknown) => value);
      expect(failure).toBeInstanceOf(ProjectCreateError);
      if (!(failure instanceof ProjectCreateError)) throw new Error("expected safe create error");
      expect(failure.code).toBe(code);
      expect(failure.uncertain).toBe(false);
      expect(String(failure)).not.toContain("private");
      expect(fetcher).toHaveBeenCalledTimes(2);
    });

  it.each([[400, "REQUEST_MALFORMED"], [422, "VALIDATION_FAILED"]] as const)(
    "maps server input rejection %s %s", async (status, code) => {
      const { session, api } = auth([error(status, code)]);
      await session.login("Synthetic Admin", "synthetic-only");
      await expect(api.create(input, key)).rejects.toMatchObject({ code: "PROJECT_CREATE_INVALID_INPUT", uncertain: false });
    });

  it.each([error(503, "SYSTEM_UNAVAILABLE"), error(403, "UNKNOWN"),
    response({ ...project, etag: '"v1"' }), response(project, 201, { Location: "/api/v1/projects/other" }),
    response(project, 201, { ETag: '"v1"' }), response({ ...project, project_id: id }),
    new Response("not-json", { status: 201, headers: { "Content-Type": "application/json" } }),
  ])("treats unknown or malformed result as potentially committed without retry", async (raw) => {
    const { session, api, fetcher } = auth([raw]);
    await session.login("Synthetic Admin", "synthetic-only");
    await expect(api.create(input, key)).rejects.toMatchObject({ code: "PROJECT_CREATE_UNCERTAIN", uncertain: true });
    expect(fetcher).toHaveBeenCalledTimes(2);
  });

  it("treats transport failure as uncertain and preserves caller key for explicit recovery", async () => {
    const { session, api, fetcher } = auth([]);
    await session.login("Synthetic Admin", "synthetic-only");
    fetcher.mockRejectedValueOnce(new Error("private network failure"));
    await expect(api.create(input, key)).rejects.toMatchObject({ code: "PROJECT_CREATE_UNCERTAIN", uncertain: true });
    expect(session.canSubmit).toBe(true);
    expect(fetcher).toHaveBeenCalledTimes(2);
  });
});
