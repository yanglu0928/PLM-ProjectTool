import { afterEach, describe, expect, it, vi } from "vitest";
import { JobDetailClient, JobDetailError } from "./jobDetailClient";

const projectId = "01234567-89ab-4cde-8123-456789abcdef";
const jobId = "11234567-89ab-4cde-8123-456789abcdef";
const otherId = "21234567-89ab-4cde-8123-456789abcdef";
const projectJob = { job_id: jobId, job_type: "DOCUMENT_PARSE", owner_module: "document", scope: "PROJECT",
  project_id: projectId, state: "RUNNING", progress: null, checkpoint: null, attempt_count: 1,
  retryable: false, error_code: null, result_ref: null, created_at: "2026-10-02T00:00:00Z",
  completed_at: null, etag: '"v1"' };
const globalJob = { ...projectJob, scope: "GLOBAL", project_id: null, job_type: "AUDIT_EXPORT", owner_module: "audit" };
function response(data: unknown, header: string | null = '"v1"'): Response {
  return new Response(JSON.stringify({ data, trace_id: projectId }), { status: 200,
    headers: { "Content-Type": "application/json", ...(header ? { ETag: header } : {}) } });
}
function failure(status: number, code: string): Response {
  return new Response(JSON.stringify({ error: { code, message: "private server detail" }, trace_id: projectId }),
    { status, headers: { "Content-Type": "application/json" } });
}
function setup(reply: Response) {
  const fetcher = vi.fn().mockResolvedValue(reply);
  return { api: new JobDetailClient(fetcher as typeof fetch), fetcher };
}

describe("JobDetailClient", () => {
  afterEach(() => { vi.restoreAllMocks(); vi.useRealTimers(); });

  it("reads project detail by canonical IDs, current Cookie and no cache", async () => {
    const { api, fetcher } = setup(response({ ...projectJob, private_payload: "secret" }));
    const item = await api.getProject(projectId, jobId);
    expect(fetcher).toHaveBeenCalledExactlyOnceWith(`/api/v1/projects/${projectId}/jobs/${jobId}`, expect.objectContaining({
      method: "GET", credentials: "same-origin", cache: "no-store", redirect: "error", headers: { Accept: "application/json" },
    }));
    expect(item).toMatchObject({ job_id: jobId, project_id: projectId, etag: '"v1"' });
    expect(JSON.stringify(item)).not.toContain("secret");
    expect(Object.isFrozen(item)).toBe(true);
  });

  it("uses distinct Admin route and rejects a project Job", async () => {
    const accepted = setup(response(globalJob));
    await expect(accepted.api.getAdmin(jobId)).resolves.toMatchObject({ scope: "GLOBAL", project_id: null });
    expect(accepted.fetcher.mock.calls[0][0]).toBe(`/api/v1/admin/jobs/${jobId}`);
    await expect(setup(response(projectJob)).api.getAdmin(jobId)).rejects.toMatchObject({ code: "JOB_DETAIL_UNAVAILABLE" });
  });

  it.each(["../admin", jobId.toUpperCase(), "00000000-0000-0000-0000-000000000000"])(
    "rejects unsafe Job ID before network: %s", async id => {
      const { api, fetcher } = setup(response(projectJob));
      await expect(api.getProject(projectId, id)).rejects.toMatchObject({ code: "JOB_DETAIL_INVALID_ID" });
      expect(fetcher).not.toHaveBeenCalled();
    });

  it.each([response({ ...projectJob, job_id: otherId }), response({ ...projectJob, project_id: otherId }),
    response(projectJob, null), response(projectJob, '"v2"'), response({ ...projectJob, result_ref: { type: "AUDIT_EXPORT", id: otherId } })])(
    "rejects mismatched item, binding, result or ETag %#", async reply => {
      await expect(setup(reply).api.getProject(projectId, jobId)).rejects.toMatchObject({ code: "JOB_DETAIL_UNAVAILABLE" });
    });

  it.each([[401, "AUTH_SESSION_EXPIRED"], [403, "LICENSE_OPERATION_DENIED"], [404, "RESOURCE_NOT_FOUND"]] as const)(
    "maps only matching safe error %s %s", async (status, code) => {
      const error = await setup(failure(status, code)).api.getProject(projectId, jobId).catch((value: unknown) => value);
      expect(error).toBeInstanceOf(JobDetailError);
      expect(error).toMatchObject({ code });
      expect(String(error)).not.toContain("private");
    });

  it("does not trust a mismatched error or HTML response", async () => {
    await expect(setup(failure(403, "RESOURCE_NOT_FOUND")).api.getProject(projectId, jobId))
      .rejects.toMatchObject({ code: "JOB_DETAIL_UNAVAILABLE" });
    const html = new Response("private", { status: 200, headers: { "Content-Type": "text/html" } });
    await expect(setup(html).api.getProject(projectId, jobId)).rejects.toMatchObject({ code: "JOB_DETAIL_UNAVAILABLE" });
  });

  it("aborts on timeout without retry or raw detail", async () => {
    vi.useFakeTimers();
    const fetcher = vi.fn().mockImplementation((_path: string, options: RequestInit) => new Promise((_resolve, reject) => {
      options.signal?.addEventListener("abort", () => reject(new Error("private timeout")));
    }));
    const pending = expect(new JobDetailClient(fetcher as typeof fetch, 100).getProject(projectId, jobId))
      .rejects.toMatchObject({ code: "JOB_DETAIL_UNAVAILABLE" });
    await vi.advanceTimersByTimeAsync(101);
    await pending;
    expect(fetcher).toHaveBeenCalledTimes(1);
  });
});
