import { defineComponent } from "vue";
import { flushPromises, mount } from "@vue/test-utils";
import { createMemoryHistory, createRouter } from "vue-router";
import { describe, expect, it, vi } from "vitest";

import { SessionClient } from "@/modules/auth/api/sessionClient";
import { PrototypeWriteError } from "@/modules/prototype/api/prototypeWriteClient";
import ProjectPrototypeDetailView from "./ProjectPrototypeDetailView.vue";
import ProjectPrototypeListView from "./ProjectPrototypeListView.vue";

const project = "01234567-89ab-4cde-8123-456789abcdef";
const prototype = "11234567-89ab-4cde-8123-456789abcdef";
const actor = "21234567-89ab-4cde-8123-456789abcdef";
const requirement = "31234567-89ab-4cde-8123-456789abcdef";
const requirementVersion = "41234567-89ab-4cde-8123-456789abcdef";
const trace = "51234567-89ab-4cde-8123-456789abcdef";
const now = "2026-10-08T12:00:00Z";
const root = { prototype_id: prototype, project_id: project, name: "交互原型", state: "ACTIVE" as const,
  current_approved_version_ref: null, created_by: actor, created_at: now, updated_by: null, updated_at: now, etag: '"v0"' };
const requirementItem = { requirement_id: requirement, project_id: project, requirement_code: "REQ-001", state: "ACTIVE" as const,
  current_approved_version_ref: requirementVersion, created_by: actor, created_at: now, updated_by: null, updated_at: now, etag: '"v0"' };
function json(data: unknown) { return new Response(JSON.stringify({ data, trace_id: trace }),
  { status: 200, headers: { "Content-Type": "application/json" } }); }
async function session() {
  const fetcher = vi.fn().mockResolvedValueOnce(json({ user: { user_id: actor, username_display: "项目经理" },
    deployment_role: "NONE", password_change_required: false,
    authorized_projects: [{ project_id: project, name: "PLM项目", role: "PROJECT_MANAGER" }],
    absolute_expires_at: "2030-01-01T12:00:00Z", idle_expires_at: "2030-01-01T11:00:00Z", csrf_token: "a".repeat(64) }));
  const value = new SessionClient(fetcher as typeof fetch); await value.login("manager", "synthetic"); return value;
}
const Dummy = defineComponent({ template: "<div />" });
function router(detail = false) {
  const value = createRouter({ history: createMemoryHistory(), routes: [
    { path: "/projects/:projectId", name: "project-detail", component: Dummy },
    { path: "/projects/:projectId/prototypes", name: "project-prototypes", component: Dummy },
    { path: "/projects/:projectId/prototypes/:prototypeId", name: "project-prototype-detail", component: Dummy },
    { path: "/projects/:projectId/prototypes/:prototypeId/versions", name: "project-prototype-versions", component: Dummy },
    { path: "/projects/:projectId/prototypes/:prototypeId/versions/:versionId", name: "project-prototype-version-detail", component: Dummy },
    { path: "/projects/:projectId/prototype-packages", name: "project-prototype-packages", component: Dummy },
    { path: "/projects/:projectId/prototype-templates", name: "project-prototype-templates", component: Dummy },
    { path: "/projects/:projectId/prototype-links", name: "project-prototype-links", component: Dummy },
  ] });
  void value.push(detail ? `/projects/${project}/prototypes/${prototype}` : `/projects/${project}/prototypes`); return value;
}

describe("Prototype list/detail structured pages", () => {
  it("explains fact boundaries and replays an uncertain create with the original key", async () => {
    const auth = await session(), appRouter = router(); await appRouter.isReady();
    const reader = { list: vi.fn().mockResolvedValueOnce({ items: [root], next_cursor: null, has_more: false })
      .mockResolvedValueOnce({ items: [root], next_cursor: null, has_more: false }) };
    const writer = { createPrototype: vi.fn().mockRejectedValueOnce(new PrototypeWriteError("PROTOTYPE_WRITE_UNAVAILABLE"))
      .mockResolvedValueOnce({ prototype_id: prototype, project_id: project, name: "新原型", state: "ACTIVE",
        current_approved_version_ref: null, etag: '"v0"' }) };
    const wrapper = mount(ProjectPrototypeListView, { props: { session: auth, reader: reader as never, writer: writer as never },
      global: { plugins: [appRouter] } }); await flushPromises();
    expect(wrapper.text()).toContain("模板和 AI 输出只是辅助输入"); expect(wrapper.text()).toContain("没有原型");
    await wrapper.get('input:not([type])').setValue("新原型"); await wrapper.get('input[type="checkbox"]').setValue(true);
    await wrapper.get("form").trigger("submit"); await flushPromises();
    expect(wrapper.text()).toContain("上次创建结果未知");
    const firstKey = writer.createPrototype.mock.calls[0]![2];
    await wrapper.get("aside button").trigger("click"); await flushPromises();
    expect(writer.createPrototype).toHaveBeenCalledTimes(2); expect(writer.createPrototype.mock.calls[1]![2]).toBe(firstKey);
    expect(wrapper.text()).toContain("已创建"); expect(reader.list).toHaveBeenCalledTimes(2);
  });

  it("uses approved Requirement choices and reconciles uncertain PATCH by independent GET", async () => {
    const auth = await session(), appRouter = router(true); await appRouter.isReady();
    const identities = { get: vi.fn().mockResolvedValueOnce(root).mockResolvedValueOnce({ ...root, name: "更新名称", etag: '"v1"' }) };
    const versions = { list: vi.fn().mockResolvedValue({ items: [], next_cursor: null, has_more: false }) };
    const requirements = { listRequirements: vi.fn().mockResolvedValue({ items: [requirementItem], next_cursor: null, has_more: false }) };
    const writer = { patchPrototype: vi.fn().mockRejectedValue(new PrototypeWriteError("PROTOTYPE_WRITE_UNAVAILABLE")),
      markNotRequired: vi.fn(), archivePrototype: vi.fn() };
    const wrapper = mount(ProjectPrototypeDetailView, { props: { session: auth, identities: identities as never,
      versions: versions as never, requirements: requirements as never, writer: writer as never }, global: { plugins: [appRouter] } });
    await flushPromises(); expect(wrapper.text()).toContain("需要人工选择固定模板、批准需求和文档制品");
    expect(wrapper.text()).toContain("REQ-001"); expect(wrapper.find(`input[value="${requirementVersion}"]`).exists()).toBe(true);
    const renameForm = wrapper.findAll("form")[0]!; await renameForm.get('input:not([type])').setValue("更新名称");
    await renameForm.get('input[type="checkbox"]').setValue(true); await renameForm.trigger("submit"); await flushPromises();
    expect(writer.patchPrototype).toHaveBeenCalledTimes(1); expect(identities.get).toHaveBeenCalledTimes(2);
    expect(wrapper.text()).toContain("独立GET已证明名称更新成功"); expect(wrapper.text()).toContain("更新名称");
    expect(wrapper.text()).toContain("不能以空列表代替决定"); expect(wrapper.text()).toContain("不是AI自动判断");
  });
});
