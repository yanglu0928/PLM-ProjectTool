<script setup lang="ts">
import { inject, onUnmounted, ref, toRaw, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { sessionClientKey } from "@/modules/auth/api/sessionContext";
import { PlanReadClient, PlanReadError, planFollows, type PlanSummary } from "@/modules/plan/api/planReadClient";

const props = defineProps<{ session?: SessionClient; reader?: PlanReadClient }>();
const session = toRaw(props.session ?? inject(sessionClientKey, null) ?? new SessionClient());
const reader = toRaw(props.reader ?? new PlanReadClient());
const route = useRoute();
const items = ref<readonly PlanSummary[]>([]);
const cursor = ref<string | null>(null);
const busy = ref(false); const loaded = ref(false); const error = ref("");
let generation = 0; let mounted = true;
const projectId = () => typeof route.params.projectId === "string" ? route.params.projectId : "";
function mayRead() {
  return mounted && !!session.view && !session.view.password_change_required
    && session.view.authorized_projects.some(item => item.project_id === projectId());
}
function mayCreate() {
  return mayRead() && session.canSubmit && session.view!.authorized_projects.some(item =>
    item.project_id === projectId()
    && (item.role === "PROJECT_MANAGER" || item.role === "IMPLEMENTATION_MEMBER"));
}
async function load(next: string | null = null, replace = false) {
  if (!mayRead() || busy.value) return;
  const project = projectId(), current = ++generation;
  busy.value = true; error.value = "";
  if (replace) { items.value = []; cursor.value = null; loaded.value = false; }
  try {
    const page = await reader.list(project, 50, next);
    if (!mounted || current !== generation || project !== projectId() || !mayRead()) return;
    const previous = items.value;
    if (page.items.some(item => previous.some(old => old.plan_id === item.plan_id))
      || previous.length > 0 && page.items.length > 0
        && !planFollows(previous[previous.length - 1]!, page.items[0]!)) {
      throw new PlanReadError("PLAN_UNAVAILABLE");
    }
    items.value = Object.freeze([...previous, ...page.items]);
    cursor.value = page.next_cursor; loaded.value = true;
  } catch (failure) {
    if (!mounted || current !== generation) return;
    items.value = []; cursor.value = null; loaded.value = false;
    error.value = failure instanceof Error ? failure.message : "暂时无法读取实施计划。";
  } finally { if (mounted && current === generation) busy.value = false; }
}
watch(() => route.params.projectId, () => {
  generation += 1; items.value = []; cursor.value = null; loaded.value = false;
  busy.value = false; error.value = "";
  void load(null, true);
}, { immediate: true });
onUnmounted(() => { mounted = false; generation += 1; });
</script>

<template>
  <section class="plan-list" aria-labelledby="plan-list-title" :aria-busy="busy">
    <p class="section-kicker">项目实施</p><h1 id="plan-list-title">实施计划</h1>
    <p class="warning">这里仅登记计划身份。计划版本、实施 WBS、评审和交付文件尚未由此创建或确认。</p>
    <p><RouterLink :to="{ name: 'project-detail', params: { projectId: route.params.projectId } }">返回项目详情</RouterLink></p>
    <p v-if="mayCreate()"><RouterLink :to="{ name: 'project-plan-create', params: { projectId: route.params.projectId } }">创建实施计划</RouterLink></p>
    <p v-if="!session.view" role="status">尚未读取当前身份，请先登录。</p>
    <p v-else-if="session.view.password_change_required" role="status">当前账户须先修改密码。</p>
    <p v-else-if="!mayRead()" role="status">当前账户无权查看此项目的实施计划。</p>
    <template v-else>
      <button type="button" :disabled="busy" @click="load(null, true)">{{ busy ? "正在读取…" : "刷新计划" }}</button>
      <p v-if="error" role="alert">{{ error }}</p>
      <p v-if="loaded && !items.length" role="status">当前项目没有可见实施计划。</p>
      <ol v-if="items.length" aria-label="项目实施计划"><li v-for="item in items" :key="item.plan_id">
        <strong>{{ item.name }}</strong><span>{{ item.plan_state === "ARCHIVED" ? "已归档" : "活动中" }}</span>
        <span>尚无已审批计划版本</span>
        <time :datetime="item.created_at">{{ new Date(item.created_at).toLocaleString("zh-CN") }}</time>
        <RouterLink :to="{ name: 'project-plan-detail', params: { projectId: item.project_id,
          planId: item.plan_id } }">查看计划详情</RouterLink>
      </li></ol>
      <button v-if="cursor" type="button" :disabled="busy" @click="load(cursor)">加载更多计划</button>
    </template>
  </section>
</template>

<style scoped>
.plan-list{max-width:60rem;margin:1rem auto;padding:1.5rem;background:#fff;border-radius:1rem}
.plan-list ol{display:grid;gap:.8rem;padding:0;list-style:none}
.plan-list li{display:grid;gap:.35rem;padding:1rem;border:1px solid #d8dee7;border-radius:.75rem}
.warning{padding:.8rem 1rem;border-left:.3rem solid #d29b42;background:#fff8e9}
.plan-list [role=alert]{color:#a21d25}
</style>
