import { afterEach, describe, expect, it, vi } from "vitest";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { ProjectMemberPatchClient, ProjectMemberPatchError,
  type ProjectMemberPatchInput } from "./projectMemberPatchClient";
import type { ProjectMemberView } from "./projectMemberReadClient";

const trace = "01234567-89ab-4cde-8123-456789abcdef";
const project = "11234567-89ab-4cde-8123-456789abcdef";
const memberId = "21234567-89ab-4cde-8123-456789abcdef";
const userId = "31234567-89ab-4cde-8123-456789abcdef";
const departmentId = "41234567-89ab-4cde-8123-456789abcdef";
const otherDepartment = "51234567-89ab-4cde-8123-456789abcdef";
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
  return { session, api: new ProjectMemberPatchClient(session), fetcher };
}

describe("ProjectMemberPatchClient", () => {
  afterEach(() => vi.restoreAllMocks());

  it("confirms changed role only after matching member, user, state, ETag and safe projection", async () => {
    const after = { ...before, role: "CUSTOMER_MEMBER", etag: '"v1"', private: "hidden",
      user: { ...before.user, password_hash: "hidden" } };
    const { session, api, fetcher } = setup([reply(after)]);
    await session.login("负责人", "synthetic-only");
    const result = await api.patch(project, before, { role: "CUSTOMER_MEMBER" });
    expect(result).toEqual({ ...before, role: "CUSTOMER_MEMBER", etag: '"v1"' });
    expect(Object.isFrozen(result)).toBe(true);
    expect(fetcher.mock.calls[1][0]).toBe(`/api/v1/projects/${project}/members/${memberId}`);
    expect(fetcher.mock.calls[1][1]).toEqual(expect.objectContaining({
      method: "PATCH", body: JSON.stringify({ role: "CUSTOMER_MEMBER" }),
      headers: { Accept: "application/json", "Content-Type": "application/json",
        "X-CSRF-Token": "a".repeat(64), "If-Match": '"v0"' },
    }));
  });

  it("accepts a legitimate no-change response at the original strong version", async () => {
    const { session, api } = setup([reply(before, 200, '"v0"')]);
    await session.login("负责人", "synthetic-only");
    await expect(api.patch(project, before, { role: before.role })).resolves.toEqual(before);
  });

  it("binds a department-only change and forbids a stale or mismatched success", async () => {
    const changed = { ...before, department: { department_id: otherDepartment, name: "交付部" }, etag: '"v1"' };
    const good = setup([reply(changed)]);
    await good.session.login("负责人", "synthetic-only");
    await expect(good.api.patch(project, before, { department_id: otherDepartment })).resolves.toEqual(changed);
    for (const bad of [
      { ...changed, member_id: trace }, { ...changed, user: { ...changed.user, user_id: trace } },
      { ...changed, state: "SUSPENDED" }, { ...changed, etag: '"v0"' },
      { ...changed, department: before.department },
    ]) {
      const caseClient = setup([reply(bad, 200, bad.etag)]);
      await caseClient.session.login("负责人", "synthetic-only");
      await expect(caseClient.api.patch(project, before, { department_id: otherDepartment }))
        .rejects.toMatchObject({ code: "PROJECT_MEMBER_PATCH_UNCERTAIN" });
    }
  });

  it("rejects invalid project, removed member, version, fields and unknown keys before network", async () => {
    const { session, api, fetcher } = setup([]);
    await session.login("负责人", "synthetic-only");
    const invalid: Array<[string, ProjectMemberView, ProjectMemberPatchInput]> = [
      ["../admin", before, { role: "CUSTOMER_MEMBER" }],
      [project, { ...before, state: "REMOVED", ended_at: "2026-09-28T09:00:00Z" }, { role: "CUSTOMER_MEMBER" }],
      [project, { ...before, etag: 'W/"v0"' }, { role: "CUSTOMER_MEMBER" }],
      [project, before, {}], [project, before, { role: "UNTRUSTED" as ProjectMemberView["role"] }],
      [project, before, { department_id: "../other" }],
      [project, before, { role: "CUSTOMER_MEMBER", extra: "private" } as ProjectMemberPatchInput],
    ];
    for (const [target, current, input] of invalid) {
      await expect(api.patch(target, current, input)).rejects.toMatchObject({
        code: "PROJECT_MEMBER_PATCH_INVALID_INPUT",
      });
    }
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it("maps only matching explicit denials; unknown responses remain uncertain", async () => {
    const { session, api } = setup([error(409, "CONFLICT_VERSION"), error(403, "LICENSE_OPERATION_DENIED"),
      error(404, "RESOURCE_NOT_FOUND"), error(503, "SYSTEM_UNAVAILABLE"), error(400, "CONFLICT_VERSION")]);
    await session.login("负责人", "synthetic-only");
    for (const code of ["CONFLICT_VERSION", "LICENSE_OPERATION_DENIED", "RESOURCE_NOT_FOUND",
      "PROJECT_MEMBER_PATCH_UNCERTAIN", "PROJECT_MEMBER_PATCH_UNCERTAIN"]) {
      await expect(api.patch(project, before, { role: "CUSTOMER_MEMBER" }))
        .rejects.toMatchObject({ code });
    }
  });

  it("treats transport failure, wrong content type and malformed success as uncertain", async () => {
    const { session, api, fetcher } = setup([new Response("down", { status: 503 }),
      new Response("ok", { status: 200, headers: { "Content-Type": "text/plain" } }),
      reply({ ...before, role: "CUSTOMER_MEMBER", etag: '"v1"' }, 200, '"v9"')]);
    await session.login("负责人", "synthetic-only");
    for (let index = 0; index < 3; index += 1) {
      await expect(api.patch(project, before, { role: "CUSTOMER_MEMBER" }))
        .rejects.toMatchObject({ uncertain: true });
    }
    expect(fetcher).toHaveBeenCalledTimes(4);
    expect(new ProjectMemberPatchError("PROJECT_MEMBER_PATCH_UNCERTAIN").message).not.toContain("private");
  });
});
