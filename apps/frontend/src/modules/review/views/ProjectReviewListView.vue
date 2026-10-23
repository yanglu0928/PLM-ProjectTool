<script setup lang="ts">
import { inject, onUnmounted, ref, toRaw, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { sessionClientKey } from "@/modules/auth/api/sessionContext";
import { ProjectReviewListClient, type ReviewListItem, type ReviewListMode } from
  "@/modules/review/api/projectReviewListClient";

const props = defineProps<{ session?: SessionClient; reader?: ProjectReviewListClient }>();
const session = toRaw(props.session ?? inject(sessionClientKey, null) ?? new SessionClient());
const reader = toRaw(props.reader ?? new ProjectReviewListClient());
const route = useRoute();
const mode = ref<ReviewListMode>("my_pending");
const items = ref<readonly ReviewListItem[]>([]);
const cursor = ref<string | null>(null);
const busy = ref(false); const loaded = ref(false); const error = ref("");
const sessionRevision = ref(session.revision);
let mounted = true; let generation = 0;
const projectId = () => typeof route.params.projectId === "string" ? route.params.projectId : "";
function mayRead() {
  void sessionRevision.value;
  return mounted && !!session.view && !session.view.password_change_required
    && session.view.authorized_projects.some(item => item.project_id === projectId());
}
function clear() { items.value = []; cursor.value = null; loaded.value = false; error.value = ""; }
function stateLabel(value: string) {
  return ({ DRAFT: "待开始", IN_REVIEW: "评审中", APPROVED: "已批准",
    RETURNED: "已退回", WITHDRAWN: "已撤回" } as Record<string, string>)[value] ?? "未知";
}
function subjectLabel(value: string) {
  return value === "SOL-05" ? "方案章节" : value === "SOL-06" ? "结构化专项" : value;
}
async function load(replace = false) {
  if (!mayRead() || busy.value) return;
  const project = projectId(), view = mode.value, actor = session.view!.user.user_id;
  const run = ++generation;
  if (replace) clear();
  busy.value = true; error.value = "";
  let next = cursor.value;
  const merged = [...items.value];
  const seen = new Set(merged.map(item => item.review_id));
  const cursors = new Set<string>();
  try {
    // Authorization can hide an entire raw page. Continue through empty pages.
    // Bound each UI operation so a long history cannot keep the page busy forever.
    for (let count = 0; count < 20; count += 1) {
      const page = await reader.list(project, view, 50, next);
      if (!mounted || run !== generation || project !== projectId()
        || view !== mode.value || actor !== session.view?.user.user_id || !mayRead()) return;
      for (const entry of page.items) {
        if (entry.project_id !== project || seen.has(entry.review_id)
          || view === "my_pending" && entry.active_round?.my_assignment?.state !== "PENDING") {
          throw new Error("评审列表不一致，请刷新重试。");
        }
        seen.add(entry.review_id); merged.push(entry);
      }
      next = page.next_cursor;
      if (!page.has_more) break;
      if (!next || cursors.has(next)) throw new Error("评审翻页位置无效，请刷新重试。");
      cursors.add(next);
    }
    items.value = Object.freeze(merged);
    cursor.value = next;
    loaded.value = true;
  } catch (failure) {
    if (!mounted || run !== generation) return;
    clear(); error.value = failure instanceof Error ? failure.message : "暂时无法读取评审待办。";
  } finally { if (mounted && run === generation) busy.value = false; }
}
function switchMode(value: ReviewListMode) {
  if (mode.value === value) return;
  generation += 1; busy.value = false; clear(); mode.value = value;
  void load(true);
}
const unsubscribe = session.subscribe(() => {
  sessionRevision.value = session.revision;
  generation += 1; busy.value = false; clear();
  if (route.name === "project-reviews" && mayRead()) void load(true);
});
watch(() => [route.name, route.params.projectId], () => {
  generation += 1; busy.value = false; clear(); mode.value = "my_pending";
  if (route.name === "project-reviews") void load(true);
}, { immediate: true });
onUnmounted(() => { mounted = false; generation += 1; unsubscribe(); clear(); });
</script>

<template>
  <section class="review-list" aria-labelledby="review-list-title" :aria-busy="busy">
    <p class="section-kicker">项目治理 · 当前授权列表</p>
    <h1 id="review-list-title">评审待办与历史</h1>
    <p><RouterLink :to="{ name: 'project-detail', params: { projectId: route.params.projectId } }">返回项目详情</RouterLink></p>
    <p class="notice">“我的待处理”只显示当前账户尚待决定的评审；历史状态不代表客户确认、实施完成或 UAT 通过。</p>
    <p v-if="!session.view" role="status">请先登录并读取当前身份。</p>
    <p v-else-if="session.view.password_change_required" role="status">当前账户须先修改密码。</p>
    <p v-else-if="!mayRead()" role="status">当前会话没有此项目的读取权限。</p>
    <template v-else>
      <div class="tabs" role="group" aria-label="评审列表范围">
        <button type="button" :aria-pressed="mode==='my_pending'" :disabled="busy" @click="switchMode('my_pending')">我的待处理</button>
        <button type="button" :aria-pressed="mode==='all'" :disabled="busy" @click="switchMode('all')">全部可见历史</button>
      </div>
      <button type="button" :disabled="busy" @click="load(true)">{{ busy ? '正在读取…' : '刷新列表' }}</button>
      <p v-if="error" role="alert">{{ error }}</p>
      <p v-else-if="busy" role="status">正在从服务器读取并自动翻页…</p>
      <p v-if="loaded && !items.length" role="status">{{ mode==='my_pending' ? '当前没有待处理评审。' : '当前没有可见评审历史。' }}</p>
      <ol v-if="items.length" aria-label="评审结果"><li v-for="entry in items" :key="entry.review_id">
        <strong>{{ stateLabel(entry.state) }} · {{ subjectLabel(entry.subject_ref.resource_type) }}</strong>
        <span>评审编号 {{ entry.review_id }}</span>
        <span>主题编号 {{ entry.subject_ref.resource_id }}</span>
        <span v-if="entry.active_round">轮次 {{ entry.active_round.round_no }} · {{ entry.active_round.my_assignment?.state==='PENDING' ? '我的待决定' : '无我的待决定' }}</span>
        <time :datetime="entry.created_at">{{ new Date(entry.created_at).toLocaleString('zh-CN') }}</time>
        <RouterLink :to="{ name: 'project-review-detail', params: { projectId: entry.project_id, reviewId: entry.review_id } }">打开评审并核对当前状态</RouterLink>
      </li></ol>
      <button v-if="cursor" type="button" :disabled="busy" @click="load()">继续加载更早评审</button>
    </template>
  </section>
</template>

<style scoped>
.review-list{max-width:64rem;margin:1rem auto;padding:1.5rem;background:#fff;border-radius:1rem}
.review-list ol{display:grid;gap:.8rem;padding:0;list-style:none}
.review-list li{display:grid;gap:.35rem;padding:1rem;border:1px solid #d8dee7;border-radius:.75rem}
.review-list button{margin:.3rem .7rem .3rem 0}
.tabs{display:flex;gap:.5rem;margin-block:1rem}.tabs [aria-pressed=true]{background:#173f69;color:#fff}
.notice{padding:.8rem 1rem;border-left:.3rem solid #d29b42;background:#fff8e9}
.review-list [role=alert]{color:#a21d25}
</style>
