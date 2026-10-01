<script setup lang="ts">
import { inject, onUnmounted, ref, toRaw, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { sessionClientKey } from "@/modules/auth/api/sessionContext";
import { JobListClient, JobListError, type JobListItem } from "@/modules/jobs/api/jobListClient";

const props = defineProps<{ session?: SessionClient; jobs?: JobListClient }>();
const session = toRaw(props.session ?? inject(sessionClientKey, null) ?? new SessionClient());
const jobs = toRaw(props.jobs ?? new JobListClient());
const identity = session.view;
const route = useRoute();
const items = ref<readonly JobListItem[]>([]);
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
async function load(next: string | null = null, replace = false) {
  if (!mayRead() || busy.value) return;
  const projectId = typeof route.params.projectId === "string" ? route.params.projectId : "";
  const current = ++generation;
  busy.value = true;
  error.value = "";
  if (replace) { items.value = []; cursor.value = null; loaded.value = false; }
  try {
    const page = await jobs.listProject(projectId, 50, next);
    if (!mounted || generation !== current || route.params.projectId !== projectId || !mayRead()) return;
    const known = new Set(items.value.map(item => item.job_id));
    if (page.items.some(item => known.has(item.job_id))) throw new JobListError("JOB_LIST_UNAVAILABLE");
    items.value = Object.freeze([...items.value, ...page.items]);
    cursor.value = page.next_cursor;
    loaded.value = true;
  } catch (failure) {
    if (!mounted || generation !== current || route.params.projectId !== projectId) return;
    items.value = []; cursor.value = null; loaded.value = false;
    error.value = failure instanceof JobListError ? failure.message : "暂时无法读取任务列表，请稍后重试。";
  } finally { if (mounted && generation === current) busy.value = false; }
}
watch(() => route.params.projectId, () => {
  generation += 1;
  items.value = []; cursor.value = null; loaded.value = false; error.value = ""; busy.value = false;
  void load(null, true);
}, { immediate: true });
onUnmounted(() => { mounted = false; generation += 1; });
</script>

<template>
  <section class="job-panel" aria-labelledby="job-list-title" :aria-busy="busy">
    <p class="section-kicker">项目任务</p>
    <h1 id="job-list-title">运行任务列表</h1>
    <p>只显示服务器当前授权的任务元数据；跨页结果不代表同一时刻的快照。此页面不提供取消或重试操作。</p>
    <p><RouterLink :to="{ name: 'project-detail', params: { projectId: route.params.projectId } }">返回项目详情</RouterLink></p>
    <template v-if="!identity">
      <p role="status">尚未读取当前身份。请先登录，或在账户页读取当前身份。</p>
      <RouterLink to="/login">前往账户与登录</RouterLink>
    </template>
    <template v-else-if="identity.password_change_required">
      <p role="status">当前账户须先修改密码，暂不能读取项目任务。</p>
      <RouterLink to="/login">前往账户与登录</RouterLink>
    </template>
    <template v-else>
      <button type="button" :disabled="busy" @click="load(null, true)">{{ busy ? "正在读取…" : "刷新任务列表" }}</button>
      <p v-if="busy" role="status">正在确认项目任务访问权限…</p>
      <p v-if="error" role="alert">{{ error }}</p>
      <p v-if="loaded && !items.length" role="status">当前项目没有可见任务。</p>
      <ul v-if="items.length" aria-label="项目运行任务">
        <li v-for="item in items" :key="item.job_id">
          <strong>{{ item.job_type }} · {{ item.state }}</strong>
          <span>任务号：{{ item.job_id }}</span>
          <span>创建：<time :datetime="item.created_at">{{ new Date(item.created_at).toLocaleString('zh-CN') }}</time></span>
          <span>尝试：{{ item.attempt_count }} · 版本：{{ item.etag }}</span>
          <span v-if="item.completed_at">完成：<time :datetime="item.completed_at">{{ new Date(item.completed_at).toLocaleString('zh-CN') }}</time></span>
        </li>
      </ul>
      <button v-if="cursor && loaded" type="button" :disabled="busy" @click="load(cursor)">加载更多任务</button>
    </template>
  </section>
</template>

<style scoped>
.job-panel { max-width: 48rem; margin: 1rem auto; padding: 1.5rem; background: #fff; border-radius: 1rem; }
.job-panel p { line-height: 1.65; }
.job-panel li { display: grid; gap: .35rem; padding: .8rem 0; border-bottom: 1px solid #d8dee7; overflow-wrap: anywhere; }
.job-panel [role="alert"] { color: #a21d25; }
</style>
