import { describe, expect, it, vi } from "vitest";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { SurveyHandoverSourceClient } from "./surveyHandoverSourceClient";

const project = "01234567-89ab-4cde-8123-456789abcdef";
const analysis = "11234567-89ab-4cde-8123-456789abcdef";
const version = "21234567-89ab-4cde-8123-456789abcdef";
const row = "31234567-89ab-4cde-8123-456789abcdef";
const item = "41234567-89ab-4cde-8123-456789abcdef";
const actor = "51234567-89ab-4cde-8123-456789abcdef";
const trace = "61234567-89ab-4cde-8123-456789abcdef";
const token = `${"A".repeat(24)}.${"B".repeat(43)}`;
const candidate = { handover_item_row_id: row, handover_analysis_version_id: version,
  handover_analysis_id: analysis, analysis_item_id: item, project_id: project,
  title: "确认实施范围", state: "CONFIRMED" };
function response(data: unknown, status = 200): Response {
  return new Response(JSON.stringify({ data, trace_id: trace }), { status,
    headers: { "Content-Type": "application/json", "Cache-Control": "no-store",
      "X-Trace-Id": trace } });
}
function sessionData(role: string) {
  return { user: { user_id: actor, username_display: "合成用户" }, deployment_role: "NONE",
    password_change_required: false, authorized_projects: [{ project_id: project,
      name: "合成项目", role }], absolute_expires_at: "2030-01-01T12:00:00Z",
    idle_expires_at: "2030-01-01T11:00:00Z", csrf_token: "a".repeat(64) };
}
async function fixture(result: Response | Error, role = "PROJECT_MANAGER") {
  const fetcher = vi.fn().mockResolvedValueOnce(response(sessionData(role)));
  if (result instanceof Error) fetcher.mockRejectedValueOnce(result);
  else fetcher.mockResolvedValueOnce(result);
  const session = new SessionClient(fetcher as typeof fetch);
  await session.login("synthetic", "synthetic-only");
  return { client: new SurveyHandoverSourceClient(session, fetcher as typeof fetch), fetcher };
}

describe("SurveyHandoverSourceClient", () => {
  it("reads minimal current candidates with same-origin no-store and cursor", async () => {
    const { client, fetcher } = await fixture(response({ items: [candidate],
      next_cursor: token, has_more: true }));
    const page = await client.list(project, 1);
    expect(page.items[0]?.handover_item_row_id).toBe(row);
    expect(page.next_cursor).toBe(token);
    expect(fetcher.mock.calls[1]).toEqual([
      `/api/v1/projects/${project}/survey-handover-sources?page_size=1`,
      { method: "GET", credentials: "same-origin", cache: "no-store",
        redirect: "error", headers: { Accept: "application/json" } },
    ]);
  });

  it("denies customer role and malformed inputs before transport", async () => {
    const denied = await fixture(response({ items: [], next_cursor: null,
      has_more: false }), "CUSTOMER_MEMBER");
    await expect(denied.client.list(project)).rejects.toMatchObject({ code: "ACCESS_DENIED" });
    await expect(denied.client.list(actor)).rejects.toMatchObject({ code: "ACCESS_DENIED" });
    await expect(denied.client.list(project, 0)).rejects.toMatchObject({ code: "INVALID_INPUT" });
    await expect(denied.client.list(project, 1, "wrong" as never)).rejects.toMatchObject({ code: "INVALID_INPUT" });
    expect(denied.fetcher).toHaveBeenCalledTimes(1);
  });

  it("rejects foreign or malformed page, duplicate item, and lost transport", async () => {
    for (const data of [
      { items: [{ ...candidate, project_id: actor }], next_cursor: null, has_more: false },
      { items: [candidate, candidate], next_cursor: null, has_more: false },
      { items: [candidate], next_cursor: null, has_more: true },
      { items: [{ ...candidate, source_text: "forbidden" }], next_cursor: null,
        has_more: false },
    ]) {
      const { client } = await fixture(response(data));
      await expect(client.list(project, 2)).rejects.toMatchObject({ code: "UNAVAILABLE" });
    }
    const lost = await fixture(new Error("synthetic network loss"));
    await expect(lost.client.list(project)).rejects.toMatchObject({ code: "UNAVAILABLE" });
    expect(lost.fetcher).toHaveBeenCalledTimes(2);
  });

  it("maps current License and stale cursor denials without presenting a candidate", async () => {
    for (const [status, code] of [[403, "LICENSE_OPERATION_DENIED"],
      [400, "REQUEST_MALFORMED"]] as const) {
      const denied = new Response(JSON.stringify({ error: { code, message: "private" }, trace_id: trace }),
        { status, headers: { "Content-Type": "application/json", "Cache-Control": "no-store",
          "X-Trace-Id": trace } });
      const { client } = await fixture(denied);
      await expect(client.list(project)).rejects.toMatchObject({ code });
    }
  });
});
