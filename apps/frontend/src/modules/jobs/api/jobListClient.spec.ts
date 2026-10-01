import { afterEach, describe, expect, it, vi } from "vitest";
import { JobListClient, JobListError } from "./jobListClient";

const projectId = "01234567-89ab-4cde-8123-456789abcdef";
const jobId = "11234567-89ab-4cde-8123-456789abcdef";
const traceId = "21234567-89ab-4cde-8123-456789abcdef";
const token = "j1.ABC_def-123";
const item = { job_id: jobId, job_type: "DOCUMENT_PARSE", owner_module: "document", scope: "PROJECT",
  project_id: projectId, state: "RUNNING", progress: null, checkpoint: null, attempt_count: 1,
  retryable: false, error_code: null, result_ref: null, created_at: "2026-10-02T00:00:00.123456Z",
  completed_at: null, etag: '"v1"' };
function success(data: unknown): Response {
  return new Response(JSON.stringify({ data, trace_id: traceId }), { status: 200, headers: { "Content-Type": "application/json" } });
}
function failure(status: number, code: string): Response {
  return new Response(JSON.stringify({ error: { code, message: "private detail" }, trace_id: traceId }),
    { status, headers: { "Content-Type": "application/json" } });
}
function setup(response: Response) {
  const fetcher = vi.fn().mockResolvedValue(response);
  return { api: new JobListClient(fetcher as typeof fetch), fetcher };
}

describe("JobListClient", () => {
  afterEach(() => { vi.restoreAllMocks(); vi.useRealTimers(); });

  it("reads only a same-origin project page and strips extra server fields", async () => {
    const { api, fetcher } = setup(success({ items: [{ ...item, private_payload: "secret" }], next_cursor: token, has_more: true }));
    const page = await api.listProject(projectId, 20);
    expect(fetcher).toHaveBeenCalledExactlyOnceWith(`/api/v1/projects/${projectId}/jobs?page_size=20`, expect.objectContaining({
      method: "GET", credentials: "same-origin", cache: "no-store", redirect: "error", headers: { Accept: "application/json" },
    }));
    expect(page.has_more).toBe(true);
    expect(page.next_cursor).toBe(token);
    expect(page.items[0]).toMatchObject({ job_id: jobId, state: "RUNNING", project_id: projectId });
    expect(JSON.stringify(page)).not.toContain("secret");
    expect(Object.isFrozen(page.items[0])).toBe(true);
  });

  it("passes the opaque cursor without decoding it", async () => {
    const { api, fetcher } = setup(success({ items: [], next_cursor: null, has_more: false }));
    await api.listProject(projectId, 50, token);
    expect(fetcher.mock.calls[0][0]).toBe(`/api/v1/projects/${projectId}/jobs?page_size=50&cursor=j1.ABC_def-123`);
  });

  it("keeps the Admin route and Scope distinct from project reads", async () => {
    const global = { ...item, scope: "GLOBAL", project_id: null, owner_module: "audit", job_type: "AUDIT_EXPORT" };
    const { api, fetcher } = setup(success({ items: [global], next_cursor: null, has_more: false }));
    await expect(api.listAdmin("GLOBAL")).resolves.toMatchObject({ items: [{ scope: "GLOBAL", project_id: null }] });
    expect(fetcher.mock.calls[0][0]).toBe("/api/v1/admin/jobs?page_size=50&scope=GLOBAL");
  });

  it.each(["../admin", "00000000-0000-0000-0000-000000000000", projectId.toUpperCase()])(
    "rejects unsafe project id before network: %s", async id => {
      const { api, fetcher } = setup(success({ items: [], next_cursor: null, has_more: false }));
      await expect(api.listProject(id)).rejects.toMatchObject({ code: "JOB_LIST_INVALID_INPUT" });
      expect(fetcher).not.toHaveBeenCalled();
    });

  it.each([0, 201, 1.5, NaN])("rejects invalid page size %s", async size => {
    const { api, fetcher } = setup(success({ items: [], next_cursor: null, has_more: false }));
    await expect(api.listProject(projectId, size)).rejects.toMatchObject({ code: "JOB_LIST_INVALID_INPUT" });
    expect(fetcher).not.toHaveBeenCalled();
  });

  it("rejects malformed cursor before network", async () => {
    const { api, fetcher } = setup(success({ items: [], next_cursor: null, has_more: false }));
    await expect(api.listProject(projectId, 50, "../secret")).rejects.toMatchObject({ code: "JOB_LIST_INVALID_INPUT" });
    expect(fetcher).not.toHaveBeenCalled();
  });

  it.each([
    { ...item, project_id: traceId }, { ...item, scope: "GLOBAL", project_id: null },
    { ...item, state: "SUCCEEDED" }, { ...item, progress: "private" },
    { ...item, etag: 'W/"v1"' }, { ...item, result_ref: { type: "AUDIT_EXPORT", id: traceId } },
  ])("rejects inconsistent or cross-scope item %#", async bad => {
    const { api } = setup(success({ items: [bad], next_cursor: null, has_more: false }));
    await expect(api.listProject(projectId)).rejects.toMatchObject({ code: "JOB_LIST_UNAVAILABLE" });
  });

  it.each([
    { items: [], next_cursor: token, has_more: false }, { items: [], next_cursor: token, has_more: true },
    { items: [item, item], next_cursor: null, has_more: false }, { items: null, next_cursor: null, has_more: false },
  ])("rejects malformed page %#", async data => {
    const { api } = setup(success(data));
    await expect(api.listProject(projectId)).rejects.toMatchObject({ code: "JOB_LIST_UNAVAILABLE" });
  });

  it.each([[401, "AUTH_SESSION_EXPIRED"], [403, "LICENSE_OPERATION_DENIED"], [404, "RESOURCE_NOT_FOUND"]] as const)(
    "maps only matching safe error %s %s", async (status, code) => {
      const { api } = setup(failure(status, code));
      const error = await api.listProject(projectId).catch((value: unknown) => value);
      expect(error).toBeInstanceOf(JobListError);
      expect(error).toMatchObject({ code });
      expect(String(error)).not.toContain("private");
    });

  it("does not expose mismatched error or HTML", async () => {
    await expect(setup(failure(403, "RESOURCE_NOT_FOUND")).api.listProject(projectId)).rejects.toMatchObject({ code: "JOB_LIST_UNAVAILABLE" });
    await expect(setup(new Response("private", { headers: { "Content-Type": "text/html" } })).api.listProject(projectId))
      .rejects.toMatchObject({ code: "JOB_LIST_UNAVAILABLE" });
  });

  it("aborts timeout without retrying or leaking details", async () => {
    vi.useFakeTimers();
    const fetcher = vi.fn().mockImplementation((_path: string, options: RequestInit) => new Promise((_resolve, reject) => {
      options.signal?.addEventListener("abort", () => reject(new Error("private timeout")));
    }));
    const pending = expect(new JobListClient(fetcher as typeof fetch, 100).listProject(projectId))
      .rejects.toMatchObject({ code: "JOB_LIST_UNAVAILABLE" });
    await vi.advanceTimersByTimeAsync(101);
    await pending;
    expect(fetcher).toHaveBeenCalledTimes(1);
  });
});
