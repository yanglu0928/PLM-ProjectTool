<script setup lang="ts">
import { inject, onUnmounted, ref, shallowRef, toRaw, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";

import { SessionClient } from "@/modules/auth/api/sessionClient";
import { sessionClientKey } from "@/modules/auth/api/sessionContext";
import { WorkflowReadClient, WorkflowReadError, type WorkflowView } from "@/modules/workflow/api/workflowReadClient";
import { WorkflowStartClient, WorkflowStartError,
  type WorkflowStartFirstReceipt } from "@/modules/workflow/api/workflowStartClient";

const props = defineProps<{ session?: SessionClient; workflows?: WorkflowReadClient;
  starter?: WorkflowStartClient }>();
const session = toRaw(props.session ?? inject(sessionClientKey, null) ?? new SessionClient());
const workflows = toRaw(props.workflows ?? new WorkflowReadClient());
const starter = toRaw(props.starter ?? new WorkflowStartClient(session));
const identity = session.view;
const route = useRoute();
const workflow = shallowRef<WorkflowView | null>(null);
const busy = ref(false);
const writeBusy = ref(false);
const error = ref("");
const startTarget = shallowRef<WorkflowView | null>(null);
const startConfirmed = ref(false);
const retryConfirmed = ref(false);
const clearConfirmed = ref(false);
const receipt = ref<WorkflowStartFirstReceipt | null>(null);
const requireFreshRead = ref(false);
const storageError = ref(false);
type PendingStart = { actor: string; project: string; workflow: string; key: string; etag: '"v0"' };
const storageKey = identity ? `plm.workflow.start.pending.${identity.user.user_id}` : "";
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
function validPending(value: unknown): value is PendingStart {
  if (typeof value !== "object" || value === null || Array.isArray(value)) return false;
  const entry = value as Record<string, unknown>;
  return entry.actor === identity?.user.user_id
    && typeof entry.project === "string" && uuid.test(entry.project)
    && typeof entry.workflow === "string" && uuid.test(entry.workflow)
    && typeof entry.key === "string" && /^[\x20-\x7e]{16,128}$/.test(entry.key)
    && entry.etag === '"v0"';
}
function readPending(): PendingStart | null {
  if (!storageKey) return null;
  try {
    const raw = window.sessionStorage.getItem(storageKey);
    if (raw === null) return null;
    const parsed: unknown = JSON.parse(raw);
    if (validPending(parsed)) return parsed;
  } catch { /* Existing operation cannot be safely interpreted. */ }
  storageError.value = true;
  return null;
}
const pending = shallowRef<PendingStart | null>(readPending());
function savePending(value: PendingStart): boolean {
  if (!storageKey || storageError.value || pending.value) return false;
  try {
    const serialized = JSON.stringify(value);
    window.sessionStorage.setItem(storageKey, serialized);
    if (window.sessionStorage.getItem(storageKey) !== serialized) return false;
    pending.value = value;
    return true;
  } catch { storageError.value = true; return false; }
}
function clearPending(value: PendingStart): boolean {
  if (!storageKey || pending.value !== value) return false;
  try {
    if (window.sessionStorage.getItem(storageKey) !== JSON.stringify(value)) return false;
    window.sessionStorage.removeItem(storageKey);
    if (window.sessionStorage.getItem(storageKey) !== null) return false;
    pending.value = null;
    return true;
  } catch { storageError.value = true; return false; }
}
let generation = 0;
let mounted = true;
function mayRead() {
  return mounted && !!identity && !identity.password_change_required
    && session.view?.user.user_id === identity.user.user_id;
}
function mayStart() {
  return mayRead() && session.canSubmit && !storageError.value
    && !!session.view?.authorized_projects.some((item) =>
      item.project_id === route.params.projectId && item.role === "PROJECT_MANAGER");
}
async function load() {
  if (!mayRead() || busy.value || writeBusy.value) return;
  const projectId = typeof route.params.projectId === "string" ? route.params.projectId : "";
  const current = ++generation;
  busy.value = true; error.value = ""; workflow.value = null;
  startTarget.value = null; startConfirmed.value = false;
  retryConfirmed.value = false; clearConfirmed.value = false;
  try {
    const latest = await workflows.get(projectId);
    if (!mounted || current !== generation || route.params.projectId !== projectId || !mayRead()) return;
    workflow.value = latest;
    requireFreshRead.value = false;
    receipt.value = null;
  } catch (failure) {
    if (!mounted || current !== generation || route.params.projectId !== projectId) return;
    error.value = failure instanceof WorkflowReadError
      ? failure.message : "暂时无法确认项目流程，请稍后重试。";
  } finally { if (mounted && current === generation) busy.value = false; }
}
function beginStart() {
  if (!mayStart() || busy.value || writeBusy.value || pending.value || requireFreshRead.value
    || receipt.value || workflow.value?.state !== "NOT_STARTED" || workflow.value.etag !== '"v0"') return;
  startTarget.value = workflow.value;
  startConfirmed.value = false;
  error.value = "";
}
function canRetry(): boolean {
  const operation = pending.value;
  return !!operation && !!workflow.value && mayStart() && !busy.value && !writeBusy.value
    && !requireFreshRead.value && operation.project === route.params.projectId
    && operation.workflow === workflow.value.workflow_id
    && operation.etag === workflow.value.etag && workflow.value.state === "NOT_STARTED";
}
async function submitStart() {
  if (!mayStart() || busy.value || writeBusy.value || requireFreshRead.value) return;
  const recovery = pending.value;
  if (recovery && (!canRetry() || !retryConfirmed.value)) return;
  if (!recovery && (!startTarget.value || !startConfirmed.value
    || workflow.value !== startTarget.value || workflow.value.state !== "NOT_STARTED"
    || workflow.value.etag !== '"v0"')) return;
  const before = workflow.value!;
  const attempt: PendingStart = recovery ?? Object.freeze({
    actor: identity!.user.user_id, project: route.params.projectId as string,
    workflow: before.workflow_id, key: crypto.randomUUID(), etag: '"v0"',
  });
  if (!recovery && !savePending(attempt)) {
    storageError.value = true;
    error.value = "无法安全保存原操作号，启动请求未发送。";
    return;
  }
  const current = ++generation;
  startTarget.value = null; startConfirmed.value = false; retryConfirmed.value = false;
  writeBusy.value = true; error.value = ""; workflow.value = null;
  try {
    const result = await starter.start(attempt.project, before, attempt.key);
    if (!mounted || current !== generation || route.params.projectId !== attempt.project
      || !mayRead()) return;
    receipt.value = result;
    if (!clearPending(attempt)) storageError.value = true;
    requireFreshRead.value = true;
  } catch (failure) {
    if (!mounted || current !== generation || route.params.projectId !== attempt.project) return;
    requireFreshRead.value = true;
    if (failure instanceof WorkflowStartError && !failure.uncertain
      && failure.code !== "CONFLICT_IDEMPOTENCY") {
      if (!clearPending(attempt)) storageError.value = true;
      error.value = failure.message + " 请重新读取流程后再决定。";
    } else {
      error.value = "启动结果无法确认。原操作号和版本已保留；先重新读取流程与审计，勿生成新操作。";
    }
  } finally { if (mounted && current === generation) writeBusy.value = false; }
}
function acknowledgeChanged() {
  const operation = pending.value;
  const latest = workflow.value;
  if (!operation || !latest || !clearConfirmed.value || !mayRead() || busy.value || writeBusy.value
    || operation.project !== route.params.projectId || operation.workflow !== latest.workflow_id
    || latest.etag === operation.etag) return;
  if (!clearPending(operation)) { storageError.value = true; return; }
  clearConfirmed.value = false;
  error.value = "已在核对当前流程及审计后清除原操作记录；当前状态仍以独立读取结果为准。";
}
watch(() => route.params.projectId, () => {
  generation += 1; workflow.value = null; busy.value = false; writeBusy.value = false;
  error.value = ""; startTarget.value = null; startConfirmed.value = false;
  retryConfirmed.value = false; clearConfirmed.value = false;
  receipt.value = null; requireFreshRead.value = false;
  void load();
}, { immediate: true });
onUnmounted(() => { mounted = false; generation += 1; });
</script>

<template>
  <section class="project-detail" aria-labelledby="workflow-title" :aria-busy="busy || writeBusy">
    <p class="section-kicker">当前项目</p>
    <h1 id="workflow-title">项目流程</h1>
    <p><RouterLink :to="{ name: 'project-detail', params: { projectId: route.params.projectId } }">返回项目详情</RouterLink></p>
    <template v-if="!identity">
      <p role="status">尚未读取当前身份。请先登录。</p><RouterLink to="/login">前往账户与登录</RouterLink>
    </template>
    <template v-else-if="identity.password_change_required">
      <p role="status">当前账户须先修改密码，暂不能读取项目流程。</p>
    </template>
    <template v-else>
      <button type="button" :disabled="busy || writeBusy" @click="load()">{{ busy ? '正在读取…' : '刷新当前流程' }}</button>
      <p v-if="busy" role="status">正在确认项目流程和当前权限…</p>
      <p v-if="error" role="alert">{{ error }}</p>
      <p v-if="storageError" role="alert">原启动操作记录无法安全读取或保存；本页已关闭新的启动请求。请核对当前流程与审计。</p>
      <p v-if="requireFreshRead" role="status">提交后的旧流程快照已清除；须重新读取当前流程。</p>
      <p v-if="receipt" role="status">首次启动回执：{{ receipt.first_result.current_stage }} · {{ receipt.first_result.etag }}。这是首次结果，不是当前状态或 Gate 通过证明。</p>
      <p v-if="pending" role="status">原启动操作号已保留。即使离开本页也不可生成新操作；请先读取当前流程与审计。</p>
      <template v-if="workflow">
        <p>流程状态：{{ workflow.state }}；当前阶段：{{ workflow.current_stage ?? '未启动' }}；版本：{{ workflow.etag }}</p>
        <p>以下清单状态仅为服务器当前快照，不代表客户已确认或项目 Gate 已通过。</p>
        <ol aria-label="六阶段流程">
          <li v-for="stage in workflow.stages" :key="stage.stage_key">
            <h2>{{ stage.order }}. {{ stage.stage_key }} · {{ stage.state }}</h2>
            <ul><li v-for="item in stage.checklist_items" :key="item.item_key">
              {{ item.item_key }} · {{ item.state }}
            </li></ul>
          </li>
        </ol>
      </template>
      <button v-if="workflow?.state === 'NOT_STARTED' && !pending && !startTarget && mayStart() && !requireFreshRead && !receipt"
        type="button" :disabled="busy || writeBusy" @click="beginStart">准备启动流程</button>
      <form v-if="startTarget && mayStart() && !pending && !requireFreshRead" @submit.prevent="submitStart">
        <h2>确认启动项目流程</h2>
        <p>仅激活首阶段 HANDOVER，不确认任何清单、Review 或 Gate；基于 {{ startTarget.etag }} 初态。</p>
        <label><input v-model="startConfirmed" type="checkbox" :disabled="writeBusy" />我已核对项目和初态，确认启动</label>
        <button type="submit" :disabled="busy || writeBusy || !startConfirmed">{{ writeBusy ? '正在提交…' : '确认启动' }}</button>
      </form>
      <form v-if="pending && canRetry()" @submit.prevent="submitStart">
        <h2>使用原操作号核查未确定的启动</h2>
        <p>当前仍为原 v0 初态。此操作只使用已保存的原 Key，不产生新 Key；仍应先核对审计。</p>
        <label><input v-model="retryConfirmed" type="checkbox" :disabled="writeBusy" />我已核对原操作和当前流程</label>
        <button type="submit" :disabled="busy || writeBusy || !retryConfirmed">使用原操作号重试</button>
      </form>
      <div v-if="pending && workflow && workflow.workflow_id === pending.workflow && workflow.etag !== pending.etag">
        <p>当前流程已变化。不能自动认定由本次操作造成；请核对审计后再清除原操作记录。</p>
        <label><input v-model="clearConfirmed" type="checkbox" :disabled="busy || writeBusy" />我已核对当前流程与审计</label>
        <button type="button" :disabled="busy || writeBusy || !clearConfirmed" @click="acknowledgeChanged">清除原操作记录</button>
      </div>
    </template>
  </section>
</template>
