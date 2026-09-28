import { afterEach, describe, expect, it, vi } from "vitest";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { ProjectMemberCreateClient, ProjectMemberCreateError, type ProjectMemberCreateInput } from "./projectMemberCreateClient";

const trace = "01234567-89ab-4cde-8123-456789abcdef";
const projectId = "11234567-89ab-4cde-8123-456789abcdef";
const memberId = "21234567-89ab-4cde-8123-456789abcdef";
const userId = "31234567-89ab-4cde-8123-456789abcdef";
const departmentId = "41234567-89ab-4cde-8123-456789abcdef";
const key = "synthetic-member-create-0001";
const input: ProjectMemberCreateInput = { user_id: userId, role: "IMPLEMENTATION_MEMBER", department_id: departmentId };
const member = { member_id: memberId, user: { user_id: userId, display_name: "合成用户" },
  role: "IMPLEMENTATION_MEMBER", department: { department_id: departmentId, name: "合成部门" },
  state: "ACTIVE", effective_at: "2026-09-28T08:30:00Z", ended_at: null, etag: '"v0"' };
function reply(data: unknown, status = 201, headers: Record<string, string> = {}): Response {
  return new Response(JSON.stringify({ data, trace_id: trace }), { status,
    headers: { "Content-Type": "application/json", ETag: '"v0"',
      Location: `/api/v1/projects/${projectId}/members/${memberId}`, ...headers } });
}
function reject(status: number, code: string): Response {
  return new Response(JSON.stringify({ error: { code, message: "private details" }, trace_id: trace }),
    { status, headers: { "Content-Type": "application/json" } });
}
function setup(replies: Response[]) {
  const login = reply({ user: { user_id: trace, username_display: "Synthetic Admin" },
    deployment_role: "DEPLOYMENT_ADMIN", password_change_required: false, authorized_projects: [],
    absolute_expires_at: "2030-01-01T12:00:00Z", idle_expires_at: "2030-01-01T11:00:00Z",
    csrf_token: "a".repeat(64) }, 200);
  const fetcher = vi.fn();
  for (const item of [login, ...replies]) fetcher.mockResolvedValueOnce(item);
  const session = new SessionClient(fetcher as typeof fetch);
  return { session, api: new ProjectMemberCreateClient(session), fetcher };
}

describe("ProjectMemberCreateClient", () => {
  afterEach(() => vi.restoreAllMocks());

  it("submits once with the caller key and returns only a frozen safe projection", async () => {
    const { session, api, fetcher } = setup([reply({ ...member, internal: "private",
      user: { ...member.user, secret: "private" } })]);
    await session.login("Synthetic Admin", "synthetic-only");
    const view = await api.create(projectId, input, key);
    expect(view).toEqual(member);
    expect(Object.isFrozen(view)).toBe(true);
    expect(Object.isFrozen(view.user)).toBe(true);
    expect(view).not.toHaveProperty("internal");
    expect(view.user).not.toHaveProperty("secret");
    expect(fetcher.mock.calls[1]).toEqual([`/api/v1/projects/${projectId}/members`, expect.objectContaining({
      method: "POST", credentials: "same-origin", cache: "no-store", redirect: "error",
      body: JSON.stringify(input), headers: { Accept: "application/json", "Content-Type": "application/json",
        "X-CSRF-Token": "a".repeat(64), "Idempotency-Key": key },
    })]);
    expect(fetcher).toHaveBeenCalledTimes(2);
  });

  it("includes an explicit UTC effective time and ignores extra input fields", async () => {
    const { session, api, fetcher } = setup([reply(member)]);
    await session.login("Synthetic Admin", "synthetic-only");
    await api.create(projectId, { ...input, effective_at: member.effective_at, extra: "private" } as ProjectMemberCreateInput, key);
    expect(JSON.parse(fetcher.mock.calls[1][1].body)).toEqual({ ...input, effective_at: member.effective_at });
  });

  it("does not accept an effective-time mismatch hidden below JavaScript millisecond precision", async () => {
    const { session, api } = setup([reply({ ...member, effective_at: "2026-09-28T08:30:00.123457Z" })]);
    await session.login("Synthetic Admin", "synthetic-only");
    await expect(api.create(projectId, { ...input, effective_at: "2026-09-28T08:30:00.123456Z" }, key))
      .rejects.toMatchObject({ code: "PROJECT_MEMBER_CREATE_UNCERTAIN", uncertain: true });
  });

  it("rejects a read-only session before attempting a write", async () => {
    const { api, fetcher } = setup([]);
    await expect(api.create(projectId, input, key))
      .rejects.toMatchObject({ code: "AUTH_RELOGIN_REQUIRED", uncertain: false });
    expect(fetcher).not.toHaveBeenCalled();
  });

  it.each([
    ["bad", input, key], [projectId, { ...input, user_id: "bad" }, key],
    [projectId, { ...input, role: "ADMIN" }, key],
    [projectId, { ...input, department_id: "bad" }, key],
    [projectId, { ...input, effective_at: "2026-02-30T00:00:00Z" }, key],
    [projectId, input, "short"],
  ])("rejects invalid input without network %#", async (target, data, requestKey) => {
    const { api, fetcher } = setup([]);
    await expect(api.create(target as string, data as ProjectMemberCreateInput, requestKey as string))
      .rejects.toMatchObject({ code: "PROJECT_MEMBER_CREATE_INVALID_INPUT", uncertain: false });
    expect(fetcher).not.toHaveBeenCalled();
  });

  it.each([[401, "AUTH_SESSION_EXPIRED"], [403, "AUTH_CSRF_INVALID"],
    [403, "LICENSE_OPERATION_DENIED"], [404, "RESOURCE_NOT_FOUND"],
    [409, "PROJECT_ARCHIVED"], [422, "PROJECT_ROLE_INVALID"],
    [409, "PROJECT_USER_ALREADY_ASSIGNED"], [409, "CONFLICT_IDEMPOTENCY"]] as const)(
    "maps definite rejection %s %s without raw details", async (status, code) => {
      const { session, api, fetcher } = setup([reject(status, code)]);
      await session.login("Synthetic Admin", "synthetic-only");
      const failure = await api.create(projectId, input, key).catch((value: unknown) => value);
      expect(failure).toBeInstanceOf(ProjectMemberCreateError);
      expect(failure).toMatchObject({ code, uncertain: false });
      expect(String(failure)).not.toContain("private");
      expect(fetcher).toHaveBeenCalledTimes(2);
    });

  it.each([[400, "REQUEST_MALFORMED"], [422, "VALIDATION_FAILED"]] as const)(
    "maps definite input rejection %s %s", async (status, code) => {
      const { session, api } = setup([reject(status, code)]);
      await session.login("Synthetic Admin", "synthetic-only");
      await expect(api.create(projectId, input, key))
        .rejects.toMatchObject({ code: "PROJECT_MEMBER_CREATE_INVALID_INPUT", uncertain: false });
    });

  it.each([reject(503, "SYSTEM_UNAVAILABLE"), reject(403, "UNKNOWN"),
    reply({ ...member, state: "SUSPENDED" }), reply({ ...member, etag: '"v1"' }),
    reply(member, 201, { Location: "/api/v1/projects/other" }),
    reply(member, 201, { ETag: '"v1"' }), reply({ ...member, user: { ...member.user, user_id: trace } }),
    reply({ ...member, role: "CUSTOMER_MEMBER" }),
    reply({ ...member, department: { ...member.department, department_id: trace } }),
    reply(member, 200), new Response("not-json", { status: 201, headers: { "Content-Type": "application/json" } }),
  ])("treats unknown or mismatched result as uncertain and never retries %#", async (raw) => {
    const { session, api, fetcher } = setup([raw]);
    await session.login("Synthetic Admin", "synthetic-only");
    await expect(api.create(projectId, input, key))
      .rejects.toMatchObject({ code: "PROJECT_MEMBER_CREATE_UNCERTAIN", uncertain: true });
    expect(fetcher).toHaveBeenCalledTimes(2);
  });

  it("classifies transport failure as uncertain without changing the caller key", async () => {
    const { session, api, fetcher } = setup([]);
    await session.login("Synthetic Admin", "synthetic-only");
    fetcher.mockRejectedValueOnce(new Error("private network details"));
    await expect(api.create(projectId, input, key))
      .rejects.toMatchObject({ code: "PROJECT_MEMBER_CREATE_UNCERTAIN", uncertain: true });
    expect(fetcher).toHaveBeenCalledTimes(2);
  });
});
