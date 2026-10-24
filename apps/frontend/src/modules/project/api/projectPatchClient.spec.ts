import { afterEach, describe, expect, it, vi } from "vitest";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { ProjectPatchClient, ProjectPatchError } from "./projectPatchClient";
import type { ProjectView } from "./projectReadClient";

const actor = "01234567-89ab-4cde-8123-456789abcdef";
const project = "11234567-89ab-4cde-8123-456789abcdef";
const trace = "31234567-89ab-4cde-8123-456789abcdef";
const before: ProjectView = { project_id: project, code: "OWNED", name: "原项目",
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
  return { api: new ProjectPatchClient(identity), identity, fetcher };
}

describe("ProjectPatchClient", () => {
  afterEach(() => vi.restoreAllMocks());

  it("normalizes name and binds v1 success to original Project identity", async () => {
    const after = { ...before, name: "新项目", etag: '"v1"', private: "hidden" };
    const { api, fetcher } = await client(envelope(after));
    const result = await api.patch(project, before, " 新项目 ");
    expect(result).toEqual({ ...before, name: "新项目", etag: '"v1"' });
    expect(Object.isFrozen(result)).toBe(true);
    expect(fetcher.mock.calls[1]).toEqual([`/api/v1/projects/${project}`,
      expect.objectContaining({ method: "PATCH", body: JSON.stringify({ name: "新项目" }),
        headers: { Accept: "application/json", "Content-Type": "application/json",
          "X-CSRF-Token": "a".repeat(64), "If-Match": '"v0"' } })]);
  });

  it("requires a new version even for the same name", async () => {
    const { api } = await client(envelope({ ...before, etag: '"v1"' }));
    await expect(api.patch(project, before, before.name)).resolves.toEqual({ ...before, etag: '"v1"' });
  });

  it.each([
    ["bad", before, "新项目"], [project.toUpperCase(), before, "新项目"],
    [project, { ...before, project_id: actor }, "新项目"],
    [project, { ...before, state: "ARCHIVED" as const }, "新项目"],
    [project, { ...before, etag: 'W/"v0"' }, "新项目"],
    [project, before, ""], [project, before, "\u0000"],
    [project, before, "x".repeat(256)],
  ])("rejects invalid input without network %#", async (target, previous, name) => {
    const { api, fetcher } = await client();
    await expect(api.patch(target, previous, name))
      .rejects.toMatchObject({ code: "PROJECT_PATCH_INVALID_INPUT", uncertain: false });
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it.each([
    { ...before, project_id: actor, name: "新项目", etag: '"v1"' },
    { ...before, code: "OTHER", name: "新项目", etag: '"v1"' },
    { ...before, created_at: "2026-09-29T03:01:00Z", name: "新项目", etag: '"v1"' },
    { ...before, state: "ARCHIVED", name: "新项目", etag: '"v1"' },
    { ...before, name: "OTHER", etag: '"v1"' },
    { ...before, name: "新项目", etag: '"v0"' },
  ])("rejects forged or drifted success %#", async (after) => {
    const { api } = await client(envelope(after, 200, after.etag));
    await expect(api.patch(project, before, "新项目"))
      .rejects.toMatchObject({ code: "PROJECT_PATCH_UNCERTAIN", uncertain: true });
  });

  it("requires exact response ETag and JSON envelope", async () => {
    for (const response of [envelope({ ...before, name: "新项目", etag: '"v1"' }, 200, '"v2"'),
      new Response("ok", { status: 200, headers: { "Content-Type": "text/plain" } })]) {
      const { api } = await client(response);
      await expect(api.patch(project, before, "新项目")).rejects.toMatchObject({ uncertain: true });
    }
  });

  it.each([
    [401, "AUTH_SESSION_EXPIRED"], [403, "AUTH_CSRF_INVALID"],
    [403, "LICENSE_OPERATION_DENIED"], [404, "RESOURCE_NOT_FOUND"],
    [409, "PROJECT_ARCHIVED"], [409, "CONFLICT_VERSION"],
    [422, "VALIDATION_FAILED"], [400, "REQUEST_MALFORMED"],
    [428, "CONFLICT_VERSION_REQUIRED"],
  ] as const)("maps known refusal %s %s", async (status, code) => {
    const { api } = await client(failure(status, code));
    const caught = await api.patch(project, before, "新项目").catch((value: unknown) => value);
    expect(caught).toBeInstanceOf(ProjectPatchError);
    expect(caught).toMatchObject({ code: ["VALIDATION_FAILED", "REQUEST_MALFORMED",
      "CONFLICT_VERSION_REQUIRED"].includes(code) ? "PROJECT_PATCH_INVALID_INPUT" : code,
    uncertain: false });
    expect(String(caught)).not.toContain("private");
  });

  it("keeps transport failure, mismatched code/status and server error uncertain", async () => {
    const { api, fetcher } = await client(failure(503, "SYSTEM_UNAVAILABLE"),
      failure(403, "RESOURCE_NOT_FOUND"));
    for (let index = 0; index < 2; index += 1) {
      await expect(api.patch(project, before, "新项目")).rejects.toMatchObject({ uncertain: true });
    }
    fetcher.mockRejectedValueOnce(new Error("synthetic disconnect"));
    await expect(api.patch(project, before, "新项目")).rejects.toMatchObject({ uncertain: true });
    expect(fetcher).toHaveBeenCalledTimes(4);
  });
});
