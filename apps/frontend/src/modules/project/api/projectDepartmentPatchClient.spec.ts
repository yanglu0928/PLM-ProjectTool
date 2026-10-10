import { afterEach, describe, expect, it, vi } from "vitest";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { ProjectDepartmentPatchClient, ProjectDepartmentPatchError,
  type ProjectDepartmentPatchInput } from "./projectDepartmentPatchClient";
import type { ProjectDepartmentView } from "./projectDepartmentReadClient";

const actor = "01234567-89ab-4cde-8123-456789abcdef";
const project = "11234567-89ab-4cde-8123-456789abcdef";
const departmentId = "21234567-89ab-4cde-8123-456789abcdef";
const trace = "31234567-89ab-4cde-8123-456789abcdef";
const before: ProjectDepartmentView = { department_id: departmentId, code: "RD", name: "研发部",
  state: "ACTIVE", created_at: "2026-09-29T03:00:00Z", etag: '"v0"' };
function envelope(data: unknown, status = 200, etag = '"v1"'): Response {
  return new Response(JSON.stringify({ data, trace_id: trace }), { status,
    headers: { "Content-Type": "application/json", ETag: etag } });
}
function failure(status: number, code: string): Response {
  return new Response(JSON.stringify({ error: { code, message: "private details" }, trace_id: trace }),
    { status, headers: { "Content-Type": "application/json" } });
}
async function client(...responses: Response[]) {
  const session = { user: { user_id: actor, username_display: "负责人" }, deployment_role: "NONE",
    password_change_required: false,
    authorized_projects: [{ project_id: project, name: "项目", role: "PROJECT_MANAGER" }],
    absolute_expires_at: "2030-01-01T12:00:00Z", idle_expires_at: "2030-01-01T11:00:00Z",
    csrf_token: "a".repeat(64) };
  const fetcher = vi.fn().mockResolvedValueOnce(envelope(session));
  for (const response of responses) fetcher.mockResolvedValueOnce(response);
  const identity = new SessionClient(fetcher as typeof fetch);
  await identity.login("manager", "synthetic-only");
  return { api: new ProjectDepartmentPatchClient(identity), identity, fetcher };
}

describe("ProjectDepartmentPatchClient", () => {
  afterEach(() => vi.restoreAllMocks());

  it("normalizes code/name and binds a changed v1 success to the original department", async () => {
    const after = { ...before, code: "NEW", name: "新部门", etag: '"v1"', private: "hidden" };
    const { api, fetcher } = await client(envelope(after));
    const result = await api.patch(project, before, { code: " ＮＥＷ ", name: " 新部门 " });
    expect(result).toEqual({ ...before, code: "NEW", name: "新部门", etag: '"v1"' });
    expect(Object.isFrozen(result)).toBe(true);
    expect(fetcher.mock.calls[1]).toEqual([`/api/v1/projects/${project}/departments/${departmentId}`,
      expect.objectContaining({ method: "PATCH", body: JSON.stringify({ code: "NEW", name: "新部门" }),
        headers: { Accept: "application/json", "Content-Type": "application/json",
          "X-CSRF-Token": "a".repeat(64), "If-Match": '"v0"' } })]);
  });

  it("accepts unchanged result only at the original version", async () => {
    const { api } = await client(envelope(before, 200, '"v0"'));
    await expect(api.patch(project, before, { name: before.name })).resolves.toEqual(before);
  });

  it.each([
    ["bad", before, { name: "新部门" }], [project.toUpperCase(), before, { name: "新部门" }],
    [project, { ...before, state: "INACTIVE" as const }, { name: "新部门" }],
    [project, { ...before, etag: 'W/"v0"' }, { name: "新部门" }],
    [project, before, {}], [project, before, { name: "\u0000" }],
    [project, before, { code: "x".repeat(65) }],
    [project, before, { name: "新部门", extra: "hidden" } as ProjectDepartmentPatchInput],
  ])("rejects invalid input before network %#", async (target, previous, input) => {
    const { api, fetcher } = await client();
    await expect(api.patch(target, previous, input))
      .rejects.toMatchObject({ code: "PROJECT_DEPARTMENT_PATCH_INVALID_INPUT", uncertain: false });
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it.each([
    { ...before, department_id: actor, name: "新部门", etag: '"v1"' },
    { ...before, created_at: "2026-09-29T03:01:00Z", name: "新部门", etag: '"v1"' },
    { ...before, state: "INACTIVE", name: "新部门", etag: '"v1"' },
    { ...before, code: "OTHER", name: "新部门", etag: '"v1"' },
    { ...before, name: "新部门", etag: '"v0"' },
  ])("rejects forged or drifted success %#", async (after) => {
    const { api } = await client(envelope(after, 200, after.etag));
    await expect(api.patch(project, before, { name: "新部门" }))
      .rejects.toMatchObject({ code: "PROJECT_DEPARTMENT_PATCH_UNCERTAIN", uncertain: true });
  });

  it("requires an exact response ETag and JSON envelope", async () => {
    for (const response of [envelope({ ...before, name: "新部门", etag: '"v1"' }, 200, '"v2"'),
      new Response("ok", { status: 200, headers: { "Content-Type": "text/plain" } })]) {
      const { api } = await client(response);
      await expect(api.patch(project, before, { name: "新部门" }))
        .rejects.toMatchObject({ uncertain: true });
    }
  });

  it.each([
    [401, "AUTH_SESSION_EXPIRED"], [403, "AUTH_CSRF_INVALID"],
    [403, "LICENSE_OPERATION_DENIED"], [404, "RESOURCE_NOT_FOUND"],
    [409, "PROJECT_ARCHIVED"], [409, "CONFLICT_VERSION"],
    [409, "CONFLICT_STATE"], [409, "CONFLICT_DUPLICATE"],
    [422, "VALIDATION_FAILED"], [400, "REQUEST_MALFORMED"],
  ] as const)("maps known refusal %s %s", async (status, code) => {
    const { api } = await client(failure(status, code));
    const caught = await api.patch(project, before, { name: "新部门" }).catch((value: unknown) => value);
    expect(caught).toBeInstanceOf(ProjectDepartmentPatchError);
    expect(caught).toMatchObject({ code: code === "VALIDATION_FAILED" || code === "REQUEST_MALFORMED"
      ? "PROJECT_DEPARTMENT_PATCH_INVALID_INPUT" : code, uncertain: false });
    expect(String(caught)).not.toContain("private");
  });

  it("keeps transport failure, mismatched code/status and server error uncertain", async () => {
    const { api, fetcher } = await client(failure(503, "SYSTEM_UNAVAILABLE"),
      failure(403, "RESOURCE_NOT_FOUND"));
    for (let index = 0; index < 2; index += 1) {
      await expect(api.patch(project, before, { name: "新部门" }))
        .rejects.toMatchObject({ uncertain: true });
    }
    fetcher.mockRejectedValueOnce(new Error("synthetic disconnect"));
    await expect(api.patch(project, before, { name: "新部门" }))
      .rejects.toMatchObject({ uncertain: true });
    expect(fetcher).toHaveBeenCalledTimes(4);
  });
});
