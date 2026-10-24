import { afterEach, describe, expect, it, vi } from "vitest";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { ProjectMemberStateClient, ProjectMemberStateError } from "./projectMemberStateClient";
import type { ProjectMemberView } from "./projectMemberReadClient";

const trace = "01234567-89ab-4cde-8123-456789abcdef";
const project = "11234567-89ab-4cde-8123-456789abcdef";
const memberId = "21234567-89ab-4cde-8123-456789abcdef";
const userId = "31234567-89ab-4cde-8123-456789abcdef";
const departmentId = "41234567-89ab-4cde-8123-456789abcdef";
const key = "synthetic-member-state-0001";
const before: ProjectMemberView = { member_id: memberId,
  user: { user_id: userId, display_name: "张三" }, role: "IMPLEMENTATION_MEMBER",
  department: { department_id: departmentId, name: "研发部" }, state: "ACTIVE",
  effective_at: "2026-09-28T08:30:00Z", ended_at: null, etag: '"v0"' };
function reply(data: unknown, status = 200, etag = '"v1"'): Response {
  return new Response(JSON.stringify({ data, trace_id: trace }), { status,
    headers: { "Content-Type": "application/json", ETag: etag } });
}
function error(status: number, code: string): Response {
  return new Response(JSON.stringify({ error: { code, message: "private details" }, trace_id: trace }), {
    status, headers: { "Content-Type": "application/json" },
  });
}
function setup(results: Response[]) {
  const fetcher = vi.fn();
  for (const item of [reply({ user: { user_id: trace, username_display: "负责人" },
    deployment_role: "NONE", password_change_required: false,
    authorized_projects: [{ project_id: project, name: "项目", role: "PROJECT_MANAGER" }],
    absolute_expires_at: "2030-01-01T12:00:00Z", idle_expires_at: "2030-01-01T11:00:00Z",
    csrf_token: "a".repeat(64) }), ...results]) fetcher.mockResolvedValueOnce(item);
  const session = new SessionClient(fetcher as typeof fetch);
  return { session, api: new ProjectMemberStateClient(session), fetcher };
}

describe("ProjectMemberStateClient", () => {
  afterEach(() => vi.restoreAllMocks());

  it.each([
    ["suspend", before, { ...before, state: "SUSPENDED", etag: '"v1"' }],
    ["resume", { ...before, state: "SUSPENDED" }, { ...before, state: "ACTIVE", etag: '"v1"' }],
    ["remove", before, { ...before, state: "REMOVED", ended_at: "2026-09-28T09:00:00Z", etag: '"v1"' }],
  ] as const)("accepts %s only as an immutable first receipt", async (action, source, after) => {
    const { session, api, fetcher } = setup([reply({ ...after, private: "hidden" })]);
    await session.login("负责人", "synthetic-only");
    const result = await api.change(project, source as ProjectMemberView, action, key);
    expect(result.is_current_state_proof).toBe(false);
    expect(result.first_result.state).toBe(after.state);
    expect(JSON.stringify(result)).not.toContain("private");
    expect(fetcher.mock.calls[1]?.[0]).toBe(`/api/v1/projects/${project}/members/${memberId}:${action}`);
    expect(fetcher).toHaveBeenCalledTimes(2);
  });

  it("reuses original Key/ETag and accepts replay of first result without claiming current state", async () => {
    const first = { ...before, state: "SUSPENDED", etag: '"v1"' };
    const { session, api, fetcher } = setup([reply(first), reply(first)]);
    await session.login("负责人", "synthetic-only");
    expect((await api.change(project, before, "suspend", key)).first_result).toMatchObject(first);
    expect((await api.change(project, before, "suspend", key)).is_current_state_proof).toBe(false);
    expect(fetcher.mock.calls[1]?.[1]).toMatchObject({ headers: {
      "Idempotency-Key": key, "If-Match": '"v0"', "X-CSRF-Token": "a".repeat(64),
    } });
    expect(fetcher.mock.calls[2]?.[1]).toMatchObject({ headers: {
      "Idempotency-Key": key, "If-Match": '"v0"', "X-CSRF-Token": "a".repeat(64),
    } });
  });

  it("rejects invalid transition, target, version and key before network", async () => {
    const { session, api, fetcher } = setup([]);
    await session.login("负责人", "synthetic-only");
    for (const [id, source, action, originalKey] of [
      ["../admin", before, "suspend", key],
      [project, { ...before, member_id: "bad" }, "remove", key],
      [project, { ...before, etag: '"v00"' }, "suspend", key],
      [project, before, "resume", key],
      [project, { ...before, state: "REMOVED", ended_at: "2026-09-28T09:00:00Z" }, "remove", key],
      [project, before, "suspend", "short"],
    ] as const) {
      await expect(api.change(id, source as ProjectMemberView,
        action as "suspend", originalKey)).rejects.toMatchObject({ code: "PROJECT_MEMBER_STATE_INVALID_INPUT" });
    }
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it.each([
    [401, "AUTH_SESSION_EXPIRED"], [403, "AUTH_CSRF_INVALID"], [404, "RESOURCE_NOT_FOUND"],
    [409, "PROJECT_ARCHIVED"], [422, "PROJECT_ROLE_INVALID"], [409, "CONFLICT_VERSION"],
    [409, "CONFLICT_STATE"], [409, "CONFLICT_IDEMPOTENCY"],
  ])("maps known %i/%s refusal without leaking server message", async (status, code) => {
    const { session, api } = setup([error(status, code)]);
    await session.login("负责人", "synthetic-only");
    await expect(api.change(project, before, "suspend", key)).rejects.toMatchObject({ code, uncertain: false });
  });

  it.each([
    reply({ ...before, state: "ACTIVE", etag: '"v1"' }),
    reply({ ...before, state: "SUSPENDED", member_id: trace, etag: '"v1"' }),
    reply({ ...before, state: "SUSPENDED", etag: '"v2"' }, 200, '"v2"'),
    reply({ ...before, state: "SUSPENDED", etag: '"v1"' }, 200, '"v0"'),
    new Response("not json", { status: 200, headers: { "Content-Type": "text/plain" } }),
    error(503, "SYSTEM_UNAVAILABLE"),
  ])("treats mismatched or unknown response as uncertain", async (result) => {
    const { session, api, fetcher } = setup([result]);
    await session.login("负责人", "synthetic-only");
    await expect(api.change(project, before, "suspend", key))
      .rejects.toMatchObject({ code: "PROJECT_MEMBER_STATE_UNCERTAIN", uncertain: true });
    expect(fetcher).toHaveBeenCalledTimes(2);
  });
});
