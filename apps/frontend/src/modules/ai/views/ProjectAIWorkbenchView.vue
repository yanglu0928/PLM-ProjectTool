<script setup lang="ts">
import { inject, onUnmounted, ref, toRaw, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";

import { AIReadClient, AIReadError, type AITaskView } from "@/modules/ai/api/aiReadClient";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { sessionClientKey } from "@/modules/auth/api/sessionContext";

const props = defineProps<{ session?: SessionClient; ai?: AIReadClient }>();
const session = toRaw(props.session ?? inject(sessionClientKey, null) ?? new SessionClient());
const ai = toRaw(props.ai ?? new AIReadClient());
const identity = session.view;
const route = useRoute();
const items = ref<readonly AITaskView[]>([]);
const cursor = ref<string | null>(null);
const loaded = ref(false);
const busy = ref(false);
const error = ref("");
let generation = 0;
let mounted = true;

const taskLabels: Readonly<Record<AITaskView["task_state"], string>> = Object.freeze({
  QUEUED: "等待执行", RUNNING: "执行中", SUCCEEDED: "已完成", FAILED: "失败",
  CANCEL_REQUESTED: "正在取消", CANCELLED: "已取消",
});
const suggestionLabels: Readonly<Record<AITaskView["suggestion_state"], string>> = Object.freeze({
  NONE: "暂无建议", AVAILABLE: "建议待查看", ACCEPTED_TO_DRAFT: "已进入草稿",
  REJECTED: "已拒绝", SUPERSEDED: "已被新版本替代",
});

function mayRead() {
  return mounted && !!identity && !identity.password_change_required
    && session.view?.user.user_id === identity.user.user_id;
}
async function load(next: string | null = null, replace = false) {
  if (!mayRead() || busy.value) return;
  const projectId = typeof route.params.projectId === "string" ? route.params.projectId : "";
  const current = ++generation;
  busy.value = true;
  error.value = "";
  if (replace) { items.value = []; cursor.value = null; loaded.value = false; }
  try {
    const page = await ai.listTasks(projectId, 50, next);
    if (!mounted || current !== generation || route.params.projectId !== projectId || !mayRead()) return;
    const known = new Set(items.value.map(item => item.ai_task_id));
    if (page.items.some(item => known.has(item.ai_task_id))) throw new AIReadError("AI_READ_UNAVAILABLE");
    items.value = Object.freeze([...items.value, ...page.items]);
    cursor.value = page.next_cursor;
    loaded.value = true;
  } catch (failure) {
    if (!mounted || current !== generation || route.params.projectId !== projectId) return;
    items.value = []; cursor.value = null; loaded.value = false;
    error.value = failure instanceof AIReadError ? failure.message : "暂时无法读取AI任务，请稍后重试。";
  } finally { if (mounted && current === generation) busy.value = false; }
}

watch(() => route.params.projectId, () => {
  generation += 1;
  items.value = []; cursor.value = null; loaded.value = false; error.value = ""; busy.value = false;
  void load(null, true);
}, { immediate: true });
onUnmounted(() => { mounted = false; generation += 1; });
</script>

<template>
  <section class="ai-workbench" aria-labelledby="ai-workbench-title" :aria-busy="busy">
    <p class="section-kicker">AI 分析工作台</p>
    <h1 id="ai-workbench-title">任务与建议状态</h1>
    <p class="fact-warning"><strong>AI 输出不是正式业务事实。</strong> 当前页面只展示任务和建议状态，不代表建议已被确认或写入项目正式数据。</p>
    <p>列表由服务器按当前项目权限实时筛选；跨页内容不代表同一时刻的快照。</p>
    <p><RouterLink :to="{ name: 'project-detail', params: { projectId: route.params.projectId } }">返回项目详情</RouterLink></p>
    <template v-if="!identity">
      <p role="status">尚未读取当前身份。请先登录，或在账户页读取当前身份。</p>
      <RouterLink to="/login">前往账户与登录</RouterLink>
    </template>
    <template v-else-if="identity.password_change_required">
      <p role="status">当前账户须先修改密码，暂不能读取AI任务。</p>
      <RouterLink to="/login">前往账户与登录</RouterLink>
    </template>
    <template v-else>
      <button type="button" :disabled="busy" @click="load(null, true)">{{ busy ? "正在读取…" : "刷新AI任务" }}</button>
      <p v-if="busy" role="status">正在确认AI任务访问权限…</p>
      <p v-if="error" role="alert">{{ error }}</p>
      <p v-if="loaded && !items.length" role="status">当前项目没有可见AI任务。</p>
      <ul v-if="items.length" aria-label="项目AI任务">
        <li v-for="item in items" :key="item.ai_task_id">
          <div class="task-heading">
            <strong>{{ item.task_type }}</strong>
            <span class="task-state">{{ taskLabels[item.task_state] }}</span>
          </div>
          <span>AI任务号：<RouterLink :to="{ name: 'project-ai-task-detail', params: { projectId: route.params.projectId, taskId: item.ai_task_id } }">{{ item.ai_task_id }}</RouterLink></span>
          <span>建议：{{ suggestionLabels[item.suggestion_state] }} · 建议始终需人工确认</span>
          <span>提交：<time :datetime="item.requested_at">{{ new Date(item.requested_at).toLocaleString("zh-CN") }}</time></span>
          <span>输出合同：{{ item.output_schema_ref }} · 版本：{{ item.etag }}</span>
          <span v-if="item.error_code">安全错误：{{ item.error_code }}<template v-if="item.retryable !== null"> · {{ item.retryable ? "可按受控流程重试" : "不可自动重试" }}</template></span>
          <span v-if="item.job_id">运行记录：<RouterLink :to="{ name: 'project-job-detail', params: { projectId: route.params.projectId, jobId: item.job_id } }">{{ item.job_id }}</RouterLink></span>
        </li>
      </ul>
      <button v-if="cursor && loaded" type="button" :disabled="busy" @click="load(cursor)">加载更多AI任务</button>
      <p v-if="items.length" class="scope-note">本阶段不提供接受、拒绝、取消或重试操作；后续详情页仍会重新向服务器确认当前权限和状态。</p>
    </template>
  </section>
</template>

<style scoped>
.ai-workbench { max-width: 54rem; margin: 1rem auto; padding: 1.5rem; background: #fff; border-radius: 1rem; }
.ai-workbench p { line-height: 1.65; }
.ai-workbench ul { display: grid; gap: .8rem; padding: 0; list-style: none; }
.ai-workbench li { display: grid; gap: .35rem; padding: 1rem; border: 1px solid #d8dee7; border-radius: .75rem; overflow-wrap: anywhere; }
.task-heading { display: flex; align-items: center; justify-content: space-between; gap: 1rem; }
.task-state { padding: .2rem .55rem; border-radius: 999px; background: #e8f0eb; color: #285c45; font-size: .85rem; }
.fact-warning { padding: .8rem 1rem; border-left: .3rem solid #d29b42; background: #fff8e9; }
.scope-note { color: #5f6e66; }
.ai-workbench [role="alert"] { color: #a21d25; }
</style>
