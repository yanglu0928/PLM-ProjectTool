import { afterEach, describe, expect, it, vi } from "vitest";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { ProjectArchiveClient, ProjectArchiveError } from "./projectArchiveClient";
import type { ProjectView } from "./projectReadClient";

const actor = "01234567-89ab-4cde-8123-456789abcdef";
const project = "11234567-89ab-4cde-8123-456789abcdef";
const other = "21234567-89ab-4cde-8123-456789abcdef";
const trace = "31234567-89ab-4cde-8123-456789abcdef";
const key = "synthetic-project-archive-0001";
const before: ProjectView = { project_id: project, code: "PLM", name: "项目", state: "ACTIVE",
  created_at: "2026-09-29T03:00:00Z", etag: '"v0"' };
const archived = { ...before, state: "ARCHIVED" as const, etag: '"v1"' };
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
  return { api: new ProjectArchiveClient(identity), identity, fetcher };
}

describe("ProjectArchiveClient", () => {
  afterEach(() => vi.restoreAllMocks());

  it("accepts only a bound archived v1 first receipt", async () => {
    const { api, fetcher } = await client(envelope({ ...archived, private: "hidden" }));
    const result = await api.archive(project, before, key);
    expect(result).toEqual({ first_result: archived, is_current_state_proof: false });
    expect(Object.isFrozen(result)).toBe(true);
    expect(fetcher.mock.calls[1][0]).toBe(`/api/v1/projects/${project}:archive`);
    expect(fetcher.mock.calls[1][1]).toMatchObject({ headers: {
      Accept: "application/json", "X-CSRF-Token": "a".repeat(64),
      "If-Match": '"v0"', "Idempotency-Key": key,
    } });
    expect(JSON.stringify(result)).not.toContain("private");
  });

  it("keeps original Key/ETag on replay without claiming current state", async () => {
    const { api, fetcher } = await client(envelope(archived), envelope(archived));
    const first = await api.archive(project, before, key);
    const replay = await api.archive(project, before, key);
    expect(replay).toEqual(first);
    expect(replay.is_current_state_proof).toBe(false);
    expect(fetcher.mock.calls[2][1]).toMatchObject({ headers: {
      "If-Match": '"v0"', "Idempotency-Key": key,
    } });
  });

  it.each([
    ["../admin", before, key], [other, before, key], [project.toUpperCase(), before, key],
    [project, { ...before, project_id: "bad" }, key],
    [project, { ...before, state: "ARCHIVED" }, key],
    [project, { ...before, etag: 'W/"v0"' }, key],
    [project, { ...before, etag: '"v9007199254740991"' }, key],
    [project, before, "short"],
  ])("rejects invalid original project, state, version or Key before network %#", async (target, source, attemptKey) => {
    const { api, fetcher } = await client();
    await expect(api.archive(target, source as ProjectView, attemptKey))
      .rejects.toMatchObject({ code: "PROJECT_ARCHIVE_INVALID_INPUT", uncertain: false });
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it.each([
    [401, "AUTH_SESSION_EXPIRED"], [403, "AUTH_CSRF_INVALID"],
    [403, "LICENSE_OPERATION_DENIED"], [404, "RESOURCE_NOT_FOUND"],
    [409, "PROJECT_ARCHIVED"], [409, "CONFLICT_VERSION"],
    [409, "CONFLICT_STATE"], [409, "CONFLICT_IDEMPOTENCY"],
    [400, "REQUEST_MALFORMED"], [422, "VALIDATION_FAILED"],
    [428, "CONFLICT_VERSION_REQUIRED"],
  ] as const)("maps known refusal %s %s", async (status, code) => {
    const { api } = await client(failure(status, code));
    const caught = await api.archive(project, before, key).catch((value: unknown) => value);
    expect(caught).toBeInstanceOf(ProjectArchiveError);
    expect(caught).toMatchObject({ code: ["REQUEST_MALFORMED", "VALIDATION_FAILED",
      "CONFLICT_VERSION_REQUIRED"].includes(code) ? "PROJECT_ARCHIVE_INVALID_INPUT" : code,
    uncertain: false });
    expect(String(caught)).not.toContain("private");
  });

  it.each([
    { ...archived, project_id: other }, { ...archived, code: "OTHER" },
    { ...archived, name: "别的项目" }, { ...archived, created_at: "2026-09-29T03:01:00Z" },
    { ...archived, state: "ACTIVE" }, { ...archived, etag: '"v2"' },
  ])("rejects a forged first result %#", async (after) => {
    const { api } = await client(envelope(after, 200, after.etag));
    await expect(api.archive(project, before, key))
      .rejects.toMatchObject({ code: "PROJECT_ARCHIVE_UNCERTAIN", uncertain: true });
  });

  it("treats mismatched ETag, bad envelope, mismatched error and disconnection as uncertain", async () => {
    const { api, fetcher } = await client(envelope(archived, 200, '"v2"'),
      new Response("ok", { status: 200, headers: { "Content-Type": "text/plain" } }),
      failure(403, "RESOURCE_NOT_FOUND"));
    for (let index = 0; index < 3; index += 1) {
      await expect(api.archive(project, before, key)).rejects.toMatchObject({ uncertain: true });
    }
    fetcher.mockRejectedValueOnce(new Error("synthetic disconnect"));
    await expect(api.archive(project, before, key)).rejects.toMatchObject({ uncertain: true });
    expect(fetcher).toHaveBeenCalledTimes(5);
  });
});
