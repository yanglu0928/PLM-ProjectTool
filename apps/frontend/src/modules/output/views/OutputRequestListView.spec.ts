import { flushPromises, mount } from "@vue/test-utils";
import { createMemoryHistory } from "vue-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import { createAppRouter } from "@/app/router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { OutputRequestListClient, type OutputRequestPage, type OutputRequestSummary } from "@/modules/output/api/outputRequestListClient";
import type { OutputArtifactReadClient, OutputArtifactReference } from "@/modules/output/api/outputArtifactReadClient";
import OutputRequestListView from "./OutputRequestListView.vue";

const project = "01234567-89ab-4cde-8123-456789abcdef";
const other = "11234567-89ab-4cde-8123-456789abcdef";
const row = {
  output_request_id: "21234567-89ab-4cde-8123-456789abcdef",
  project_id: project, output_type: "DOCX" as const, state: "QUEUED" as const,
  requested_at: "2026-10-19T00:00:00Z", completed_at: null,
};
async function session(role: string | null = "PROJECT_MANAGER", restricted = false) {
  const response = new Response(JSON.stringify({ data: {
    user: { user_id: project, username_display: "合成用户" }, deployment_role: "NONE",
    password_change_required: restricted,
    authorized_projects: role ? [{ project_id: project, name: "合成项目", role }] : [],
    absolute_expires_at: "2030-01-01T12:00:00Z", idle_expires_at: "2030-01-01T11:00:00Z",
    csrf_token: "a".repeat(64),
  }, trace_id: project }), { headers: { "Content-Type": "application/json" } });
  const client = new SessionClient(vi.fn().mockResolvedValue(response) as typeof fetch);
  await client.login("synthetic", "not-a-secret");
  return client;
}
async function view(
  auth: SessionClient, path: string, reader: OutputRequestListClient,
  artifactReader?: OutputArtifactReadClient, navigate?: (url: string) => void,
) {
  const router = createAppRouter(createMemoryHistory());
  await router.push(path); await router.isReady();
  const wrapper = mount(OutputRequestListView, {
    props: { session: auth, reader, artifactReader, navigate },
    global: { plugins: [router] } });
  await flushPromises();
  return { wrapper, router };
}
function page(items: readonly OutputRequestSummary[], next_cursor: string | null = null): OutputRequestPage {
  return { items, next_cursor, has_more: next_cursor !== null };
}

describe("OutputRequestListView", () => {
  afterEach(() => vi.restoreAllMocks());

  it("loads safe request summaries and paginates with the returned cursor", async () => {
    const token = "a".repeat(40) + "." + "b".repeat(43);
    const reader = { list: vi.fn()
      .mockResolvedValueOnce(page([row], token))
      .mockResolvedValueOnce(page([{ ...row, output_request_id: other,
        requested_at: "2026-10-18T00:00:00Z" }])) } as unknown as OutputRequestListClient;
    const { wrapper } = await view(await session(), "/projects/" + project + "/output-requests", reader);
    expect(wrapper.text()).toContain("输出请求历史");
    expect(wrapper.text()).toContain("排队中");
    expect(wrapper.text()).toContain(row.output_request_id);
    await wrapper.get("button:last-of-type").trigger("click");
    await flushPromises();
    expect(reader.list).toHaveBeenCalledTimes(2);
    expect(wrapper.text()).toContain(other);
    wrapper.unmount();
  });

  it("does not call the API for CustomerMember, unrelated project or password-reset session", async () => {
    const reader = { list: vi.fn() } as unknown as OutputRequestListClient;
    const member = await view(await session("CUSTOMER_MEMBER"),
      "/projects/" + project + "/output-requests", reader);
    expect(member.wrapper.text()).toContain("当前项目角色无权");
    member.wrapper.unmount();
    const unrelated = await view(await session(null),
      "/projects/" + project + "/output-requests", reader);
    expect(unrelated.wrapper.text()).toContain("无权查看");
    unrelated.wrapper.unmount();
    const restricted = await view(await session(null, true),
      "/projects/" + project + "/output-requests", reader);
    expect(restricted.wrapper.text()).toContain("须先修改密码");
    expect(reader.list).not.toHaveBeenCalled();
    restricted.wrapper.unmount();
  });

  it("clears stale rows when route project changes", async () => {
    const reader = { list: vi.fn()
      .mockResolvedValueOnce(page([row]))
      .mockResolvedValueOnce(page([])) } as unknown as OutputRequestListClient;
    const { wrapper, router } = await view(await session(), "/projects/" + project + "/output-requests", reader);
    expect(wrapper.text()).toContain(row.output_request_id);
    await router.push("/projects/" + other + "/output-requests");
    await flushPromises();
    expect(wrapper.text()).not.toContain(row.output_request_id);
    expect(reader.list).toHaveBeenCalledTimes(1);
    wrapper.unmount();
  });

  it("shows download only for succeeded rows and navigates only through the authorized same-origin reference", async () => {
    const succeeded = { ...row, state: "SUCCEEDED" as const,
      completed_at: "2026-10-19T00:01:00Z" };
    const reader = { list: vi.fn().mockResolvedValue(page([row, succeeded])) }
      as unknown as OutputRequestListClient;
    const reference: OutputArtifactReference = Object.freeze({
      output_artifact_id: other, output_request_id: succeeded.output_request_id,
      project_id: project, document_id: "31234567-89ab-4cde-8123-456789abcdef",
      document_version_id: "41234567-89ab-4cde-8123-456789abcdef",
      artifact_kind: "DOCX",
      media_type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      content_sha256: "a".repeat(64), size_bytes: 128,
      content_url: "/api/v1/projects/" + project + "/documents/31234567-89ab-4cde-8123-456789abcdef/versions/41234567-89ab-4cde-8123-456789abcdef/content",
    });
    const artifactReader = { get: vi.fn().mockResolvedValue(reference) }
      as unknown as OutputArtifactReadClient;
    const navigate = vi.fn();
    const { wrapper } = await view(await session(),
      "/projects/" + project + "/output-requests", reader, artifactReader, navigate);
    expect(wrapper.findAll("button").filter(button => button.text() === "下载文件")).toHaveLength(1);
    await wrapper.findAll("button").find(button => button.text() === "下载文件")!.trigger("click");
    await flushPromises();
    expect(artifactReader.get).toHaveBeenCalledExactlyOnceWith(project, succeeded.output_request_id);
    expect(navigate).toHaveBeenCalledExactlyOnceWith(reference.content_url);
    wrapper.unmount();
  });

  it("does not navigate when artifact lookup fails", async () => {
    const succeeded = { ...row, state: "SUCCEEDED" as const,
      completed_at: "2026-10-19T00:01:00Z" };
    const reader = { list: vi.fn().mockResolvedValue(page([succeeded])) }
      as unknown as OutputRequestListClient;
    const artifactReader = { get: vi.fn().mockRejectedValue(new Error("输出文件尚未可用或无权读取。")) }
      as unknown as OutputArtifactReadClient;
    const navigate = vi.fn();
    const { wrapper } = await view(await session(),
      "/projects/" + project + "/output-requests", reader, artifactReader, navigate);
    await wrapper.findAll("button").find(button => button.text() === "下载文件")!.trigger("click");
    await flushPromises();
    expect(navigate).not.toHaveBeenCalled();
    expect(wrapper.get('[role="alert"]').text()).toContain("无权读取");
    wrapper.unmount();
  });

  it("shows an empty state and safe error message", async () => {
    const reader = { list: vi.fn().mockResolvedValue(page([])) } as unknown as OutputRequestListClient;
    const { wrapper } = await view(await session(), "/projects/" + project + "/output-requests", reader);
    expect(wrapper.text()).toContain("没有可见的输出请求");
    wrapper.unmount();
    const failing = { list: vi.fn().mockRejectedValue(new Error("safe client message")) } as unknown as OutputRequestListClient;
    const failed = await view(await session(), "/projects/" + project + "/output-requests", failing);
    expect(failed.wrapper.get('[role="alert"]').text()).toContain("safe client message");
    failed.wrapper.unmount();
  });
});
