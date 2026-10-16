import { afterEach, describe, expect, it, vi } from "vitest";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { SectionCreateClient, normalizeSectionKey } from "./sectionCreateClient";

const project = "01234567-89ab-4cde-8123-456789abcdef";
const outline = "11234567-89ab-4cde-8123-456789abcdef";
const section = "21234567-89ab-4cde-8123-456789abcdef";
const trace = "31234567-89ab-4cde-8123-456789abcdef";
const key = "41234567-89ab-4cde-8123-456789abcdef";
const item = { solution_section_id: section, solution_outline_id: outline, project_id: project,
  section_key: "业务范围", section_state: "ACTIVE", current_approved_version_ref: null,
  created_at: "2026-10-09T00:00:00Z", etag: '"v0"' };
function response(data: unknown, status = 201, header = '"v0"'): Response {
  return new Response(JSON.stringify({ data, trace_id: trace }), { status,
    headers: { "Content-Type": "application/json", "Cache-Control": "no-store", ETag: header,
      "X-Trace-Id": trace, Location: `/api/v1/projects/${project}/solution-sections/${section}` } });
}
async function setup(role = "PROJECT_MANAGER", result: Response = response(item)) {
  const fetcher = vi.fn().mockResolvedValueOnce(new Response(JSON.stringify({ data: {
    user: { user_id: project, username_display: "合成用户" }, deployment_role: "NONE",
    password_change_required: false,
    authorized_projects: [{ project_id: project, name: "项目", role }],
    absolute_expires_at: "2030-01-01T12:00:00Z", idle_expires_at: "2030-01-01T11:00:00Z",
    csrf_token: "a".repeat(64),
  }, trace_id: trace }), { status: 200, headers: { "Content-Type": "application/json" } }))
    .mockResolvedValueOnce(result);
  const session = new SessionClient(fetcher as typeof fetch);
  await session.login("user", "synthetic-only");
  return { api: new SectionCreateClient(session), fetcher, session };
}

describe("SectionCreateClient", () => {
  afterEach(() => vi.restoreAllMocks());

  it("submits exact parent/key and verifies 201, ETag, Trace and detail Location", async () => {
    const { api, fetcher } = await setup();
    expect(await api.create(project, outline, "业务范围", key)).toEqual(item);
    expect(fetcher).toHaveBeenCalledTimes(2);
    expect(fetcher.mock.calls[1]?.[0]).toBe(`/api/v1/projects/${project}/solution-sections`);
    expect(fetcher.mock.calls[1]?.[1]).toMatchObject({ method: "POST",
      body: JSON.stringify({ solution_outline_id: outline, section_key: "业务范围" }),
      credentials: "same-origin", cache: "no-store", redirect: "error",
      headers: expect.objectContaining({ "Idempotency-Key": key, "X-CSRF-Token": "a".repeat(64) }) });
  });

  it("normalizes backend NFKC key and rejects malformed, reader or foreign writes before network", async () => {
    expect(normalizeSectionKey("  ＡＢ  ")).toBe("AB");
    expect(() => normalizeSectionKey("\u0000")).toThrow();
    const { api, fetcher } = await setup("CUSTOMER_MEMBER");
    await expect(api.create(project, outline, "业务范围", key))
      .rejects.toMatchObject({ code: "SECTION_CREATE_INVALID" });
    await expect(api.create(section, outline, "业务范围", key))
      .rejects.toMatchObject({ code: "SECTION_CREATE_INVALID" });
    await expect(api.create(project, "not-id", "业务范围", key))
      .rejects.toMatchObject({ code: "SECTION_CREATE_INVALID" });
    await expect(api.create(project, outline, " ＡＢ ", key))
      .rejects.toMatchObject({ code: "SECTION_CREATE_INVALID" });
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it("keeps malformed success, wrong parent/Location/ETag and unknown errors uncertain", async () => {
    for (const bad of [response({ ...item, solution_outline_id: section }),
      response(item, 201, '"v1"'),
      new Response(JSON.stringify({ data: item, trace_id: trace }), { status: 201,
        headers: { "Content-Type": "application/json", "Cache-Control": "no-store",
          ETag: '"v0"', "X-Trace-Id": trace,
          Location: `/api/v1/projects/${project}/solution-sections/${project}` } }),
      response({ error: { code: "UNKNOWN" } }, 500)]) {
      const { api } = await setup("PROJECT_MANAGER", bad);
      await expect(api.create(project, outline, "业务范围", key))
        .rejects.toMatchObject({ code: "SECTION_CREATE_UNCERTAIN", uncertain: true });
    }
  });

  it("maps known rejection without claiming commit", async () => {
    const bad = new Response(JSON.stringify({ error: { code: "CONFLICT_DUPLICATE", message: "duplicate" },
      trace_id: trace }), { status: 409, headers: { "Content-Type": "application/json",
        "Cache-Control": "no-store", "X-Trace-Id": trace } });
    const { api } = await setup("PROJECT_MANAGER", bad);
    await expect(api.create(project, outline, "业务范围", key))
      .rejects.toMatchObject({ code: "CONFLICT_DUPLICATE", uncertain: false });
  });

  it("keeps transport failures uncertain and performs no implicit retry", async () => {
    const { api, fetcher } = await setup();
    fetcher.mockReset().mockRejectedValueOnce(new Error("network"));
    await expect(api.create(project, outline, "业务范围", key))
      .rejects.toMatchObject({ code: "SECTION_CREATE_UNCERTAIN" });
    expect(fetcher).toHaveBeenCalledTimes(1);
  });
});
