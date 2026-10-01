<script setup lang="ts">
import { inject, onUnmounted, ref, toRaw, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { sessionClientKey } from "@/modules/auth/api/sessionContext";
import { JobDetailClient, JobDetailError } from "@/modules/jobs/api/jobDetailClient";
import type { JobListItem } from "@/modules/jobs/api/jobListClient";

const props = defineProps<{ session?: SessionClient; jobs?: JobDetailClient }>();
const session = toRaw(props.session ?? inject(sessionClientKey, null) ?? new SessionClient());
const jobs = toRaw(props.jobs ?? new JobDetailClient());
const actorId = session.view?.user.user_id;
const route = useRoute();
const item = ref<JobListItem | null>(null);
const busy = ref(false);
const error = ref("");
let mounted = true;
let generation = 0;

function mayRead() {
  return mounted && !!actorId && session.view?.user.user_id === actorId
    && session.view.deployment_role === "DEPLOYMENT_ADMIN" && !session.view.password_change_required;
}
async function load() {
  if (!mayRead() || busy.value) return;
  const jobId = typeof route.params.jobId === "string" ? route.params.jobId : "";
  const current = ++generation;
  item.value = null;
  error.value = "";
  busy.value = true;
  try {
    const latest = await jobs.getAdmin(jobId);
    if (!mounted || current !== generation || route.params.jobId !== jobId || !mayRead()) return;
    item.value = latest;
  } catch (failure) {
    if (!mounted || current !== generation || route.params.jobId !== jobId) return;
    item.value = null;
    error.value = failure instanceof JobDetailError ? failure.message : "暂时无法读取任务详情，请稍后重试。";
  } finally { if (mounted && current === generation) busy.value = false; }
}
watch(() => route.params.jobId, () => {
  generation += 1;
  busy.value = false;
  item.value = null;
  error.value = "";
  void load();
}, { immediate: true });
onUnmounted(() => { mounted = false; generation += 1; });
</script>

<template>
  <section class="job-detail" aria-labelledby="admin-job-detail-title" :aria-busy="busy">
    <p class="section-kicker">部署任务</p>
    <h1 id="admin-job-detail-title">全局与部署任务详情</h1>
    <p>仅部署管理员可读，不包含项目任务。每次读取都由服务器重新核验；结果引用不是文件下载许可。</p>
    <p><RouterLink :to="{ name: 'admin-jobs' }">返回部署任务列表</RouterLink></p>
    <template v-if="!mayRead()">
      <p role="status">当前身份无权查看部署任务，或登录状态已变化。</p>
      <RouterLink to="/login">前往账户与登录</RouterLink>
    </template>
    <template v-else>
      <button type="button" :disabled="busy" @click="load">{{ busy ? "正在读取…" : "刷新任务详情" }}</button>
      <p v-if="busy" role="status">正在确认当前任务访问权限…</p>
      <p v-if="error" role="alert">{{ error }}</p>
      <dl v-if="item" aria-label="当前授权部署任务详情">
        <dt>任务号</dt><dd>{{ item.job_id }}</dd>
        <dt>范围</dt><dd>{{ item.scope }}</dd>
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
</style>
