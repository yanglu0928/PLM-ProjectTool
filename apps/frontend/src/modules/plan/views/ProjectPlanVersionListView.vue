<script setup lang="ts">
import { inject, onUnmounted, ref, toRaw, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { sessionClientKey } from "@/modules/auth/api/sessionContext";
import { PlanVersionReadClient, PlanVersionReadError, type PlanVersionSummary } from "@/modules/plan/api/planVersionReadClient";
const props = defineProps<{ session?: SessionClient; reader?: PlanVersionReadClient }>();
const session = toRaw(props.session ?? inject(sessionClientKey, null) ?? new SessionClient());
const reader = toRaw(props.reader ?? new PlanVersionReadClient()); const route = useRoute();
const items = ref<readonly PlanVersionSummary[]>([]); const cursor = ref<string | null>(null);
const busy = ref(false); const loaded = ref(false); const error = ref(""); let generation = 0; let mounted = true;
const projectId = () => typeof route.params.projectId === "string" ? route.params.projectId : "";
const planId = () => typeof route.params.planId === "string" ? route.params.planId : "";
function mayRead() { return mounted && !!session.view && !session.view.password_change_required
  && session.view.authorized_projects.some(p => p.project_id === projectId()); }
async function load(next: string | null = null, replace = false) {
  if (!mayRead() || busy.value) return; const project = projectId(), plan = planId(), run = ++generation;
  busy.value = true; error.value = ""; if (replace) { items.value = []; cursor.value = null; loaded.value = false; }
  try { const page = await reader.list(project, plan, 50, next);
    if (!mounted || run !== generation || project !== projectId() || plan !== planId()) return;
    if (page.items.some(x => items.value.some(old => old.plan_version_id === x.plan_version_id)
      || items.value.length && x.version_no >= items.value[items.value.length - 1]!.version_no))
      throw new PlanVersionReadError("PLAN_VERSION_READ_UNAVAILABLE");
    items.value = Object.freeze([...items.value, ...page.items]); cursor.value = page.next_cursor; loaded.value = true;
  } catch (e) { if (mounted && run === generation) { items.value = []; cursor.value = null; loaded.value = false;
    error.value = e instanceof Error ? e.message : "暂时无法读取计划版本。"; } }
  finally { if (mounted && run === generation) busy.value = false; }
}
watch(() => [route.params.projectId, route.params.planId], () => { generation++; items.value = []; cursor.value = null;
  loaded.value = false; busy.value = false; error.value = ""; void load(null, true); }, { immediate: true });
onUnmounted(() => { mounted = false; generation++; });
</script>
<template><section class="plan-version-list" aria-labelledby="plan-version-list-title" :aria-busy="busy">
  <p class="section-kicker">项目实施</p><h1 id="plan-version-list-title">计划版本历史</h1>
  <p class="warning">每个版本是不可变历史快照。状态或历史引用不等于当前批准、客户确认或已交付。</p>
  <p><RouterLink :to="{ name: 'project-plan-detail', params: { projectId: route.params.projectId, planId: route.params.planId } }">返回计划详情</RouterLink></p>
  <p v-if="!session.view" role="status">尚未读取当前身份，请先登录。</p><p v-else-if="session.view.password_change_required" role="status">当前账户须先修改密码。</p>
  <p v-else-if="!mayRead()" role="status">当前账户无权查看此项目的计划版本。</p><template v-else>
    <button type="button" :disabled="busy" @click="load(null, true)">{{ busy ? "正在读取…" : "刷新版本历史" }}</button>
    <p v-if="error" role="alert">{{ error }}</p><p v-if="loaded && !items.length" role="status">此计划尚无可见版本。</p>
    <ol v-if="items.length"><li v-for="item in items" :key="item.plan_version_id"><strong>版本 {{ item.version_no }} · {{ item.version_state }}</strong>
      <span>创建于 <time :datetime="item.created_at">{{ new Date(item.created_at).toLocaleString("zh-CN") }}</time></span>
      <RouterLink :to="{ name: 'project-plan-version-detail', params: { projectId: item.project_id, planId: item.plan_id, versionId: item.plan_version_id } }">查看固定快照</RouterLink></li></ol>
    <button v-if="cursor" type="button" :disabled="busy" @click="load(cursor)">加载更早版本</button>
  </template>
</section></template>
<style scoped>.plan-version-list{max-width:64rem;margin:1rem auto;padding:1.5rem;background:#fff;border-radius:1rem}.plan-version-list ol{display:grid;gap:.8rem;padding:0;list-style:none}.plan-version-list li{display:grid;gap:.35rem;padding:1rem;border:1px solid #d8dee7;border-radius:.75rem}.warning{padding:.8rem 1rem;border-left:.3rem solid #d29b42;background:#fff8e9}.plan-version-list [role=alert]{color:#a21d25}</style>
