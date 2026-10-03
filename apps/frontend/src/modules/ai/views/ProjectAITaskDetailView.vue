<script setup lang="ts">
import { inject, onUnmounted, ref, toRaw, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";

import { AIReadClient, AIReadError, type AIInvocationView, type AITaskView } from "@/modules/ai/api/aiReadClient";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { sessionClientKey } from "@/modules/auth/api/sessionContext";

const props = defineProps<{ session?: SessionClient; ai?: AIReadClient }>();
const session = toRaw(props.session ?? inject(sessionClientKey, null) ?? new SessionClient());
const ai = toRaw(props.ai ?? new AIReadClient());
const identity = session.view;
const route = useRoute();
const task = ref<AITaskView | null>(null);
const invocations = ref<readonly AIInvocationView[]>([]);
const cursor = ref<string | null>(null);
const loaded = ref(false);
const busy = ref(false);
const error = ref("");
let generation = 0;
let mounted = true;

function mayRead() {
  return mounted && !!identity && !identity.password_change_required
    && session.view?.user.user_id === identity.user.user_id;
}
function ids() {
  return {
    projectId: typeof route.params.projectId === "string" ? route.params.projectId : "",
    taskId: typeof route.params.taskId === "string" ? route.params.taskId : "",
  };
}
async function load() {
  if (!mayRead() || busy.value) return;
  const request = ids();
  const current = ++generation;
  task.value = null; invocations.value = []; cursor.value = null; loaded.value = false; error.value = ""; busy.value = true;
  try {
    const [currentTask, page] = await Promise.all([
      ai.getTask(request.projectId, request.taskId),
      ai.listInvocations(request.projectId, request.taskId, 50),
    ]);
    const latest = ids();
    if (!mounted || current !== generation || latest.projectId !== request.projectId
        || latest.taskId !== request.taskId || !mayRead()) return;
    task.value = currentTask;
    invocations.value = page.items;
    cursor.value = page.next_cursor;
    loaded.value = true;
  } catch (failure) {
    const latest = ids();
    if (!mounted || current !== generation || latest.projectId !== request.projectId || latest.taskId !== request.taskId) return;
    task.value = null; invocations.value = []; cursor.value = null; loaded.value = false;
    error.value = failure instanceof AIReadError ? failure.message : "暂时无法读取AI任务详情，请稍后重试。";
  } finally { if (mounted && current === generation) busy.value = false; }
}
async function loadMore() {
  if (!mayRead() || busy.value || !loaded.value || !task.value || !cursor.value) return;
  const request = ids();
  const next = cursor.value;
  const current = ++generation;
  error.value = ""; busy.value = true;
  try {
    const page = await ai.listInvocations(request.projectId, request.taskId, 50, next);
    const latest = ids();
    if (!mounted || current !== generation || latest.projectId !== request.projectId
        || latest.taskId !== request.taskId || !mayRead()) return;
    const known = new Set(invocations.value.map(item => item.ai_invocation_id));
    if (page.items.some(item => known.has(item.ai_invocation_id))) throw new AIReadError("AI_READ_UNAVAILABLE");
    invocations.value = Object.freeze([...invocations.value, ...page.items]);
    cursor.value = page.next_cursor;
  } catch (failure) {
    const latest = ids();
    if (!mounted || current !== generation || latest.projectId !== request.projectId || latest.taskId !== request.taskId) return;
    task.value = null; invocations.value = []; cursor.value = null; loaded.value = false;
    error.value = failure instanceof AIReadError ? failure.message : "暂时无法读取AI任务详情，请稍后重试。";
  } finally { if (mounted && current === generation) busy.value = false; }
}

watch(() => [route.params.projectId, route.params.taskId], () => {
  generation += 1; task.value = null; invocations.value = []; cursor.value = null;
  loaded.value = false; busy.value = false; error.value = ""; void load();
}, { immediate: true });
onUnmounted(() => { mounted = false; generation += 1; });
</script>

<template>
  <section class="ai-task-detail" aria-labelledby="ai-task-detail-title" :aria-busy="busy">
    <p class="section-kicker">AI 分析工作台</p>
    <h1 id="ai-task-detail-title">任务详情与运行历史</h1>
    <p class="fact-warning"><strong>AI 输出不是正式业务事实。</strong> 此页只展示任务与调用版本事实，不展示Provider请求或响应正文。</p>
    <p><RouterLink :to="{ name: 'project-ai-workbench', params: { projectId: route.params.projectId } }">返回AI任务列表</RouterLink></p>
    <template v-if="!identity">
      <p role="status">尚未读取当前身份。请先登录，或在账户页读取当前身份。</p>
      <RouterLink to="/login">前往账户与登录</RouterLink>
    </template>
    <template v-else-if="identity.password_change_required">
      <p role="status">当前账户须先修改密码，暂不能读取AI任务。</p>
      <RouterLink to="/login">前往账户与登录</RouterLink>
    </template>
    <template v-else>
      <button type="button" :disabled="busy" @click="load()">{{ busy ? "正在读取…" : "刷新任务详情" }}</button>
      <p v-if="busy" role="status">正在重新确认任务与运行历史权限…</p>
      <p v-if="error" role="alert">{{ error }}</p>
      <template v-if="task">
        <dl aria-label="AI任务安全详情">
          <dt>任务类型</dt><dd>{{ task.task_type }}</dd>
          <dt>任务号</dt><dd>{{ task.ai_task_id }}</dd>
          <dt>任务状态</dt><dd>{{ task.task_state }}</dd>
          <dt>建议状态</dt><dd>{{ task.suggestion_state }}（仍需人工确认）</dd>
          <dt>输出合同</dt><dd>{{ task.output_schema_ref }}</dd>
          <dt>上下文策略</dt><dd>{{ task.context_policy_ref }}</dd>
          <dt>提交时间</dt><dd><time :datetime="task.requested_at">{{ new Date(task.requested_at).toLocaleString("zh-CN") }}</time></dd>
          <dt>版本</dt><dd>{{ task.etag }}</dd>
        </dl>
        <h2>固定输入版本</h2>
        <ul aria-label="AI任务输入版本">
          <li v-for="input in task.input_refs" :key="`${input.resource_type}:${input.resource_id}:${input.version_id}`">
            <template v-if="input.resource_type === 'DOC-02'">
              文档：<RouterLink :to="{ name: 'project-document-detail', params: { projectId: route.params.projectId, documentId: input.resource_id } }">{{ input.resource_id }}</RouterLink>
              · 固定版本 {{ input.version_id }}
            </template>
            <template v-else>{{ input.resource_type }} · {{ input.resource_id }} · {{ input.version_id }}</template>
          </li>
        </ul>
        <p v-if="task.job_id">取消、重试与当前Job状态由既有受控任务页处理：<RouterLink :to="{ name: 'project-job-detail', params: { projectId: route.params.projectId, jobId: task.job_id } }">打开运行任务 {{ task.job_id }}</RouterLink></p>
        <p v-else>当前任务没有可公开的Job引用，因此不提供取消或重试入口。</p>
        <p v-if="task.suggestion_state !== 'NONE'"><RouterLink :to="{ name: 'project-ai-suggestion', params: { projectId: route.params.projectId, taskId: task.ai_task_id } }">查看AI建议、原文位置与待维护信息</RouterLink></p>
        <h2>调用历史</h2>
        <p v-if="loaded && !invocations.length" role="status">当前任务尚无可见调用记录。</p>
        <ol v-if="invocations.length" aria-label="AI调用历史">
          <li v-for="item in invocations" :key="item.ai_invocation_id">
            <strong>第 {{ item.attempt_no }} 次 · {{ item.invocation_state }}</strong>
            <span>调用号：{{ item.ai_invocation_id }}</span>
            <span>模型版本：{{ item.model.revision }} · Prompt v{{ item.prompt_version_ref.version_no }}</span>
            <span>输出：{{ item.output_schema.ref }}@{{ item.output_schema.version }} · 校验 {{ item.schema_validation_state }}</span>
            <span>上下文：{{ item.context ? `${item.context.mode} / ${item.context.context_policy_ref}` : "历史记录未绑定Content Plan" }}</span>
            <span v-if="item.usage.input_tokens !== null || item.usage.output_tokens !== null">Token：输入 {{ item.usage.input_tokens ?? "未知" }} / 输出 {{ item.usage.output_tokens ?? "未知" }}</span>
            <span v-if="item.latency_ms !== null">耗时：{{ item.latency_ms }} ms</span>
            <span v-if="item.error_code">安全错误：{{ item.error_code }} · {{ item.retryable ? "可按受控Job流程判断重试" : "不可自动重试" }}</span>
          </li>
        </ol>
        <button v-if="cursor && loaded" type="button" :disabled="busy" @click="loadMore">加载更多调用记录</button>
      </template>
    </template>
  </section>
</template>

<style scoped>
.ai-task-detail { max-width: 56rem; margin: 1rem auto; padding: 1.5rem; background: #fff; border-radius: 1rem; }
.ai-task-detail p { line-height: 1.65; }
.ai-task-detail dl { display: grid; grid-template-columns: minmax(7rem, auto) 1fr; gap: .65rem 1rem; }
.ai-task-detail dt { font-weight: 700; }
.ai-task-detail dd { margin: 0; overflow-wrap: anywhere; }
.ai-task-detail ul, .ai-task-detail ol { display: grid; gap: .7rem; }
.ai-task-detail ol li { display: grid; gap: .3rem; padding: .9rem; border: 1px solid #d8dee7; border-radius: .75rem; overflow-wrap: anywhere; }
.fact-warning { padding: .8rem 1rem; border-left: .3rem solid #d29b42; background: #fff8e9; }
.ai-task-detail [role="alert"] { color: #a21d25; }
</style>
