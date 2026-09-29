import { flushPromises, mount } from "@vue/test-utils";
import { createMemoryHistory } from "vue-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { createAppRouter } from "@/app/router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { ProjectReadClient, type ProjectView } from "@/modules/project/api/projectReadClient";
import { ProjectArchiveClient, ProjectArchiveError,
  type ProjectArchiveFirstReceipt } from "@/modules/project/api/projectArchiveClient";
import { ProjectPatchClient, ProjectPatchError } from "@/modules/project/api/projectPatchClient";
import ProjectDetailView from "./ProjectDetailView.vue";

const id = "01234567-89ab-4cde-8123-456789abcdef";
const otherId = "11234567-89ab-4cde-8123-456789abcdef";
const project: ProjectView = { project_id: id, code: "TEST", name: "合成项目", state: "ACTIVE",
  created_at: "2026-09-28T08:30:00Z", etag: '"v0"' };
function response(data: unknown, etag?: string) {
  return new Response(JSON.stringify({ data, trace_id: id }),
    { headers: { "Content-Type": "application/json", ...(etag ? { ETag: etag } : {}) } });
}
function failure(status: number, code: string) {
  return new Response(JSON.stringify({ error: { code, message: "private details" }, trace_id: id }),
    { status, headers: { "Content-Type": "application/json" } });
}
async function session(restricted = false, manager = false): Promise<SessionClient> {
  const api = new SessionClient(vi.fn().mockResolvedValue(response({
    user: { user_id: id, username_display: "合成用户" }, deployment_role: "NONE",
    password_change_required: restricted, authorized_projects: manager
      ? [{ project_id: id, name: "合成项目", role: "PROJECT_MANAGER" }] : [],
    absolute_expires_at: "2030-01-01T12:00:00Z", idle_expires_at: "2030-01-01T11:00:00Z",
    csrf_token: "a".repeat(64),
  })) as typeof fetch);
  await api.login("user", "synthetic-only");
  return api;
}
async function view(auth: SessionClient, path: string, fetcher: typeof fetch,
  archiver?: ProjectArchiveClient, patcher?: ProjectPatchClient) {
  const router = createAppRouter(createMemoryHistory());
  await router.push(path);
  await router.isReady();
  const wrapper = mount(ProjectDetailView, { props: { session: auth,
    projects: new ProjectReadClient(fetcher), archiver, patcher },
    global: { plugins: [router] } });
  await flushPromises();
  return { wrapper, router };
}

describe("ProjectDetailView", () => {
  afterEach(() => vi.restoreAllMocks());

  it("does not fetch with no in-memory identity or restricted password session", async () => {
    const fetcher = vi.fn();
    const absent = await view(new SessionClient(fetcher as typeof fetch), `/projects/${id}`, fetcher as typeof fetch);
    expect(absent.wrapper.text()).toContain("尚未读取当前身份");
    absent.wrapper.unmount();
    const restricted = await view(await session(true), `/projects/${id}`, fetcher as typeof fetch);
    expect(restricted.wrapper.text()).toContain("须先修改密码");
    expect(fetcher).not.toHaveBeenCalled();
    restricted.wrapper.unmount();
  });

  it("loads only server-confirmed detail for direct URL and escapes display text", async () => {
    const fetcher = vi.fn().mockResolvedValue(response({ ...project, name: "<img src=x>" }, project.etag));
    const { wrapper } = await view(await session(), `/projects/${id}`, fetcher as typeof fetch);
    expect(wrapper.text()).toContain("<img src=x>");
    expect(wrapper.find("img").exists()).toBe(false);
    expect(wrapper.get('dl[aria-label="当前授权项目详情"]')).toBeTruthy();
    expect(wrapper.get('a[href="/projects/' + id + '/members"]').text()).toContain("成员历史");
    expect(fetcher).toHaveBeenCalledTimes(1);
    expect(fetcher.mock.calls[0][0]).toBe(`/api/v1/projects/${id}`);
    wrapper.unmount();
  });

  it.each([[404, "RESOURCE_NOT_FOUND", "项目不存在或无权查看"],
    [401, "AUTH_SESSION_EXPIRED", "会话已失效"],
    [403, "LICENSE_OPERATION_DENIED", "当前许可不允许查看项目"]] as const)(
    "safely handles direct URL rejection %s %s", async (status, code, message) => {
      const fetcher = vi.fn().mockResolvedValue(failure(status, code));
      const { wrapper } = await view(await session(), `/projects/${id}`, fetcher as typeof fetch);
      expect(wrapper.get('[role="alert"]').text()).toContain(message);
      expect(wrapper.find("dl").exists()).toBe(false);
      expect(wrapper.html()).not.toContain("private details");
      wrapper.unmount();
    });

  it("rejects an unsafe path ID before network access", async () => {
    const fetcher = vi.fn();
    const { wrapper } = await view(await session(), "/projects/not-an-id", fetcher as typeof fetch);
    expect(wrapper.get('[role="alert"]').text()).toContain("项目标识无效");
    expect(fetcher).not.toHaveBeenCalled();
    wrapper.unmount();
  });

  it("clears prior detail when navigating to another project whose server response is 404", async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(response(project, project.etag))
      .mockResolvedValueOnce(failure(404, "RESOURCE_NOT_FOUND"));
    const { wrapper, router } = await view(await session(), `/projects/${id}`, fetcher as typeof fetch);
    expect(wrapper.text()).toContain(project.name);
    await router.push(`/projects/${otherId}`);
    await flushPromises();
    expect(wrapper.text()).not.toContain(project.name);
    expect(wrapper.get('[role="alert"]').text()).toContain("项目不存在或无权查看");
    expect(fetcher).toHaveBeenCalledTimes(2);
    wrapper.unmount();
  });

  it("rejects a response with a different ID or ETag instead of showing it", async () => {
    const fetcher = vi.fn().mockResolvedValue(response({ ...project, project_id: otherId }, project.etag));
    const { wrapper } = await view(await session(), `/projects/${id}`, fetcher as typeof fetch);
    expect(wrapper.get('[role="alert"]').text()).toContain("暂时无法读取项目");
    expect(wrapper.find("dl").exists()).toBe(false);
    wrapper.unmount();
  });

  it("offers one-way archive only to the current manager of an active project", async () => {
    const fetcher = vi.fn().mockImplementation(() => Promise.resolve(response(project, project.etag)));
    const reader = await view(await session(), `/projects/${id}`, fetcher as typeof fetch);
    expect(reader.wrapper.text()).not.toContain("归档此项目");
    reader.wrapper.unmount();
    const auth = await session(false, true);
    const manager = await view(auth, `/projects/${id}`, fetcher as typeof fetch);
    expect(manager.wrapper.get("button").text()).toContain("刷新项目详情");
    expect(manager.wrapper.text()).toContain("归档此项目");
    manager.wrapper.unmount();
    const archived = await view(auth, `/projects/${id}`, vi.fn().mockResolvedValue(
      response({ ...project, state: "ARCHIVED", etag: '"v1"' }, '"v1"')) as typeof fetch);
    expect(archived.wrapper.text()).toContain("已归档");
    expect(archived.wrapper.text()).not.toContain("归档此项目");
    archived.wrapper.unmount();
  });

  it("offers name edit only to the current manager of an active project", async () => {
    const fetcher = vi.fn().mockImplementation(() => Promise.resolve(response(project, project.etag)));
    const reader = await view(await session(), `/projects/${id}`, fetcher as typeof fetch);
    expect(reader.wrapper.text()).not.toContain("修改项目名称");
    reader.wrapper.unmount();
    const auth = await session(false, true);
    const manager = await view(auth, `/projects/${id}`, fetcher as typeof fetch);
    expect(manager.wrapper.text()).toContain("修改项目名称");
    manager.wrapper.unmount();
    const archived = await view(auth, `/projects/${id}`, vi.fn().mockResolvedValue(
      response({ ...project, state: "ARCHIVED", etag: '"v1"' }, '"v1"')) as typeof fetch);
    expect(archived.wrapper.text()).not.toContain("修改项目名称");
    archived.wrapper.unmount();
  });

  it("requires name confirmation and separates PATCH receipt from a fresh project GET", async () => {
    const auth = await session(false, true);
    const patcher = new ProjectPatchClient(auth);
    const patch = vi.spyOn(patcher, "patch").mockResolvedValue({ ...project, name: "新项目", etag: '"v1"' });
    const fetcher = vi.fn().mockResolvedValueOnce(response(project, project.etag))
      .mockResolvedValueOnce(response({ ...project, name: "新项目", etag: '"v1"' }, '"v1"'));
    const { wrapper } = await view(auth, `/projects/${id}`, fetcher as typeof fetch, undefined, patcher);
    await wrapper.findAll("button").find((button) => button.text() === "修改项目名称")!.trigger("click");
    expect(wrapper.text()).toContain("不修改项目编号");
    expect(wrapper.text()).not.toContain("归档此项目");
    expect(wrapper.get('form button[type="submit"]').attributes("disabled")).toBeDefined();
    await wrapper.get('form input[type="text"]').setValue("新项目");
    await wrapper.get('form input[type="checkbox"]').setValue(true);
    await wrapper.get("form").trigger("submit");
    await flushPromises();
    expect(patch.mock.calls[0]).toEqual([id, project, "新项目"]);
    expect(wrapper.text()).toContain("本次名称修改回执");
    expect(wrapper.text()).toContain("不是独立的当前状态证明");
    expect(wrapper.find("dl").exists()).toBe(false);
    await wrapper.findAll("button").find((button) => button.text() === "刷新项目详情")!.trigger("click");
    await flushPromises();
    expect(wrapper.get("dl").text()).toContain("新项目");
    expect(wrapper.text()).not.toContain("本次名称修改回执");
    wrapper.unmount();
  });

  it("resets name confirmation when edited and allows the same name only after confirmation", async () => {
    const auth = await session(false, true);
    const patcher = new ProjectPatchClient(auth);
    const patch = vi.spyOn(patcher, "patch").mockResolvedValue({ ...project, etag: '"v1"' });
    const { wrapper } = await view(auth, `/projects/${id}`,
      vi.fn().mockResolvedValue(response(project, project.etag)) as typeof fetch, undefined, patcher);
    await wrapper.findAll("button").find((button) => button.text() === "修改项目名称")!.trigger("click");
    await wrapper.get('form input[type="checkbox"]').setValue(true);
    await wrapper.get('form input[type="text"]').setValue("临时名称");
    expect(wrapper.get('form input[type="checkbox"]').element).toHaveProperty("checked", false);
    await wrapper.get('form input[type="text"]').setValue(project.name);
    await wrapper.get('form input[type="checkbox"]').setValue(true);
    await wrapper.get("form").trigger("submit");
    await flushPromises();
    expect(patch).toHaveBeenCalledWith(id, project, project.name);
    wrapper.unmount();
  });

  it("clears stale detail after a known refusal or uncertain PATCH and requires fresh read", async () => {
    for (const code of ["CONFLICT_VERSION", "PROJECT_PATCH_UNCERTAIN"] as const) {
      const auth = await session(false, true);
      const patcher = new ProjectPatchClient(auth);
      const patch = vi.spyOn(patcher, "patch").mockRejectedValue(new ProjectPatchError(code));
      const fetcher = vi.fn().mockResolvedValueOnce(response(project, project.etag))
        .mockResolvedValueOnce(failure(503, "SYSTEM_UNAVAILABLE"))
        .mockResolvedValueOnce(response(project, project.etag));
      const { wrapper } = await view(auth, `/projects/${id}`, fetcher as typeof fetch, undefined, patcher);
      await wrapper.findAll("button").find((button) => button.text() === "修改项目名称")!.trigger("click");
      await wrapper.get('form input[type="checkbox"]').setValue(true);
      await wrapper.get("form").trigger("submit");
      await flushPromises();
      expect(wrapper.find("dl").exists()).toBe(false);
      expect(wrapper.text()).toContain(code === "CONFLICT_VERSION" ? "项目信息已变化" : "结果无法确认");
      expect(wrapper.text()).not.toContain("修改项目名称");
      await wrapper.get("button").trigger("click");
      await flushPromises();
      expect(wrapper.find("dl").exists()).toBe(false);
      await wrapper.get("button").trigger("click");
      await flushPromises();
      expect(wrapper.get("dl").text()).toContain(project.name);
      expect(patch).toHaveBeenCalledTimes(1);
      wrapper.unmount();
    }
  });

  it("discards a name PATCH result after switching projects", async () => {
    const auth = await session(false, true);
    const patcher = new ProjectPatchClient(auth);
    let finish!: (value: ProjectView) => void;
    vi.spyOn(patcher, "patch").mockReturnValue(new Promise((resolve) => { finish = resolve; }));
    const fetcher = vi.fn().mockResolvedValueOnce(response(project, project.etag))
      .mockResolvedValueOnce(failure(404, "RESOURCE_NOT_FOUND"));
    const { wrapper, router } = await view(auth, `/projects/${id}`, fetcher as typeof fetch, undefined, patcher);
    await wrapper.findAll("button").find((button) => button.text() === "修改项目名称")!.trigger("click");
    await wrapper.get('form input[type="checkbox"]').setValue(true);
    await wrapper.get("form").trigger("submit");
    await router.push(`/projects/${otherId}`);
    await flushPromises();
    finish({ ...project, name: "迟到名称", etag: '"v1"' });
    await flushPromises();
    expect(wrapper.text()).not.toContain("迟到名称");
    expect(wrapper.text()).not.toContain("本次名称修改回执");
    expect(wrapper.get('[role="alert"]').text()).toContain("项目不存在或无权查看");
    wrapper.unmount();
  });

  it("requires explicit impact confirmation, then separates first receipt from current detail", async () => {
    const auth = await session(false, true);
    const archiver = new ProjectArchiveClient(auth);
    const archive = vi.spyOn(archiver, "archive").mockResolvedValue({
      first_result: { ...project, state: "ARCHIVED", etag: '"v1"' }, is_current_state_proof: false,
    });
    const fetcher = vi.fn().mockResolvedValueOnce(response(project, project.etag))
      .mockResolvedValueOnce(response({ ...project, state: "ARCHIVED", etag: '"v1"' }, '"v1"'));
    const { wrapper } = await view(auth, `/projects/${id}`, fetcher as typeof fetch, archiver);
    await wrapper.findAll("button").find((button) => button.text() === "归档此项目")!.trigger("click");
    expect(wrapper.text()).toContain("首版没有普通反归档入口");
    expect(wrapper.get('form button[type="submit"]').attributes("disabled")).toBeDefined();
    await wrapper.get('form input[type="checkbox"]').setValue(true);
    await wrapper.get("form").trigger("submit");
    await flushPromises();
    expect(archive).toHaveBeenCalledTimes(1);
    expect(archive.mock.calls[0]?.[0]).toBe(id);
    expect(archive.mock.calls[0]?.[1]).toEqual(project);
    expect(archive.mock.calls[0]?.[2]).toMatch(/^[0-9a-f-]{36}$/);
    expect(wrapper.text()).toContain("本次归档首次回执");
    expect(wrapper.text()).toContain("不是当前状态证明");
    expect(wrapper.find("dl").exists()).toBe(false);
    await wrapper.get("button").trigger("click");
    await flushPromises();
    expect(wrapper.text()).toContain("已归档");
    expect(wrapper.text()).not.toContain("归档此项目");
    expect(wrapper.text()).not.toContain("本次归档首次回执");
    wrapper.unmount();
  });

  it("retains only the original key after unknown result and requires matching fresh detail", async () => {
    const auth = await session(false, true);
    const archiver = new ProjectArchiveClient(auth);
    const archive = vi.spyOn(archiver, "archive")
      .mockRejectedValueOnce(new ProjectArchiveError("PROJECT_ARCHIVE_UNCERTAIN"))
      .mockResolvedValueOnce({ first_result: { ...project, state: "ARCHIVED", etag: '"v1"' },
        is_current_state_proof: false });
    const fetcher = vi.fn().mockResolvedValueOnce(response(project, project.etag))
      .mockResolvedValueOnce(failure(503, "SYSTEM_UNAVAILABLE"))
      .mockResolvedValueOnce(response(project, project.etag));
    const { wrapper } = await view(auth, `/projects/${id}`, fetcher as typeof fetch, archiver);
    await wrapper.findAll("button").find((button) => button.text() === "归档此项目")!.trigger("click");
    await wrapper.get('form input[type="checkbox"]').setValue(true);
    await wrapper.get("form").trigger("submit");
    await flushPromises();
    expect(wrapper.text()).toContain("归档结果无法确认");
    expect(wrapper.find("dl").exists()).toBe(false);
    expect(wrapper.get('form button[type="submit"]').attributes("disabled")).toBeDefined();
    await wrapper.get("button").trigger("click");
    await flushPromises();
    expect(wrapper.get('form button[type="submit"]').attributes("disabled")).toBeDefined();
    await wrapper.get("button").trigger("click");
    await flushPromises();
    expect(wrapper.text()).toContain("进行中");
    expect(wrapper.findAll("button").some((button) => button.text() === "归档此项目")).toBe(false);
    await wrapper.get('form input[type="checkbox"]').setValue(true);
    await wrapper.get("form").trigger("submit");
    await flushPromises();
    expect(archive).toHaveBeenCalledTimes(2);
    expect(archive.mock.calls[1]).toEqual(archive.mock.calls[0]);
    expect(wrapper.text()).toContain("本次归档首次回执");
    wrapper.unmount();
  });

  it("does not recover against changed history and keeps a key-conflict lock after refresh", async () => {
    const auth = await session(false, true);
    const archiver = new ProjectArchiveClient(auth);
    const archive = vi.spyOn(archiver, "archive")
      .mockRejectedValueOnce(new ProjectArchiveError("PROJECT_ARCHIVE_UNCERTAIN"));
    const fetcher = vi.fn().mockResolvedValueOnce(response(project, project.etag))
      .mockResolvedValueOnce(response({ ...project, name: "已改名", etag: '"v1"' }, '"v1"'));
    const { wrapper } = await view(auth, `/projects/${id}`, fetcher as typeof fetch, archiver);
    await wrapper.findAll("button").find((button) => button.text() === "归档此项目")!.trigger("click");
    await wrapper.get('form input[type="checkbox"]').setValue(true);
    await wrapper.get("form").trigger("submit");
    await flushPromises();
    await wrapper.get("button").trigger("click");
    await flushPromises();
    expect(wrapper.text()).toContain("已改名");
    expect(wrapper.get('form button[type="submit"]').attributes("disabled")).toBeDefined();
    expect(archive).toHaveBeenCalledTimes(1);
    wrapper.unmount();

    archive.mockRejectedValueOnce(new ProjectArchiveError("CONFLICT_IDEMPOTENCY"));
    archive.mockClear();
    const sameFetcher = vi.fn().mockImplementation(() => Promise.resolve(response(project, project.etag)));
    const conflict = await view(auth, `/projects/${id}`, sameFetcher as typeof fetch, archiver);
    await conflict.wrapper.findAll("button").find((button) => button.text() === "归档此项目")!.trigger("click");
    await conflict.wrapper.get('form input[type="checkbox"]').setValue(true);
    await conflict.wrapper.get("form").trigger("submit");
    await flushPromises();
    await conflict.wrapper.get("button").trigger("click");
    await flushPromises();
    expect(conflict.wrapper.text()).toContain("已停止本页后续归档");
    expect(conflict.wrapper.text()).not.toContain("归档此项目");
    expect(archive).toHaveBeenCalledTimes(1);
    conflict.wrapper.unmount();
  });

  it("discards a late archive receipt when the project changes", async () => {
    const auth = await session(false, true);
    const archiver = new ProjectArchiveClient(auth);
    let finish!: (value: ProjectArchiveFirstReceipt) => void;
    const archive = vi.spyOn(archiver, "archive")
      .mockReturnValueOnce(new Promise((resolve) => { finish = resolve; }));
    const fetcher = vi.fn().mockResolvedValueOnce(response(project, project.etag))
      .mockResolvedValueOnce(response({ ...project, project_id: otherId, name: "其他项目" }, project.etag));
    const { wrapper, router } = await view(auth, `/projects/${id}`, fetcher as typeof fetch, archiver);
    await wrapper.findAll("button").find((button) => button.text() === "归档此项目")!.trigger("click");
    await wrapper.get('form input[type="checkbox"]').setValue(true);
    await wrapper.get("form").trigger("submit");
    await router.push(`/projects/${otherId}`);
    finish({ first_result: { ...project, state: "ARCHIVED", etag: '"v1"' }, is_current_state_proof: false });
    await flushPromises();
    expect(archive).toHaveBeenCalledTimes(1);
    expect(wrapper.text()).not.toContain("本次归档首次回执");
    expect(wrapper.text()).toContain("其他项目");
    expect(wrapper.text()).not.toContain("合成项目");
    wrapper.unmount();
  });
});
