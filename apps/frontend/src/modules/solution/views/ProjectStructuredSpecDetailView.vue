<script setup lang="ts">
import { inject, onUnmounted, ref, toRaw, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { sessionClientKey } from "@/modules/auth/api/sessionContext";
import { StructuredSpecReadClient, type StructuredSpecDetail } from
  "@/modules/solution/api/structuredSpecReadClient";
import { StructuredSpecValidateClient, StructuredSpecValidateError,
  type StructuredSpecValidationReport, type StructuredSpecValidationStatus } from
  "@/modules/solution/api/structuredSpecValidateClient";
import { describeStructuredSpec, type SpecPresentation } from "./structuredSpecPresentation";

const props = defineProps<{ session?: SessionClient; reader?: StructuredSpecReadClient;
  validator?: StructuredSpecValidateClient }>();
const session = toRaw(props.session ?? inject(sessionClientKey, null) ?? new SessionClient());
const reader = toRaw(props.reader ?? new StructuredSpecReadClient());
const validator = toRaw(props.validator ?? new StructuredSpecValidateClient(session));
const route = useRoute();
const current = ref<StructuredSpecDetail | null>(null);
const presentation = ref<SpecPresentation | null>(null);
const busy = ref(false); const error = ref("");
const validating = ref(false); const validationError = ref("");
const validationReport = ref<StructuredSpecValidationReport | null>(null);
const confirmRetry = ref(false); const validationLocked = ref(false);
const pending = ref<{ actor: string; project: string; spec: string; key: string } | null>(null);
let mounted = true; let generation = 0;
const projectId = () => typeof route.params.projectId === "string" ? route.params.projectId : "";
const specId = () => typeof route.params.specId === "string" ? route.params.specId : "";
function mayRead() {
  return mounted && !!session.view && !session.view.password_change_required
    && session.view.authorized_projects.some(item => item.project_id === projectId());
}
function mayRevise() {
  return !!current.value && ["DRAFT", "RETURNED", "APPROVED"].includes(current.value.version_state)
    && !!session.view && !session.view.password_change_required && session.canSubmit
    && session.view.authorized_projects.some(item => item.project_id === projectId()
      && (item.role === "PROJECT_MANAGER" || item.role === "IMPLEMENTATION_MEMBER"));
}
function mayValidate() {
  return !!current.value && mayRead() && session.canSubmit
    && current.value.project_id === projectId()
    && current.value.structured_solution_spec_id === specId()
    && session.view!.authorized_projects.some(item => item.project_id === projectId()
      && (item.role === "PROJECT_MANAGER" || item.role === "IMPLEMENTATION_MEMBER"));
}
function storageKey() {
  return `plm.sol.structured-spec.validate.pending.${session.view?.user.user_id ?? "none"}`
    + `.${projectId()}.${specId()}`;
}
function restorePending() {
  pending.value = null; confirmRetry.value = false; validationLocked.value = false;
  validationReport.value = null; validationError.value = "";
  if (!mayRead()) return;
  const writer = session.view!.authorized_projects.some(item => item.project_id === projectId()
    && (item.role === "PROJECT_MANAGER" || item.role === "IMPLEMENTATION_MEMBER"));
  if (!writer) return;
  try {
    const raw = window.sessionStorage.getItem(storageKey()); if (!raw) return;
    const value: unknown = JSON.parse(raw);
    if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("invalid");
    const item = value as Record<string, unknown>;
    if (item.actor !== session.view!.user.user_id || item.project !== projectId()
      || item.spec !== specId() || typeof item.key !== "string"
      || !/^[\x20-\x7e]{16,128}$/.test(item.key)) throw new Error("invalid");
    pending.value = { actor: item.actor as string, project: item.project as string,
      spec: item.spec as string, key: item.key as string };
  } catch {
    validationLocked.value = true;
    validationError.value = "原验证操作记录无法读取，已停止再次提交；请核对审计记录。";
  }
}
function stateLabel(value: string) {
  const labels: Record<string, string> = { DRAFT: "待评审草案", IN_REVIEW: "评审中",
    APPROVED: "已批准", RETURNED: "已退回", SUPERSEDED: "已被后续版本替代",
    RESTRICTED: "受限" };
  return labels[value] ?? "状态未知";
}
async function load() {
  if (!mayRead() || busy.value) return;
  const project = projectId(), spec = specId(), run = ++generation;
  busy.value = true; error.value = ""; current.value = null; presentation.value = null;
  validationReport.value = null;
  try {
    const result = await reader.detail(project, spec);
    if (!mounted || run !== generation || project !== projectId() || spec !== specId()) return;
    const readable = describeStructuredSpec(result);
    current.value = result; presentation.value = readable;
  } catch (failure) {
    if (mounted && run === generation) error.value = failure instanceof Error
      ? failure.message : "暂时无法读取专项版本。";
  } finally { if (mounted && run === generation) busy.value = false; }
}
watch(() => [route.name, route.params.projectId, route.params.specId], () => {
  generation += 1; current.value = null; presentation.value = null;
  busy.value = false; validating.value = false; error.value = ""; restorePending();
  if (route.name === "project-structured-spec-detail") void load();
}, { immediate: true });
onUnmounted(() => { mounted = false; generation += 1; });
async function validateCurrent() {
  if (!mayValidate() || busy.value || validating.value || validationLocked.value
    || pending.value && !confirmRetry.value) return;
  const actor = session.view!.user.user_id, project = projectId(), spec = specId();
  const run = generation; let attempt = pending.value;
  if (!attempt) {
    attempt = { actor, project, spec, key: `structured-spec-validate-${crypto.randomUUID()}` };
    try { window.sessionStorage.setItem(storageKey(), JSON.stringify(attempt)); }
    catch { validationError.value = "无法保存原操作号，本次未发送验证。"; return; }
    pending.value = attempt;
  }
  if (attempt.actor !== actor || attempt.project !== project || attempt.spec !== spec) {
    validationLocked.value = true; return;
  }
  validating.value = true; confirmRetry.value = false; validationError.value = "";
  validationReport.value = null;
  try {
    const report = await validator.validate(project, spec, attempt.key);
    if (!mounted || run !== generation || actor !== session.view?.user.user_id) return;
    const detail = current.value;
    if (!detail || report.spec_series_id !== detail.spec_series_id
      || report.spec_type !== detail.spec_type || report.version_no !== detail.version_no
      || report.version_state !== detail.version_state
      || report.content_fingerprint !== detail.content_fingerprint
      || report.payload_fingerprint !== detail.payload_fingerprint
      || report.requirement_count !== detail.requirement_refs.length
      || report.section_count !== detail.section_refs.length
      || report.evidence_count !== detail.evidence_ids.length
      || report.artifact_count !== detail.artifact_ids.length) {
      validationLocked.value = true;
      validationError.value = "验证报告与固定专项版本不一致，已停止提交；请核对版本与审计记录。";
      return;
    }
    validationReport.value = report;
    try { window.sessionStorage.removeItem(storageKey()); pending.value = null; }
    catch { validationLocked.value = true; validationError.value = "报告已生成，但原操作号清理失败；请勿再次提交。"; }
  } catch (failure) {
    if (!mounted || run !== generation) return;
    if (failure instanceof StructuredSpecValidateError && failure.code === "CONFLICT_IDEMPOTENCY") validationLocked.value = true;
    validationError.value = failure instanceof Error ? failure.message : "验证结果无法确认，请保留原操作号。";
  } finally { if (mounted && run === generation) validating.value = false; }
}
const dimensions = [{field:"integrity",label:"固定版本完整性"},{field:"payload",label:"类型化内容结构"},
  {field:"requirements",label:"需求来源"},{field:"sections",label:"章节来源"},{field:"evidence",label:"证据来源"},
  {field:"artifacts",label:"输出附件"},{field:"trace",label:"追溯覆盖"},{field:"current_version",label:"系列当前版本"}] as const;
function statusLabel(value: StructuredSpecValidationStatus) { return value === "PASS" ? "通过" : value === "FAIL" ? "未通过" : "暂无法核验"; }
function factHint(field: typeof dimensions[number]["field"]) { return ({integrity:"固定来源摘要已变化；请基于当前来源创建修订版。",payload:"类型化正文结构不完整；请修订专项内容。",requirements:"请核对引用需求是否仍为当前批准版本。",sections:"请核对章节及正文版本是否仍有效。",evidence:"请核对项目证据资格与关联文件。",artifacts:"当前附件来源尚不能核验。",trace:"当前缺少专项到需求/章节的可信追溯覆盖。",current_version:"该版本不是系列最新版本；请查看后续版本。"})[field]; }
</script>

<template>
  <section class="spec-detail" aria-labelledby="spec-detail-title" :aria-busy="busy">
    <p class="section-kicker">项目方案 · 固定历史</p>
    <h1 id="spec-detail-title">结构化专项详情</h1>
    <p><RouterLink :to="{ name: 'project-structured-specs', params: { projectId: route.params.projectId } }">返回专项版本历史</RouterLink></p>
    <p v-if="!mayRead()" role="status">当前会话没有此项目的读取权限。</p>
    <template v-else>
      <button type="button" :disabled="busy" @click="load()">{{ busy ? "正在读取…" : "刷新详情" }}</button>
      <p v-if="error" role="alert">{{ error }}</p>
      <p v-else-if="busy" role="status">正在读取固定专项版本…</p>
      <template v-else-if="current && presentation">
        <p class="warning" role="status">{{ stateLabel(current.version_state) }}。固定历史引用不证明需求、章节或证据目前仍合格；只有实际完成评审的版本才可作为正式结论。</p>
        <p v-if="mayRevise()"><RouterLink :to="{ name: 'project-structured-spec-revise', params: {
          projectId: current.project_id, specId: current.structured_solution_spec_id } }">基于此版本创建修订草案</RouterLink></p>
        <h2>{{ presentation.title }} · 版本 {{ current.version_no }}</h2>
        <dl class="facts"><dt>系列编号</dt><dd>{{ current.spec_series_id }}</dd>
          <dt>版本编号</dt><dd>{{ current.structured_solution_spec_id }}</dd>
          <dt>创建时间</dt><dd>{{ current.created_at }}</dd>
          <dt>内容指纹</dt><dd>{{ current.content_fingerprint }}</dd></dl>
        <section aria-labelledby="spec-fields-title" v-if="presentation.fields.length">
          <h3 id="spec-fields-title">设计内容</h3>
          <dl class="facts"><template v-for="item in presentation.fields" :key="item.label">
            <dt>{{ item.label }}</dt><dd>{{ item.value }}</dd></template></dl>
        </section>
        <section v-for="list in presentation.lists" :key="list.label">
          <h3>{{ list.label }}</h3><p v-if="!list.items.length">无</p>
          <ul v-else><li v-for="(item, index) in list.items" :key="index">{{ item }}</li></ul>
        </section>
        <section v-for="table in presentation.tables" :key="table.label">
          <h3>{{ table.label }}</h3><p v-if="!table.rows.length">无</p>
          <div v-else class="table-scroll"><table><thead><tr><th v-for="heading in table.headings" :key="heading" scope="col">{{ heading }}</th></tr></thead>
            <tbody><tr v-for="(row, index) in table.rows" :key="index"><td v-for="(cell, cellIndex) in row" :key="cellIndex">{{ cell }}</td></tr></tbody></table></div>
        </section>
        <section aria-labelledby="spec-refs-title"><h3 id="spec-refs-title">固定来源引用</h3>
          <h4>需求版本（{{ current.requirement_refs.length }}）</h4>
          <ul><li v-for="item in current.requirement_refs" :key="item.requirement_version_id">
            <RouterLink :to="{ name: 'project-requirement-detail', params: {
              projectId: current.project_id, requirementId: item.requirement_id } }">查看需求</RouterLink>
            · 固定版本 {{ item.requirement_version_id }}</li></ul>
          <h4>章节版本（{{ current.section_refs.length }}）</h4>
          <ul><li v-for="item in current.section_refs" :key="item.solution_section_version_id">
            <RouterLink :to="{ name: 'project-section-version-detail', params: {
              projectId: current.project_id, sectionId: item.solution_section_id,
              versionId: item.solution_section_version_id } }">查看固定章节</RouterLink></li></ul>
          <h4>项目证据（{{ current.evidence_ids.length }}）</h4>
          <p v-if="!current.evidence_ids.length">无</p>
          <ul v-else><li v-for="item in current.evidence_ids" :key="item">{{ item }}</li></ul>
          <p><RouterLink :to="{ name: 'project-evidence', params: { projectId: current.project_id } }">查看项目证据列表</RouterLink></p>
        </section>
        <section aria-labelledby="spec-validation-title">
          <h3 id="spec-validation-title">当前事实验证</h3>
          <p class="warning">验证会保存一次审计观察，不会批准专项、不会创建评审，也不代表客户确认。新操作号会重新观察当前来源。</p>
          <p v-if="!mayValidate()" role="status">仅当前项目负责人或实施成员可验证；请确认会话与项目权限。</p>
          <template v-else><p v-if="pending" role="status">存在结果未知的原验证操作；请核对审计并保持原操作号。</p>
            <label v-if="pending"><input v-model="confirmRetry" type="checkbox" :disabled="validating || validationLocked"> 我已核对并确认按原操作号重试</label>
            <p v-if="validationError" role="alert">{{ validationError }}</p>
            <button type="button" :disabled="busy || validating || validationLocked || !!pending && !confirmRetry" @click="validateCurrent()">{{ validating ? "正在验证…" : pending ? "按原操作号重试验证" : "验证当前事实" }}</button></template>
          <div v-if="validationReport" class="validation-report" role="status"><h4>验证报告 · {{ validationReport.valid ? "固定内容与主要来源核验通过" : "固定内容或来源存在问题" }}</h4>
            <p>{{ validationReport.ready_for_review ? "当前检查满足送审前置；仍需正式评审与客户确认。" : "尚不具备送审条件；不得视为已批准。" }}</p>
            <p>观察时间：{{ validationReport.observed_at }} · 审计：<code>{{ validationReport.audit_event_id }}</code></p>
            <ul><li v-for="item in dimensions" :key="item.field">{{ item.label }}：{{ statusLabel(validationReport.facts[item.field]) }}<span v-if="validationReport.facts[item.field] !== 'PASS'"> — {{ factHint(item.field) }}</span></li></ul>
            <h4>专项类型检查</h4><ul><li v-for="check in validationReport.type_checks" :key="check.code"><code>{{ check.code }}</code>：{{ statusLabel(check.status) }}<span v-if="check.status !== 'PASS'"> — 请补充该项业务证明或维护信息。</span></li></ul>
            <p v-if="validationReport.issue_codes.length">问题代码：{{ validationReport.issue_codes.join("、") }}</p>
          </div>
        </section>
        <p v-if="current.review_ref">评审编号：{{ current.review_ref }}；轮次编号：{{ current.review_round_ref }}</p>
        <p v-else>尚无评审记录；本页不提供提交评审操作。</p>
      </template>
    </template>
  </section>
</template>

<style scoped>
.spec-detail{max-width:64rem;margin:1rem auto;padding:1.5rem;background:#fff;border-radius:1rem}
.spec-detail section{margin-block:1.5rem}.spec-detail .facts{display:grid;grid-template-columns:minmax(8rem,12rem) 1fr;gap:.5rem 1rem}
.spec-detail dt{font-weight:650}.spec-detail dd{margin:0;overflow-wrap:anywhere;white-space:pre-wrap}
.spec-detail .warning{padding:.8rem 1rem;border-left:.3rem solid #d29b42;background:#fff8e9}
.spec-detail .table-scroll{overflow-x:auto}.spec-detail table{border-collapse:collapse;width:100%}
.spec-detail th,.spec-detail td{border:1px solid #aaa;padding:.5rem;text-align:left;vertical-align:top}
.validation-report{margin-top:1rem;padding:1rem;border:1px solid #94a3b8;border-radius:.5rem;overflow-wrap:anywhere}
.spec-detail [role=alert]{color:#a21d25}
</style>
