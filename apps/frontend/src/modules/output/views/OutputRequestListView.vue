<script setup lang="ts">
import { inject, onUnmounted, ref, toRaw, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { sessionClientKey } from "@/modules/auth/api/sessionContext";
import {
  OutputRequestListClient, OutputRequestListError, outputRequestFollows,
  type OutputRequestState, type OutputRequestSummary,
} from "@/modules/output/api/outputRequestListClient";
import { OutputArtifactReadClient } from "@/modules/output/api/outputArtifactReadClient";

const props = defineProps<{
  session?: SessionClient;
  reader?: OutputRequestListClient;
  artifactReader?: OutputArtifactReadClient;
  navigate?: (url: string) => void;
}>();
const session = toRaw(props.session ?? inject(sessionClientKey, null) ?? new SessionClient());
const reader = toRaw(props.reader ?? new OutputRequestListClient());
const artifactReader = toRaw(props.artifactReader ?? new OutputArtifactReadClient());
const navigate = props.navigate ?? ((url: string) => window.location.assign(url));
const route = useRoute();
const items = ref<readonly OutputRequestSummary[]>([]);
const cursor = ref<string | null>(null);
const busy = ref(false);
const loaded = ref(false);
const error = ref("");
const downloadError = ref("");
const downloadingId = ref<string | null>(null);
let generation = 0;
let mounted = true;
const projectId = () => typeof route.params.projectId === "string" ? route.params.projectId : "";
const allowedRoles = ["PROJECT_MANAGER", "IMPLEMENTATION_MEMBER", "CUSTOMER_MANAGER"];
function mayRead() {
  const view = session.view;
  return mounted && !!view && !view.password_change_required
    && view.authorized_projects.some(item => item.project_id === projectId()
      && allowedRoles.includes(item.role));
}
function roleDenied() {
  const view = session.view;
  return !!view && !view.password_change_required
    && view.authorized_projects.some(item => item.project_id === projectId())
    && !mayRead();
}
function stateLabel(state: OutputRequestState): string {
  return ({
    REQUESTED: "已登记", QUEUED: "排队中", GENERATING: "生成中",
    VALIDATING: "校验中", SUCCEEDED: "已生成", FAILED: "生成失败",
    CANCEL_REQUESTED: "正在取消", CANCELLED: "已取消",
  } as const)[state];
}
async function download(item: OutputRequestSummary) {
  if (!mayRead() || item.state !== "SUCCEEDED" || downloadingId.value !== null) return;
  const project = projectId();
  const current = generation;
  if (item.project_id !== project) return;
  downloadingId.value = item.output_request_id;
  downloadError.value = "";
  try {
    const reference = await artifactReader.get(project, item.output_request_id);
    if (!mounted || current !== generation || project !== projectId() || !mayRead()
      || reference.project_id !== project
      || reference.output_request_id !== item.output_request_id) return;
    navigate(reference.content_url);
  } catch (failure) {
    if (!mounted || current !== generation || project !== projectId()) return;
    downloadError.value = failure instanceof Error
      ? failure.message : "暂时无法获取输出文件，请稍后重试。";
  } finally {
    if (mounted && current === generation) downloadingId.value = null;
  }
}

async function load(next: string | null = null, replace = false) {
  if (!mayRead() || busy.value) return;
  const project = projectId();
  const current = ++generation;
  downloadingId.value = null;
  downloadError.value = "";
  busy.value = true;
  error.value = "";
  if (replace) { items.value = []; cursor.value = null; loaded.value = false; }
  try {
    const page = await reader.list(project, 50, next);
    if (!mounted || current !== generation || project !== projectId() || !mayRead()) return;
    const previous = items.value;
    const ids = new Set(previous.map(item => item.output_request_id));
    if (page.items.some(item => ids.has(item.output_request_id))
      || previous.length > 0 && page.items.length > 0
        && !outputRequestFollows(previous[previous.length - 1]!, page.items[0]!)) {
      throw new OutputRequestListError("OUTPUT_UNAVAILABLE");
    }
    items.value = Object.freeze([...previous, ...page.items]);
    cursor.value = page.next_cursor;
    loaded.value = true;
  } catch (failure) {
    if (!mounted || current !== generation) return;
    items.value = [];
    cursor.value = null;
    loaded.value = false;
    error.value = failure instanceof Error ? failure.message : "暂时无法读取输出请求。";
  } finally {
    if (mounted && current === generation) busy.value = false;
  }
}
watch(() => route.params.projectId, () => {
  generation += 1;
  items.value = [];
  cursor.value = null;
  loaded.value = false;
  busy.value = false;
  error.value = "";
  downloadError.value = "";
  downloadingId.value = null;
  if (mayRead()) void load(null, true);
}, { immediate: true });
onUnmounted(() => { mounted = false; generation += 1; });
</script>

<template>
  <section class="output-list" aria-labelledby="output-list-title" :aria-busy="busy">
    <p class="section-kicker">项目交付</p>
    <h1 id="output-list-title">输出请求历史</h1>
    <p><RouterLink :to="{ name: 'project-detail', params: { projectId: route.params.projectId } }">返回项目详情</RouterLink></p>
    <p v-if="!session.view" role="status">尚未读取当前身份，请先登录。</p>
    <p v-else-if="session.view.password_change_required" role="status">当前账户须先修改密码。</p>
    <p v-else-if="!mayRead() && roleDenied()" role="status">当前项目角色无权查看输出请求历史。</p>
    <p v-else-if="!mayRead()" role="status">当前账户无权查看此项目的输出请求历史。</p>
    <template v-else>
      <p class="warning">仅已完成且通过文件校验的输出可下载。</p>
      <button type="button" :disabled="busy" @click="load(null, true)">
        {{ busy ? "正在读取…" : "刷新输出请求" }}
      </button>
      <p v-if="error" role="alert">{{ error }}</p>
      <p v-if="downloadError" role="alert">{{ downloadError }}</p>
      <p v-if="loaded && items.length === 0" role="status">当前项目没有可见的输出请求。</p>
      <ol v-if="items.length" aria-label="输出请求历史">
        <li v-for="item in items" :key="item.output_request_id">
          <strong>{{ item.output_type }}</strong>
          <span>{{ stateLabel(item.state) }}</span>
          <span class="request-id">请求编号：{{ item.output_request_id }}</span>
          <span>请求时间：<time :datetime="item.requested_at">{{ new Date(item.requested_at).toLocaleString("zh-CN") }}</time></span>
          <span v-if="item.completed_at">完成时间：<time :datetime="item.completed_at">{{ new Date(item.completed_at).toLocaleString("zh-CN") }}</time></span>
          <button v-if="item.state === 'SUCCEEDED'" type="button"
            :disabled="downloadingId !== null" @click="download(item)">
            {{ downloadingId === item.output_request_id ? "正在准备下载…" : "下载文件" }}
          </button>
        </li>
      </ol>
      <button v-if="cursor" type="button" :disabled="busy" @click="load(cursor)">加载更多</button>
    </template>
  </section>
</template>

<style scoped>
.output-list{max-width:60rem;margin:1rem auto;padding:1.5rem;background:#fff;border-radius:1rem}
.output-list ol{display:grid;gap:.8rem;padding:0;list-style:none}
.output-list li{display:grid;gap:.35rem;padding:1rem;border:1px solid #d8dee7;border-radius:.75rem}
.output-list .request-id{overflow-wrap:anywhere;font-family:ui-monospace,monospace}
.warning{padding:.8rem 1rem;border-left:.3rem solid #d29b42;background:#fff8e9}
.output-list button{width:max-content}
.output-list [role=alert]{color:#a21d25}
</style>
