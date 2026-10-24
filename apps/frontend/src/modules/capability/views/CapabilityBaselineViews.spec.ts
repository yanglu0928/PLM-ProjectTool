import { flushPromises, mount } from "@vue/test-utils";
import { createMemoryHistory } from "vue-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import { createAppRouter } from "@/app/router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { CapabilityReadClient } from "@/modules/capability/api/capabilityReadClient";
import CapabilityBaselineListView from "./CapabilityBaselineListView.vue";
import CapabilityBaselineDetailView from "./CapabilityBaselineDetailView.vue";

const actorId = "01234567-89ab-4cde-8123-456789abcdef";
const baselineId = "11234567-89ab-4cde-8123-456789abcdef";
const versionId = "21234567-89ab-4cde-8123-456789abcdef";
const traceId = "31234567-89ab-4cde-8123-456789abcdef";
const base = { baseline_id: baselineId, baseline_code: "STD-01", name: "全局标准能力",
  description: null, state: "ACTIVE", source_collection_ref: `sha256:${"a".repeat(64)}`,
  current_approved_version_ref: versionId as string | null, created_at: "2026-10-24T01:00:00Z",
  updated_at: "2026-10-24T01:00:00Z", etag: '"v1"' };
const version = { baseline_version_id: versionId, baseline_id: baselineId, version_no: 1,
  state: "APPROVED", source_collection_ref: base.source_collection_ref,
  content_fingerprint: "a".repeat(64), declared_item_count: 1, declared_document_ref_count: 0,
  declared_evidence_ref_count: 0, supersedes_version_ref: null, review_ref: null,
  review_round_ref: null, created_at: "2026-10-24T01:00:00Z" };
const item = { capability_item_id: traceId, baseline_version_id: versionId, baseline_id: baselineId,
  ordinal: 0, capability_code: "C-01", domain_name: "产品", module_name: "物料",
  feature_name: "管理", name: "标准物料", description: "说明", boundary: "边界",
  prerequisites: [], interface_refs: [], state: "AVAILABLE", document_version_refs: [], evidence_refs: [] } as const;
function response(data: unknown): Response { return new Response(JSON.stringify({ data, trace_id: traceId }),
  { status: 200, headers: { "Content-Type": "application/json" } }); }
function authView(admin: boolean) { return { user: { user_id: actorId, username_display: "合成用户" },
  deployment_role: admin ? "DEPLOYMENT_ADMIN" : "NONE", password_change_required: false,
  authorized_projects: admin ? [] : [{ project_id: traceId, name: "合成项目", role: "PROJECT_MANAGER" }],
  absolute_expires_at: "2030-01-01T12:00:00Z", idle_expires_at: "2030-01-01T11:00:00Z",
  csrf_token: "a".repeat(64) }; }
async function session(...roles: boolean[]): Promise<SessionClient> {
  const fetcher = vi.fn(); roles.forEach(role => fetcher.mockResolvedValueOnce(response(authView(role))));
  const result = new SessionClient(fetcher as typeof fetch);
  if (roles.length) await result.login("synthetic", "synthetic-only");
  return result;
}
function listClient(entry = base) { return { listBaselines: vi.fn().mockResolvedValue({ items: [entry],
  next_cursor: null, has_more: false }) } as unknown as CapabilityReadClient; }
function detailClient(entry = base, selected = version) { return {
  getBaseline: vi.fn().mockResolvedValue(entry),
  listVersions: vi.fn().mockResolvedValue({ items: [selected], next_cursor: null, has_more: false }),
  getVersion: vi.fn().mockResolvedValue(selected),
  listItems: vi.fn().mockResolvedValue({ items: [item], next_cursor: null, has_more: false }),
} as unknown as CapabilityReadClient; }
describe("Capability baseline views", () => {
  afterEach(() => vi.restoreAllMocks());
  it("denies an absent session before any list request", async () => {
    const router = createAppRouter(createMemoryHistory()); await router.push("/capability-baselines");
    const client = listClient(); const wrapper = mount(CapabilityBaselineListView,
      { props: { session: await session(), client }, global: { plugins: [router] } });
    await flushPromises();
    expect(wrapper.text()).toContain("请先登录");
    expect(client.listBaselines).not.toHaveBeenCalled(); wrapper.unmount();
  });
  it("lists a member's current-approved projection and rejects an unapproved server row", async () => {
    const router = createAppRouter(createMemoryHistory()); await router.push("/capability-baselines");
    const client = listClient(); const wrapper = mount(CapabilityBaselineListView,
      { props: { session: await session(false), client }, global: { plugins: [router] } });
    await flushPromises();
    expect(wrapper.text()).toContain("全局标准能力");
    expect(wrapper.text()).toContain("仅当前已批准基线"); wrapper.unmount();
    const bad = listClient({ ...base, current_approved_version_ref: null });
    const blocked = mount(CapabilityBaselineListView,
      { props: { session: await session(false), client: bad }, global: { plugins: [router] } });
    await flushPromises();
    expect(blocked.text()).not.toContain("STD-01 · 全局标准能力");
    expect(blocked.find('[role="alert"]').exists()).toBe(true); blocked.unmount();
  });
  it("reads the approved detail and item; member cannot display a returned version", async () => {
    const router = createAppRouter(createMemoryHistory());
    await router.push(`/capability-baselines/${baselineId}`);
    const client = detailClient(); const wrapper = mount(CapabilityBaselineDetailView,
      { props: { session: await session(false), client }, global: { plugins: [router] } });
    await flushPromises();
    expect(wrapper.text()).toContain("标准物料");
    expect(client.getVersion).toHaveBeenCalledWith(baselineId, versionId); wrapper.unmount();
    const bad = detailClient(base, { ...version, state: "RETURNED" });
    const blocked = mount(CapabilityBaselineDetailView,
      { props: { session: await session(false), client: bad }, global: { plugins: [router] } });
    await flushPromises();
    expect(blocked.text()).not.toContain("标准物料");
    expect(blocked.find('[role="alert"]').exists()).toBe(true); blocked.unmount();
  });
  it("clears administrator history when the same actor changes to member", async () => {
    const router = createAppRouter(createMemoryHistory()); await router.push("/capability-baselines");
    const auth = await session(true, false);
    const client = listClient({ ...base, current_approved_version_ref: null });
    const wrapper = mount(CapabilityBaselineListView,
      { props: { session: auth, client }, global: { plugins: [router] } });
    await flushPromises(); expect(wrapper.text()).toContain("STD-01 · 全局标准能力");
    await auth.login("synthetic", "synthetic-only"); await flushPromises();
    expect(wrapper.text()).not.toContain("STD-01 · 全局标准能力");
    expect(client.listBaselines).toHaveBeenCalledTimes(2); wrapper.unmount();
  });
});
