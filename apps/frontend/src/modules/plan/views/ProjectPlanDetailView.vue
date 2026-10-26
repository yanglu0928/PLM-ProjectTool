<script setup lang="ts">
import { inject, onUnmounted, ref, toRaw, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { sessionClientKey } from "@/modules/auth/api/sessionContext";
import { PlanReadClient, type PlanCurrent } from "@/modules/plan/api/planReadClient";

const props = defineProps<{ session?: SessionClient; reader?: PlanReadClient }>();
const session = toRaw(props.session ?? inject(sessionClientKey, null) ?? new SessionClient());
const reader = toRaw(props.reader ?? new PlanReadClient());
const route = useRoute();
const current = ref<PlanCurrent | null>(null); const busy = ref(false); const error = ref("");
let generation = 0; let mounted = true;
const projectId = () => typeof route.params.projectId === "string" ? route.params.projectId : "";
const planId = () => typeof route.params.planId === "string" ? route.params.planId : "";
function mayRead() {
  return mounted && !!session.view && !session.view.password_change_required
    && session.view.authorized_projects.some(item => item.project_id === projectId());
}
async function load() {
  if (!mayRead() || busy.value) return;
  const project = projectId(), plan = planId(), run = ++generation;
  busy.value = true; error.value = ""; current.value = null;
  try {
    const result = await reader.current(project, plan);
    if (!mounted || run !== generation || project !== projectId() || plan !== planId()
      || !mayRead()) return;
    current.value = result;
  } catch (failure) {
    if (mounted && run === generation) error.value = failure instanceof Error
      ? failure.message : "暂时无法读取实施计划。";
  } finally { if (mounted && run === generation) busy.value = false; }
}
watch(() => [route.params.projectId, route.params.planId], () => {
  generation += 1; current.value = null; busy.value = false; error.value = "";
  void load();
}, { immediate: true });
onUnmounted(() => { mounted = false; generation += 1; });
</script>

<template>
  <section class="plan-detail" aria-labelledby="plan-detail-title" :aria-busy="busy">
    <p class="section-kicker">项目实施</p><h1 id="plan-detail-title">实施计划详情</h1>
    <p class="warning">此处只显示当前计划身份。计划版本、WBS、评审和输出文件尚未由此确认；不得据此判断实施计划已交付。</p>
    <p><RouterLink :to="{ name: 'project-plans', params: { projectId: route.params.projectId } }">返回实施计划</RouterLink></p>
    <p v-if="!session.view" role="status">尚未读取当前身份，请先登录。</p>
    <p v-else-if="session.view.password_change_required" role="status">当前账户须先修改密码。</p>
    <p v-else-if="!mayRead()" role="status">当前账户无权查看此项目的实施计划。</p>
    <template v-else>
      <button type="button" :disabled="busy" @click="load()">{{ busy ? "正在读取…" : "重新读取计划" }}</button>
      <p v-if="error" role="alert">{{ error }}</p>
      <template v-if="current"><h2>{{ current.name }}</h2>
        <p><RouterLink :to="{ name: 'project-plan-versions', params: { projectId: current.project_id, planId: current.plan_id } }">查看计划版本历史</RouterLink></p>
        <dl><dt>计划状态</dt><dd>{{ current.plan_state === "ARCHIVED" ? "已归档" : "活动中" }}</dd>
          <dt>批准版引用</dt><dd>尚无已审批计划版本</dd>
          <dt>创建时间</dt><dd><time :datetime="current.created_at">{{ new Date(current.created_at).toLocaleString("zh-CN") }}</time></dd>
          <dt>并发版本</dt><dd>{{ current.etag }}</dd></dl>
      </template>
    </template>
  </section>
</template>

<style scoped>
.plan-detail{max-width:60rem;margin:1rem auto;padding:1.5rem;background:#fff;border-radius:1rem}
.plan-detail dl{display:grid;grid-template-columns:10rem 1fr;gap:.5rem}
.plan-detail dd{margin:0;overflow-wrap:anywhere}
.warning{padding:.8rem 1rem;border-left:.3rem solid #d29b42;background:#fff8e9}
.plan-detail [role=alert]{color:#a21d25}
</style>
