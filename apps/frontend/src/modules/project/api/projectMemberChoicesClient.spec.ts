import { afterEach, describe, expect, it, vi } from "vitest";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { MemberChoicesError, ProjectMemberChoicesClient } from "./projectMemberChoicesClient";

const trace = "01234567-89ab-4cde-8123-456789abcdef";
const project = "11234567-89ab-4cde-8123-456789abcdef";
const user = "21234567-89ab-4cde-8123-456789abcdef";
const department = "31234567-89ab-4cde-8123-456789abcdef";
const inactive = "41234567-89ab-4cde-8123-456789abcdef";
const cursor = `${"a".repeat(32)}.${"b".repeat(43)}`;
function reply(data: unknown, status = 200): Response {
  return new Response(JSON.stringify({ data, trace_id: trace }), { status,
    headers: { "Content-Type": "application/json" } });
}
function error(status: number, code: string): Response {
  return new Response(JSON.stringify({ error: { code, message: "private" }, trace_id: trace }), {
    status, headers: { "Content-Type": "application/json" },
  });
}
function login(): Response {
  return reply({ user: { user_id: trace, username_display: "负责人" }, deployment_role: "NONE",
    password_change_required: false, authorized_projects: [{ project_id: project, name: "项目", role: "PROJECT_MANAGER" }],
    absolute_expires_at: "2030-01-01T12:00:00Z", idle_expires_at: "2030-01-01T11:00:00Z",
    csrf_token: "a".repeat(64) });
}
function setup(responses: Response[]) {
  const fetcher = vi.fn();
  for (const response of [login(), ...responses]) fetcher.mockResolvedValueOnce(response);
  const session = new SessionClient(fetcher as typeof fetch);
  return { session, api: new ProjectMemberChoicesClient(session, fetcher as typeof fetch), fetcher };
}

describe("ProjectMemberChoicesClient", () => {
  afterEach(() => { vi.restoreAllMocks(); vi.useRealTimers(); });

  it("performs exactly one same-origin private-CSRF POST and keeps only the safe candidate", async () => {
    const { session, api, fetcher } = setup([reply({ candidate: { user_id: user, display_name: "张三", secret: "private" }, other: "private" })]);
    await session.login("负责人", "synthetic-only");
    const candidate = await api.candidate(project, "张三");
    expect(candidate).toEqual({ user_id: user, display_name: "张三" });
    expect(Object.isFrozen(candidate)).toBe(true);
    expect(fetcher).toHaveBeenCalledTimes(2);
    expect(fetcher.mock.calls[1]).toEqual([`/api/v1/projects/${project}/member-candidates:resolve`,
      expect.objectContaining({ method: "POST", credentials: "same-origin", cache: "no-store", redirect: "error",
        body: JSON.stringify({ username: "张三" }), headers: { Accept: "application/json",
          "Content-Type": "application/json", "X-CSRF-Token": "a".repeat(64) } })]);
    expect(JSON.stringify(api)).not.toContain("a".repeat(64));
  });

  it("preserves uniform null and rejects malformed candidate or wrong status", async () => {
    const { session, api } = setup([reply({ candidate: null }), reply({ candidate: { user_id: "bad", display_name: "X" } }),
      error(429, "AUTH_RATE_LIMITED")]);
    await session.login("负责人", "synthetic-only");
    await expect(api.candidate(project, "Missing")).resolves.toBeNull();
    await expect(api.candidate(project, "Bad")).rejects.toMatchObject({ code: "UNAVAILABLE" });
    await expect(api.candidate(project, "Again")).rejects.toMatchObject({ code: "AUTH_RATE_LIMITED" });
  });

  it("rejects unsafe input and missing CSRF without candidate network", async () => {
    const { session, api, fetcher } = setup([]);
    await expect(api.candidate(project, "Target")).rejects.toMatchObject({ code: "AUTH_RELOGIN_REQUIRED" });
    await session.login("负责人", "synthetic-only");
    await expect(api.candidate("../admin", "Target")).rejects.toMatchObject({ code: "INVALID_INPUT" });
    await expect(api.candidate(project, "\u0000bad")).rejects.toMatchObject({ code: "INVALID_INPUT" });
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it("clears session on candidate 401 but not on rate limit", async () => {
    const { session, api } = setup([error(429, "AUTH_RATE_LIMITED"), error(401, "AUTH_SESSION_EXPIRED")]);
    await session.login("负责人", "synthetic-only");
    await expect(api.candidate(project, "One")).rejects.toMatchObject({ code: "AUTH_RATE_LIMITED" });
    expect(session.canSubmit).toBe(true);
    await expect(api.candidate(project, "Two")).rejects.toMatchObject({ code: "AUTH_SESSION_EXPIRED" });
    expect(session.canSubmit).toBe(false);
  });

  it("reads all department pages and exposes only ACTIVE safe options", async () => {
    const active = { department_id: department, code: "DEV", name: "研发", state: "ACTIVE", private: "x" };
    const off = { department_id: inactive, code: "OLD", name: "旧部门", state: "INACTIVE" };
    const fetcher = vi.fn().mockResolvedValueOnce(reply({ items: [active, off], next_cursor: cursor, has_more: true }))
      .mockResolvedValueOnce(reply({ items: [], next_cursor: null, has_more: false }));
    const session = new SessionClient();
    const api = new ProjectMemberChoicesClient(session, fetcher as typeof fetch);
    const options = await api.activeDepartments(project);
    expect(options).toEqual([{ department_id: department, code: "DEV", name: "研发" }]);
    expect(Object.isFrozen(options)).toBe(true);
    expect(fetcher.mock.calls[1][0]).toBe(`/api/v1/projects/${project}/departments?page_size=50&cursor=${encodeURIComponent(cursor)}`);
    expect(fetcher.mock.calls[0]).toEqual([`/api/v1/projects/${project}/departments?page_size=50`,
      expect.objectContaining({ method: "GET", credentials: "same-origin", cache: "no-store", redirect: "error" })]);
    expect(session.view).toBeNull();
  });

  it("calls the department fetch function without a client receiver", async () => {
    const fetcher = vi.fn(function (this: unknown) {
      expect(this).toBeUndefined();
      return Promise.resolve(reply({ items: [], next_cursor: null, has_more: false }));
    });
    const api = new ProjectMemberChoicesClient(new SessionClient(), fetcher as typeof fetch);
    await expect(api.activeDepartments(project)).resolves.toEqual([]);
  });

  it("rejects repeated cursor, duplicate department, malformed envelope and permission errors", async () => {
    const item = { department_id: department, code: "DEV", name: "研发", state: "ACTIVE" };
    // Use a direct fetcher because department reads do not require the SessionClient to log in.
    const direct = vi.fn().mockResolvedValueOnce(reply({ items: [item], next_cursor: cursor, has_more: true }))
      .mockResolvedValueOnce(reply({ items: [item], next_cursor: null, has_more: false }));
    await expect(new ProjectMemberChoicesClient(new SessionClient(), direct as typeof fetch).activeDepartments(project))
      .rejects.toMatchObject({ code: "UNAVAILABLE" });
    const repeated = vi.fn().mockResolvedValueOnce(reply({ items: [item], next_cursor: cursor, has_more: true }))
      .mockResolvedValueOnce(reply({ items: [item], next_cursor: cursor, has_more: true }));
    await expect(new ProjectMemberChoicesClient(new SessionClient(), repeated as typeof fetch).activeDepartments(project))
      .rejects.toMatchObject({ code: "UNAVAILABLE" });
    const forbidden = vi.fn().mockResolvedValueOnce(error(404, "RESOURCE_NOT_FOUND"));
    await expect(new ProjectMemberChoicesClient(new SessionClient(), forbidden as typeof fetch).activeDepartments(project))
      .rejects.toMatchObject({ code: "RESOURCE_NOT_FOUND" });
    expect(new MemberChoicesError("UNAVAILABLE").message).not.toContain("private");
  });
});
