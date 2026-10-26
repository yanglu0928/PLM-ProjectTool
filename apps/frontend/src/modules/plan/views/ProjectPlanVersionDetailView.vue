<script setup lang="ts">
import { inject, onUnmounted, ref, toRaw, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { sessionClientKey } from "@/modules/auth/api/sessionContext";
import { PlanVersionReadClient, type PlanVersionDetail } from "@/modules/plan/api/planVersionReadClient";
const props = defineProps<{ session?: SessionClient; reader?: PlanVersionReadClient }>();
const session = toRaw(props.session ?? inject(sessionClientKey, null) ?? new SessionClient());
const reader = toRaw(props.reader ?? new PlanVersionReadClient()); const route = useRoute();
const current = ref<PlanVersionDetail | null>(null); const busy = ref(false); const error = ref(""); let generation = 0; let mounted = true;
const projectId = () => typeof route.params.projectId === "string" ? route.params.projectId : "";
const planId = () => typeof route.params.planId === "string" ? route.params.planId : "";
const versionId = () => typeof route.params.versionId === "string" ? route.params.versionId : "";
function mayRead() { return mounted && !!session.view && !session.view.password_change_required
  && session.view.authorized_projects.some(p => p.project_id === projectId()); }
function mayValidate() { return mayRead() && session.canSubmit && session.view?.authorized_projects.some(p => p.project_id === projectId()
  && (p.role === "PROJECT_MANAGER" || p.role === "IMPLEMENTATION_MEMBER")); }
function maySubmitReview() { return mayRead() && session.canSubmit && session.view?.authorized_projects.some(p => p.project_id === projectId()
  && p.role === "PROJECT_MANAGER"); }
async function load() { if (!mayRead() || busy.value) return; const project = projectId(), plan = planId(), version = versionId(), run = ++generation;
  busy.value = true; error.value = ""; current.value = null;
  try { const value = await reader.detail(project, plan, version); if (!mounted || run !== generation || project !== projectId() || plan !== planId() || version !== versionId()) return; current.value = value; }
  catch (e) { if (mounted && run === generation) error.value = e instanceof Error ? e.message : "暂时无法读取固定快照。"; }
  finally { if (mounted && run === generation) busy.value = false; }
}
watch(() => [route.params.projectId, route.params.planId, route.params.versionId], () => { generation++; current.value = null; busy.value = false; error.value = ""; void load(); }, { immediate: true });
onUnmounted(() => { mounted = false; generation++; });
const pretty = (v: unknown) => JSON.stringify(v, null, 2);
</script>
<template><section class="plan-version-detail" aria-labelledby="plan-version-detail-title" :aria-busy="busy">
  <p class="section-kicker">项目实施</p><h1 id="plan-version-detail-title">计划固定版本快照</h1>
  <p class="warning">只读历史内容。快照中的来源引用不会随源记录更新；本页不代表当前来源仍合格，也不执行Validate或Review。</p>
  <p><RouterLink :to="{ name: 'project-plan-versions', params: { projectId: route.params.projectId, planId: route.params.planId } }">返回版本历史</RouterLink></p>
  <p v-if="!session.view" role="status">尚未读取当前身份，请先登录。</p><p v-else-if="session.view.password_change_required" role="status">当前账户须先修改密码。</p>
  <p v-else-if="!mayRead()" role="status">当前账户无权查看此项目的计划版本。</p><template v-else>
    <button type="button" :disabled="busy" @click="load()">{{ busy ? "正在读取…" : "重新读取固定版本" }}</button><p v-if="error" role="alert">{{ error }}</p>
    <template v-if="current"><h2>版本 {{ current.version_no }} · {{ current.version_state }}</h2><dl>
      <dt>版本ID</dt><dd>{{ current.plan_version_id }}</dd><dt>创建人</dt><dd>{{ current.created_by }}</dd><dt>前序版本</dt><dd>{{ current.supersedes_version_ref ?? "无" }}</dd>
      <dt>评审引用</dt><dd>{{ current.review_ref ?? "无" }}</dd><dt>评审轮次</dt><dd>{{ current.review_round_ref ?? "无" }}</dd>
      <dt>创建时间</dt><dd><time :datetime="current.created_at">{{ new Date(current.created_at).toLocaleString("zh-CN") }}</time></dd></dl>
      <p v-if="mayValidate()"><RouterLink :to="{ name: 'project-plan-version-validate', params: { projectId: current.project_id, planId: current.plan_id, versionId: current.plan_version_id } }">核查此固定版本</RouterLink></p>
      <p v-if="maySubmitReview() && current.version_state === 'DRAFT' && !current.review_ref && !current.review_round_ref"><RouterLink :to="{ name: 'project-plan-version-submit-review', params: { projectId: current.project_id, planId: current.plan_id, versionId: current.plan_version_id } }">提交此计划版本评审</RouterLink></p>
      <h3>日历固定引用</h3><pre>{{ pretty(current.calendar_ref) }}</pre>
      <h3>Approved Solution 固定引用（{{ current.approved_solution_refs.length }}）</h3><pre>{{ pretty(current.approved_solution_refs) }}</pre>
      <h3>WBS 固定快照（{{ current.wbs_items.length }}）</h3><pre>{{ pretty(current.wbs_items) }}</pre>
      <h3>依赖（{{ current.dependencies.length }}）</h3><pre>{{ pretty(current.dependencies) }}</pre>
      <h3>里程碑（{{ current.milestones.length }}）</h3><pre>{{ pretty(current.milestones) }}</pre>
      <h3>明确排除项（{{ current.exclusions.length }}）</h3><pre>{{ pretty(current.exclusions) }}</pre>
    </template></template>
</section></template>
<style scoped>.plan-version-detail{max-width:64rem;margin:1rem auto;padding:1.5rem;background:#fff;border-radius:1rem}.plan-version-detail dl{display:grid;grid-template-columns:10rem 1fr;gap:.5rem}.plan-version-detail dd{margin:0;overflow-wrap:anywhere}.plan-version-detail pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f5f7fa;padding:.7rem}.warning{padding:.8rem 1rem;border-left:.3rem solid #d29b42;background:#fff8e9}.plan-version-detail [role=alert]{color:#a21d25}</style>
