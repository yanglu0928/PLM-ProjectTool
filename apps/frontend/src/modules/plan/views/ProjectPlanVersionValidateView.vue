<script setup lang="ts">
import { inject, onUnmounted, ref, toRaw, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { sessionClientKey } from "@/modules/auth/api/sessionContext";
import { PlanVersionReadClient, type PlanVersionDetail } from "@/modules/plan/api/planVersionReadClient";
import { PlanVersionWriteClient, PlanVersionWriteError, type PlanVersionValidation } from "@/modules/plan/api/planVersionWriteClient";

const props = defineProps<{ session?: SessionClient; reader?: PlanVersionReadClient; validator?: PlanVersionWriteClient }>();
const session = toRaw(props.session ?? inject(sessionClientKey, null) ?? new SessionClient());
const reader = toRaw(props.reader ?? new PlanVersionReadClient());
const validator = toRaw(props.validator ?? new PlanVersionWriteClient(session));
const route = useRoute();
const current = ref<PlanVersionDetail | null>(null); const report = ref<PlanVersionValidation | null>(null);
const busy = ref(false); const loading = ref(false); const error = ref(""); const locked = ref(false);
let generation = 0; let mounted = true;
type Attempt = { project: string; plan: string; version: string; actor: string; key: string };
const projectId = () => typeof route.params.projectId === "string" ? route.params.projectId : "";
const planId = () => typeof route.params.planId === "string" ? route.params.planId : "";
const versionId = () => typeof route.params.versionId === "string" ? route.params.versionId : "";
const storageKey = () => `plm:plan-version-validate:${projectId()}:${planId()}:${versionId()}`;
function authorized() { return mounted && !!session.view && !session.view.password_change_required
  && session.view.authorized_projects.some(item => item.project_id === projectId()
    && (item.role === "PROJECT_MANAGER" || item.role === "IMPLEMENTATION_MEMBER")); }
function readAttempt(): Attempt | null {
  try {
    const raw = window.sessionStorage.getItem(storageKey()); if (!raw) return null;
    const value: unknown = JSON.parse(raw);
    if (typeof value !== "object" || value === null || Array.isArray(value)) return null;
    const item = value as Record<string, unknown>;
    if (Object.keys(item).length !== 5 || item.project !== projectId() || item.plan !== planId()
      || item.version !== versionId() || typeof item.actor !== "string" || !item.actor
      || typeof item.key !== "string" || !/^[\x20-\x7e]{16,128}$/.test(item.key)) return null;
    return item as Attempt;
  } catch { return null; }
}
function coverageLabel(field: string) {
  const labels: Readonly<Record<string, string>> = {
    requirement_total: "需求总数", requirement_mapped: "已映射需求", requirement_excluded: "明确排除需求",
    requirement_uncovered: "未覆盖需求", solution_total: "方案项总数", solution_mapped: "已映射方案项",
    solution_excluded: "明确排除方案项", solution_uncovered: "未覆盖方案项",
  };
  return labels[field] ?? "覆盖项";
}
async function load() {
  const project = projectId(), plan = planId(), version = versionId(), run = ++generation;
  current.value = null; report.value = null; error.value = ""; locked.value = false; busy.value = false;
  if (!authorized()) { loading.value = false; return; }
  loading.value = true;
  try {
    const snapshot = await reader.detail(project, plan, version);
    if (!mounted || run !== generation || project !== projectId() || plan !== planId() || version !== versionId()) return;
    current.value = snapshot;
    const attempt = readAttempt(); if (attempt && attempt.actor !== session.view?.user.user_id) locked.value = true;
  } catch (failure) {
    if (mounted && run === generation) error.value = failure instanceof Error ? failure.message : "无法读取此计划固定版本。";
  } finally { if (mounted && run === generation) loading.value = false; }
}
async function validate() {
  if (!authorized() || !current.value || busy.value || locked.value) return;
  const project = projectId(), plan = planId(), version = versionId(), actor = session.view!.user.user_id, run = generation;
  let attempt = readAttempt();
  if (attempt && (attempt.project !== project || attempt.plan !== plan || attempt.version !== version || attempt.actor !== actor)) {
    locked.value = true; error.value = "原验证操作属于其他会话；请在原会话恢复，避免重复执行。"; return;
  }
  if (!attempt) {
    attempt = { project, plan, version, actor, key: crypto.randomUUID() };
    try { window.sessionStorage.setItem(storageKey(), JSON.stringify(attempt)); }
    catch { error.value = "无法安全保存验证操作号；本次未提交。"; return; }
  }
  busy.value = true; error.value = ""; report.value = null;
  try {
    const value = await validator.validate(project, plan, version, attempt.key);
    if (!mounted || run !== generation || project !== projectId() || plan !== planId() || version !== versionId()
      || actor !== session.view?.user.user_id) return;
    report.value = value; window.sessionStorage.removeItem(storageKey());
  } catch (failure) {
    if (!mounted || run !== generation || project !== projectId() || plan !== planId() || version !== versionId()) return;
    if (failure instanceof PlanVersionWriteError) {
      if (!failure.uncertain) { try { window.sessionStorage.removeItem(storageKey()); } catch { locked.value = true; } }
      error.value = failure.message;
    } else error.value = failure instanceof Error ? failure.message : "验证结果无法确认；请按原操作号重试。";
  } finally { if (mounted && run === generation) busy.value = false; }
}
watch(() => [route.params.projectId, route.params.planId, route.params.versionId], () => { void load(); }, { immediate: true });
watch(() => session.view?.user.user_id, () => { generation++; current.value = null; report.value = null; void load(); });
onUnmounted(() => { mounted = false; generation++; });
</script>

<template><section class="plan-version-validate" aria-labelledby="plan-version-validate-title" :aria-busy="loading || busy">
  <p class="section-kicker">项目实施</p><h1 id="plan-version-validate-title">核查计划固定版本</h1>
  <p class="warning">验证会记录检查结果与审计事件；结果仅反映本次固定快照及来源检查，不代表批准、客户确认或交付。此操作不会改变版本状态，也不会提交评审。</p>
  <p><RouterLink :to="{ name: 'project-plan-version-detail', params: { projectId: route.params.projectId, planId: route.params.planId, versionId: route.params.versionId } }">返回固定版本</RouterLink></p>
  <p v-if="!session.view" role="status">尚未读取当前身份，请先登录。</p>
  <p v-else-if="session.view.password_change_required" role="status">当前账户须先修改密码。</p>
  <p v-else-if="!authorized()" role="status">当前账户无权核查此项目计划版本。</p>
  <template v-else>
    <p v-if="loading" role="status">正在读取固定计划版本…</p><p v-if="error" role="alert">{{ error }}</p>
    <template v-if="current"><h2>版本 {{ current.version_no }} · {{ current.version_state }}</h2>
      <p>固定版本 ID：{{ current.plan_version_id }}</p>
      <button type="button" :disabled="busy || loading || locked" @click="validate">{{ busy ? "正在核查…" : "执行Validate" }}</button>
      <p v-if="locked" role="status">当前会话无法安全恢复此验证操作。</p>
    </template>
    <section v-if="report" class="report" aria-live="polite" aria-label="验证结果">
      <h2>{{ report.valid ? "验证通过" : "发现阻断问题" }}</h2>
      <p>检查时间：<time :datetime="report.checked_at">{{ new Date(report.checked_at).toLocaleString("zh-CN") }}</time></p>
      <h3>阻断问题（{{ report.blocking_issues.length }}）</h3><p v-if="!report.blocking_issues.length">无</p>
      <ul v-else><li v-for="issue in report.blocking_issues" :key="issue">{{ issue }}</li></ul>
      <h3>警告（{{ report.warnings.length }}）</h3><p v-if="!report.warnings.length">无</p>
      <ul v-else><li v-for="warning in report.warnings" :key="warning">{{ warning }}</li></ul>
      <h3>追溯覆盖统计</h3><dl><template v-for="(value, key) in report.coverage_summary" :key="key"><dt>{{ coverageLabel(String(key)) }}</dt><dd>{{ value }}</dd></template></dl>
      <p class="warning">验证结果不等于方案批准；如需复核，本页面可再次执行并生成新的检查记录。</p>
    </section>
  </template>
</section></template>

<style scoped>.plan-version-validate{max-width:56rem;margin:1rem auto;padding:1.5rem;background:#fff;border-radius:1rem}.warning{padding:.8rem 1rem;border-left:.3rem solid #d29b42;background:#fff8e9}.report{margin-top:1.5rem;padding:1rem;border:1px solid #8795a6;border-radius:.7rem;background:#f8fafc}.report dl{display:grid;grid-template-columns:minmax(12rem,1fr) 5rem;gap:.5rem}.report dd{margin:0}.plan-version-validate [role=alert]{color:#a21d25}</style>
