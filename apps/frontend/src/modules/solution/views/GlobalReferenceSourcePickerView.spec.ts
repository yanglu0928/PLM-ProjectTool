import { flushPromises, mount } from "@vue/test-utils";
import { createMemoryHistory } from "vue-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { createAppRouter } from "@/app/router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import type { EvidenceListClient } from "@/modules/evidence/api/evidenceListClient";
import type { EvidenceViewerClient } from "@/modules/evidence/api/evidenceViewerClient";
import type { EvidenceEligibilityClient } from "@/modules/evidence/api/evidenceEligibilityClient";
import GlobalReferenceSourcePickerView from "./GlobalReferenceSourcePickerView.vue";

const actor = "01234567-89ab-4cde-8123-456789abcdef";
const documentA = "11234567-89ab-4cde-8123-456789abcdef";
const documentB = "21234567-89ab-4cde-8123-456789abcdef";
const versionA = "31234567-89ab-4cde-8123-456789abcdef";
const versionB = "41234567-89ab-4cde-8123-456789abcdef";
const evidenceA = "51234567-89ab-4cde-8123-456789abcdef";
const evidenceB = "61234567-89ab-4cde-8123-456789abcdef";
const evidenceC = "71234567-89ab-4cde-8123-456789abcdef";
const trace = "81234567-89ab-4cde-8123-456789abcdef";
const item = (evidenceId: string, documentId: string, versionId: string,
  eligibilityState: "ELIGIBLE" | "CANDIDATE" = "ELIGIBLE") => ({
  evidence_id: evidenceId, document_id: documentId, document_version_id: versionId,
  display_label: `来源 ${evidenceId.slice(0, 2)}`, display_excerpt: null,
  eligibility_state: eligibilityState, created_at: "2026-10-09T00:00:00Z",
});
const first = item(evidenceA, documentA, versionA);
const second = item(evidenceB, documentA, versionA);
const third = item(evidenceC, documentB, versionB);
const descriptor = (entry: typeof first) => ({ ...entry, document_version_no: 1,
  detected_mime: "text/plain", size_bytes: 12, locator: { locator_type: "DOCUMENT" },
  precision: "DOCUMENT", short_preview: null,
  content_url: `/api/v1/global/documents/${entry.document_id}/versions/${entry.document_version_id}/content`,
});
function envelope(data: unknown): Response {
  return new Response(JSON.stringify({ data, trace_id: trace }), { status: 200,
    headers: { "Content-Type": "application/json" } });
}
async function session(admin = true): Promise<SessionClient> {
  const api = new SessionClient(vi.fn().mockResolvedValue(envelope({
    user: { user_id: actor, username_display: "Synthetic" },
    deployment_role: admin ? "DEPLOYMENT_ADMIN" : "NONE",
    password_change_required: false, authorized_projects: [],
    absolute_expires_at: "2030-01-01T12:00:00Z", idle_expires_at: "2030-01-01T11:00:00Z",
    csrf_token: "a".repeat(64),
  })) as typeof fetch);
  await api.login("synthetic", "synthetic-only");
  return api;
}
async function view(admin: boolean, pages: unknown[], currentState = "ELIGIBLE") {
  const list = vi.fn(); for (const page of pages) list.mockResolvedValueOnce(page);
  const get = vi.fn().mockImplementation(async (_scope, evidenceId) =>
    descriptor([first, second, third].find((entry) => entry.evidence_id === evidenceId)!));
  const currentGlobal = vi.fn().mockImplementation(async (evidenceId) => {
    const entry = [first, second, third].find((candidate) => candidate.evidence_id === evidenceId)!;
    return { evidence_id: entry.evidence_id, document_id: entry.document_id,
      document_version_id: entry.document_version_id, eligibility_state: currentState, etag: '"v1"' };
  });
  const router = createAppRouter(createMemoryHistory());
  await router.push("/admin/reference-deidentification"); await router.isReady();
  const wrapper = mount(GlobalReferenceSourcePickerView, { props: {
    session: await session(admin), listClient: { list } as unknown as EvidenceListClient,
    viewerClient: { get } as unknown as EvidenceViewerClient,
    eligibilityClient: { currentGlobal } as unknown as EvidenceEligibilityClient,
  }, global: { plugins: [router] } });
  await flushPromises();
  return { wrapper, list, get, currentGlobal };
}
function button(wrapper: Awaited<ReturnType<typeof view>>["wrapper"], label: string) {
  return wrapper.findAll("button").find((entry) => entry.text() === label)!;
}

describe("GlobalReferenceSourcePickerView", () => {
  afterEach(() => { vi.restoreAllMocks(); });

  it("keeps ordered Evidence while counting the same fixed document once", async () => {
    const result = await view(true, [{ items: [first, second], next_cursor: "next", has_more: true },
      { items: [third], next_cursor: null, has_more: false }]);
    expect(result.list).toHaveBeenCalledWith({ kind: "GLOBAL" }, null);
    await result.wrapper.findAll("button").filter((entry) => entry.text() === "加入核查候选")[0]!.trigger("click");
    await flushPromises();
    await result.wrapper.findAll("button").filter((entry) => entry.text() === "加入核查候选")[1]!.trigger("click");
    await flushPromises();
    expect(result.wrapper.text()).toContain("2 条证据、1 个固定文档版本");
    await button(result.wrapper, "继续加载").trigger("click"); await flushPromises();
    expect(result.list).toHaveBeenLastCalledWith({ kind: "GLOBAL" }, "next");
    await result.wrapper.findAll("button").filter((entry) => entry.text() === "加入核查候选")[2]!.trigger("click");
    await flushPromises();
    expect(result.wrapper.text()).toContain("3 条证据、2 个固定文档版本");
    expect(result.wrapper.findAll('ol[aria-label="已选固定来源"] li a')).toHaveLength(3);
    expect(result.wrapper.text()).toContain("本页不能提交");
    expect(result.wrapper.text()).not.toContain("提交人工脱敏确认");
  });

  it("rejects stale eligibility and clears the collection on refresh", async () => {
    const result = await view(true, [{ items: [first], next_cursor: null, has_more: false },
      { items: [first], next_cursor: null, has_more: false }], "REVOKED");
    await button(result.wrapper, "加入核查候选").trigger("click"); await flushPromises();
    expect(result.wrapper.text()).toContain("固定来源已变化");
    expect(result.wrapper.text()).toContain("0 条证据");
    await button(result.wrapper, "重新读取并清空候选").trigger("click"); await flushPromises();
    expect(result.wrapper.text()).not.toContain("固定来源已变化");
  });

  it("does not list or reveal candidates to a non-admin", async () => {
    const result = await view(false, []);
    expect(result.list).not.toHaveBeenCalled();
    expect(result.wrapper.text()).toContain("需要当前 DeploymentAdmin");
    expect(result.wrapper.find('ol[aria-label="已选固定来源"]').exists()).toBe(false);
  });
});
