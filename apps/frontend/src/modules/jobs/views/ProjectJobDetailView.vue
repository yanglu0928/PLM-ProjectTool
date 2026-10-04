<script setup lang="ts">
import { inject, onUnmounted, ref, shallowRef, toRaw, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { sessionClientKey } from "@/modules/auth/api/sessionContext";
import { JobDetailClient, JobDetailError } from "@/modules/jobs/api/jobDetailClient";
import { JobCancelClient, JobCancelError, type JobCancelFirstReceipt } from "@/modules/jobs/api/jobCancelClient";
import type { JobListItem } from "@/modules/jobs/api/jobListClient";

const props = defineProps<{ session?: SessionClient; jobs?: JobDetailClient; canceller?: JobCancelClient }>();
const session = toRaw(props.session ?? inject(sessionClientKey, null) ?? new SessionClient());
const jobs = toRaw(props.jobs ?? new JobDetailClient());
const canceller = toRaw(props.canceller ?? new JobCancelClient(session));
const identity = session.view;
const route = useRoute();
const item = ref<JobListItem | null>(null);
const busy = ref(false);
const error = ref("");
const cancelBusy = ref(false);
const cancelError = ref("");
const cancelTarget = ref<JobListItem | null>(null);
const cancelReason = ref("");
const cancelConfirmed = ref(false);
const cancelReceipt = ref<JobCancelFirstReceipt | null>(null);
type PendingCancel = { actor: string; project: string; job: string; key: string; etag: string };
const storageKey = identity ? `plm.jobs.cancel.pending.${identity.user.user_id}` : "";
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const storageError = ref(false);
function validPending(value: unknown): value is PendingCancel {
  if (typeof value !== "object" || value === null || Array.isArray(value)) return false;
  const entry = value as Record<string, unknown>;
  return entry.actor === identity?.user.user_id && typeof entry.project === "string" && uuid.test(entry.project)
    && typeof entry.job === "string" && uuid.test(entry.job)
    && typeof entry.key === "string" && /^[\x20-\x7e]{16,128}$/.test(entry.key)
    && typeof entry.etag === "string" && /^"v(0|[1-9][0-9]*)"$/.test(entry.etag);
}
function readPending(): PendingCancel | null {
  if (!storageKey) return null;
  try {
    const value = window.sessionStorage.getItem(storageKey);
    if (value === null) return null;
    const parsed: unknown = JSON.parse(value);
    if (validPending(parsed)) return parsed;
  } catch { /* Fail closed when original operation cannot be recovered. */ }
  storageError.value = true;
  return null;
}
const pending = shallowRef<PendingCancel | null>(readPending());
const clearConfirmed = ref(false);
function savePending(value: PendingCancel): boolean {
  if (!storageKey || storageError.value || pending.value) return false;
  try {
    const serialized = JSON.stringify(value);
    window.sessionStorage.setItem(storageKey, serialized);
    if (window.sessionStorage.getItem(storageKey) !== serialized) return false;
    pending.value = value;
    return true;
  } catch { storageError.value = true; return false; }
}
function clearPending(value: PendingCancel): boolean {
  if (!storageKey || pending.value !== value) return false;
  try {
    if (window.sessionStorage.getItem(storageKey) !== JSON.stringify(value)) return false;
    window.sessionStorage.removeItem(storageKey);
    if (window.sessionStorage.getItem(storageKey) !== null) return false;
    pending.value = null;
    return true;
  } catch { storageError.value = true; return false; }
}
let mounted = true;
let generation = 0;

function mayRead() {
  return mounted && !!identity && !identity.password_change_required
    && session.view?.user.user_id === identity.user.user_id;
}
function mayCancel() {
  return mayRead() && session.canSubmit && !storageError.value && !pending.value && !busy.value
    && !cancelBusy.value && !!session.view?.authorized_projects.some(p => p.project_id === route.params.projectId);
}
function beginCancel() {
  if (!mayCancel() || !item.value || !["PENDING", "RUNNING", "RETRY_WAIT", "CANCEL_REQUESTED"].includes(item.value.state)) return;
  cancelTarget.value = Object.freeze({ ...item.value });
  cancelReason.value = ""; cancelConfirmed.value = false; cancelError.value = "";
}
async function submitCancel() {
  const target = cancelTarget.value;
  if (!target || !mayCancel() || !cancelConfirmed.value || !item.value
    || item.value.job_id !== target.job_id || item.value.etag !== target.etag
    || route.params.projectId !== target.project_id || route.params.jobId !== target.job_id) return;
  const reason = cancelReason.value.trim();
  if (reason.length < 1 || reason.length > 1024 || /\p{C}/u.test(reason)) {
    cancelError.value = "取消原因须为 1～1024 字且不能包含控制字符；请求未发送。";
    return;
  }
  const attempt: PendingCancel = { actor: identity!.user.user_id, project: target.project_id!,
    job: target.job_id, key: crypto.randomUUID(), etag: target.etag };
  if (!savePending(attempt)) { storageError.value = true; cancelError.value = "无法安全保存原操作号，取消请求未发送。"; return; }
  const current = ++generation;
  cancelTarget.value = null; cancelConfirmed.value = false; cancelReason.value = "";
  cancelBusy.value = true; cancelError.value = ""; item.value = null;
  try {
    const receipt = await canceller.cancel(attempt.project, target, attempt.key, reason);
    if (!mounted || current !== generation || route.params.projectId !== attempt.project
      || route.params.jobId !== attempt.job || !mayRead()) return;
    cancelReceipt.value = receipt;
    if (!clearPending(attempt)) storageError.value = true;
  } catch (failure) {
    if (!mounted || current !== generation || route.params.projectId !== attempt.project
      || route.params.jobId !== attempt.job) return;
    if (failure instanceof JobCancelError && !failure.uncertain && failure.code !== "CONFLICT_IDEMPOTENCY") {
      if (!clearPending(attempt)) storageError.value = true;
      cancelError.value = failure.message + " 请重新读取任务详情。";
    } else {
      cancelError.value = "取消结果无法确认；已保留原操作号和版本。先重新读取当前任务并核对，不要生成新操作。";
    }
  } finally { if (mounted && current === generation) cancelBusy.value = false; }
}
function acknowledgePending() {
  const attempt = pending.value;
  if (!attempt || !clearConfirmed.value || !item.value || !mayRead() || busy.value || cancelBusy.value
    || attempt.project !== route.params.projectId || attempt.job !== route.params.jobId
    || item.value.etag === attempt.etag) return;
  if (!clearPending(attempt)) { storageError.value = true; return; }
  clearConfirmed.value = false; cancelError.value = "原操作记录已由用户在核对当前变化后清除；如仍需取消，请重新评估当前任务。";
}
async function load() {
  if (!mayRead() || busy.value || cancelBusy.value) return;
  const projectId = typeof route.params.projectId === "string" ? route.params.projectId : "";
  const jobId = typeof route.params.jobId === "string" ? route.params.jobId : "";
  const current = ++generation;
  item.value = null;
  cancelTarget.value = null; cancelReason.value = ""; cancelConfirmed.value = false; clearConfirmed.value = false;
  error.value = "";
  busy.value = true;
  try {
    const latest = await jobs.getProject(projectId, jobId);
    if (!mounted || current !== generation || route.params.projectId !== projectId
      || route.params.jobId !== jobId || !mayRead()) return;
    item.value = latest;
    cancelReceipt.value = null;
  } catch (failure) {
    if (!mounted || current !== generation || route.params.projectId !== projectId || route.params.jobId !== jobId) return;
    item.value = null;
    error.value = failure instanceof JobDetailError ? failure.message : "暂时无法读取任务详情，请稍后重试。";
  } finally { if (mounted && current === generation) busy.value = false; }
}
watch(() => [route.params.projectId, route.params.jobId], () => {
  generation += 1;
  busy.value = false;
  item.value = null;
  error.value = "";
  cancelTarget.value = null; cancelReason.value = ""; cancelConfirmed.value = false;
  cancelReceipt.value = null; cancelError.value = ""; clearConfirmed.value = false;
  void load();
}, { immediate: true });
onUnmounted(() => { mounted = false; generation += 1; });
</script>

<template>
  <section class="job-detail" aria-labelledby="job-detail-title" :aria-busy="busy || cancelBusy">
    <p class="section-kicker">项目任务</p>
    <h1 id="job-detail-title">运行任务详情</h1>
    <p>详情每次由服务器重新核验当前项目与原资源权限。版本标识不是操作授权；结果引用也不是文件下载许可。</p>
    <p><RouterLink :to="{ name: 'project-jobs', params: { projectId: route.params.projectId } }">返回项目任务列表</RouterLink></p>
    <template v-if="!identity">
      <p role="status">尚未读取当前身份。请先登录，或在账户页读取当前身份。</p>
      <RouterLink to="/login">前往账户与登录</RouterLink>
    </template>
    <template v-else-if="identity.password_change_required">
      <p role="status">当前账户须先修改密码，暂不能读取任务详情。</p>
      <RouterLink to="/login">前往账户与登录</RouterLink>
    </template>
    <template v-else>
      <button type="button" :disabled="busy || cancelBusy" @click="load">{{ busy ? "正在读取…" : "刷新任务详情" }}</button>
      <p v-if="busy" role="status">正在确认当前任务访问权限…</p>
      <p v-if="error" role="alert">{{ error }}</p>
      <p v-if="cancelError" role="alert">{{ cancelError }}</p>
      <p v-if="storageError" role="alert">浏览器会话记录不可用或损坏；取消入口已关闭，避免丢失原操作号。</p>
      <p v-if="cancelReceipt" role="status">取消首次回执：{{ cancelReceipt.first_result.state }} · {{ cancelReceipt.first_result.etag }}。这不是当前状态，请刷新任务详情。</p>
      <p v-if="pending" role="status">有待核对的原取消操作：{{ pending.job }} · {{ pending.etag }}，操作号 {{ pending.key }}。不得生成新操作号；跨页面仍保留在本浏览器会话。</p>
      <p v-if="pending && (pending.project !== route.params.projectId || pending.job !== route.params.jobId)"><RouterLink :to="{ name: 'project-job-detail', params: { projectId: pending.project, jobId: pending.job } }">前往原任务核对</RouterLink></p>
      <dl v-if="item" aria-label="当前授权任务详情">
        <dt>任务号</dt><dd>{{ item.job_id }}</dd>
        <dt>类型</dt><dd>{{ item.job_type }}</dd>
        <dt>来源模块</dt><dd>{{ item.owner_module }}</dd>
        <dt>状态</dt><dd>{{ item.state }}</dd>
        <dt>尝试次数</dt><dd>{{ item.attempt_count }}</dd>
        <dt>允许人工重试</dt><dd>{{ item.retryable ? "是；本页未开放重试" : "否" }}</dd>
        <dt>当前版本</dt><dd>{{ item.etag }}</dd>
        <dt>创建时间</dt><dd><time :datetime="item.created_at">{{ new Date(item.created_at).toLocaleString('zh-CN') }}</time></dd>
        <template v-if="item.completed_at"><dt>完成时间</dt><dd><time :datetime="item.completed_at">{{ new Date(item.completed_at).toLocaleString('zh-CN') }}</time></dd></template>
        <template v-if="item.result_ref"><dt>逻辑结果引用</dt><dd>{{ item.result_ref.type }}：{{ item.result_ref.id }}</dd></template>
      </dl>
      <button v-if="item && !cancelReceipt && mayCancel() && ['PENDING', 'RUNNING', 'RETRY_WAIT', 'CANCEL_REQUESTED'].includes(item.state)"
        type="button" @click="beginCancel">申请取消此任务</button>
      <form v-if="cancelTarget && mayCancel()" @submit.prevent="submitCancel">
        <h2>确认取消任务 {{ cancelTarget.job_id }}</h2>
        <p>原状态 {{ cancelTarget.state }}、版本 {{ cancelTarget.etag }}。取消是协作请求，不回滚已发布副作用；最终结果以刷新后的任务详情为准。</p>
        <label>取消原因 <textarea v-model="cancelReason" required maxlength="1024" :disabled="cancelBusy" /></label>
        <label><input v-model="cancelConfirmed" type="checkbox" :disabled="cancelBusy" />我已核对任务号、状态与版本</label>
        <button type="submit" :disabled="cancelBusy || !cancelConfirmed || !cancelReason.trim()">确认提交取消请求</button>
      </form>
      <form v-if="pending && item && pending.project === route.params.projectId && pending.job === route.params.jobId && item.etag !== pending.etag"
        @submit.prevent="acknowledgePending">
        <p>当前任务版本 {{ item.etag }} 已不同于原提交版本。此变化不证明原请求成功；请先核对任务和审计，再由本人决定是否清除本机待核对记录。</p>
        <label><input v-model="clearConfirmed" type="checkbox" />我已核对当前任务及审计，知悉清除后不能恢复原操作号</label>
        <button type="submit" :disabled="!clearConfirmed">清除本机待核对记录</button>
      </form>
    </template>
  </section>
</template>

<style scoped>
.job-detail { max-width: 48rem; margin: 1rem auto; padding: 1.5rem; background: #fff; border-radius: 1rem; }
.job-detail p { line-height: 1.65; }
.job-detail dl { display: grid; grid-template-columns: max-content minmax(0,1fr); gap: .5rem 1rem; overflow-wrap: anywhere; }
.job-detail dt { font-weight: 600; }
.job-detail dd { margin: 0; }
.job-detail [role="alert"] { color: #a21d25; }
.job-detail form { display: grid; gap: .7rem; margin-top: 1rem; }
</style>
