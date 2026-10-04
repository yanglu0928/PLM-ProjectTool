<script setup lang="ts">
import { inject, onMounted, onUnmounted, ref, toRaw } from "vue";
import { RouterLink } from "vue-router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { sessionClientKey } from "@/modules/auth/api/sessionContext";
import { JobListClient, JobListError, type JobListItem } from "@/modules/jobs/api/jobListClient";

const props = defineProps<{ session?: SessionClient; jobs?: JobListClient }>();
const session = toRaw(props.session ?? inject(sessionClientKey, null) ?? new SessionClient());
const jobs = toRaw(props.jobs ?? new JobListClient());
const actorId = session.view?.user.user_id;
const scope = ref<"ALL" | "GLOBAL" | "DEPLOYMENT">("ALL");
const items = ref<readonly JobListItem[]>([]);
const cursor = ref<string | null>(null);
const loaded = ref(false);
const busy = ref(false);
const error = ref("");
let mounted = true;
let generation = 0;

function mayRead() {
  return mounted && !!actorId && session.view?.user.user_id === actorId
    && session.view.deployment_role === "DEPLOYMENT_ADMIN" && !session.view.password_change_required;
}
async function load(next: string | null = null, replace = false) {
  if (!mayRead() || busy.value) return;
  const current = ++generation;
  const requestedScope = scope.value;
  busy.value = true;
  error.value = "";
  if (replace) { items.value = []; cursor.value = null; loaded.value = false; }
  try {
    const page = await jobs.listAdmin(requestedScope === "ALL" ? null : requestedScope, 50, next);
    if (!mounted || current !== generation || requestedScope !== scope.value || !mayRead()) return;
    const known = new Set(items.value.map(item => item.job_id));
    if (page.items.some(item => known.has(item.job_id))) throw new JobListError("JOB_LIST_UNAVAILABLE");
    items.value = Object.freeze([...items.value, ...page.items]);
    cursor.value = page.next_cursor;
    loaded.value = true;
  } catch (failure) {
    if (!mounted || current !== generation || requestedScope !== scope.value) return;
    items.value = []; cursor.value = null; loaded.value = false;
    error.value = failure instanceof JobListError ? failure.message : "暂时无法读取任务列表，请稍后重试。";
  } finally { if (mounted && current === generation) busy.value = false; }
}
function changeScope() {
  generation += 1;
  busy.value = false;
  items.value = []; cursor.value = null; loaded.value = false; error.value = "";
  void load(null, true);
}
onMounted(() => { void load(null, true); });
onUnmounted(() => { mounted = false; generation += 1; });
</script>

<template>
  <section class="job-panel" aria-labelledby="admin-job-title" :aria-busy="busy">
    <p class="section-kicker">部署任务</p>
    <h1 id="admin-job-title">全局与部署任务列表</h1>
    <p>仅部署管理员可读；不包含项目任务。服务端逐页核验当前权限，跨页结果不是同一时刻的快照。</p>
    <template v-if="!mayRead()">
      <p role="status">当前身份无权查看部署任务，或登录状态已变化。</p>
      <RouterLink to="/login">前往账户与登录</RouterLink>
    </template>
    <template v-else>
      <label for="job-scope">任务范围</label>
      <select id="job-scope" v-model="scope" @change="changeScope">
        <option value="ALL">全部可见范围</option>
        <option value="GLOBAL">全局</option>
        <option value="DEPLOYMENT">部署</option>
      </select>
      <button type="button" :disabled="busy" @click="load(null, true)">{{ busy ? "正在读取…" : "刷新任务列表" }}</button>
      <p v-if="busy" role="status">正在确认部署任务访问权限…</p>
      <p v-if="error" role="alert">{{ error }}</p>
      <p v-if="loaded && !items.length" role="status">当前范围没有可见任务。</p>
      <ul v-if="items.length" aria-label="部署运行任务">
        <li v-for="item in items" :key="item.job_id">
          <strong>{{ item.job_type }} · {{ item.state }}</strong>
          <span>范围：{{ item.scope }} · 任务号：<RouterLink :to="{ name: 'admin-job-detail', params: { jobId: item.job_id } }">{{ item.job_id }}</RouterLink></span>
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
