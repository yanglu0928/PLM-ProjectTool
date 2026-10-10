<script setup lang="ts">
import { inject, onUnmounted, ref, toRaw, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";

import { SessionClient } from "@/modules/auth/api/sessionClient";
import { sessionClientKey } from "@/modules/auth/api/sessionContext";
import { EvidenceViewerClient, EvidenceViewerClientError, type EvidenceViewerDescriptor } from "@/modules/evidence/api/evidenceViewerClient";
import { RequirementReadClient, RequirementReadError, type RequirementSourceView,
  type RequirementVersionCursor, type RequirementVersionSummary, type RequirementVersionView,
  type RequirementView } from "@/modules/requirement/api/requirementReadClient";

const props = defineProps<{ session?: SessionClient; requirements?: RequirementReadClient; evidence?: EvidenceViewerClient }>();
const session = toRaw(props.session ?? inject(sessionClientKey, null) ?? new SessionClient());
const requirements = toRaw(props.requirements ?? new RequirementReadClient());
const evidence = toRaw(props.evidence ?? new EvidenceViewerClient());
const identity = session.view; const route = useRoute();
const requirement = ref<RequirementView | null>(null); const versions = ref<readonly RequirementVersionSummary[]>([]);
const versionCursor = ref<RequirementVersionCursor | null>(null); const selected = ref<RequirementVersionView | null>(null);
const selectedEvidence = ref<EvidenceViewerDescriptor | null>(null); const selectedEvidenceId = ref("");
const busy = ref(false); const versionBusy = ref(false); const detailBusy = ref(false); const evidenceBusy = ref(false);
const error = ref(""); const versionError = ref(""); const detailError = ref(""); const evidenceError = ref("");
let generation = 0; let detailGeneration = 0; let evidenceGeneration = 0; let mounted = true;
const stateLabels = Object.freeze({ DRAFT: "草稿", IN_REVIEW: "评审中", APPROVED: "已批准", RETURNED: "已退回",
  SUPERSEDED: "已被替代", RESTRICTED: "受限" });
const classLabels = Object.freeze({ STANDARD_FUNCTION: "标准功能", NONSTANDARD_FUNCTION: "非标功能",
  DIFFERENCE: "差异项", PENDING_CONFIRMATION: "待确认项" });
const sourceLabels = Object.freeze({ APPROVED_SURVEY_CONCLUSION: "已批准调研结论", CONFIRMED_HANDOVER: "已确认交接项",
  HUMAN_DECISION: "人工决策", PROJECT_EVIDENCE: "项目证据" });

function ids() { return { projectId: typeof route.params.projectId === "string" ? route.params.projectId : "",
  requirementId: typeof route.params.requirementId === "string" ? route.params.requirementId : "" }; }
function mayRead() { return mounted && !!identity && !identity.password_change_required
  && session.view?.user.user_id === identity.user.user_id; }
function clearEvidence() { evidenceGeneration += 1; selectedEvidence.value = null; selectedEvidenceId.value = "";
  evidenceError.value = ""; evidenceBusy.value = false; }
function clearSelection() { detailGeneration += 1; selected.value = null; detailError.value = ""; detailBusy.value = false; clearEvidence(); }
async function load() {
  if (!mayRead() || busy.value) return; const request = ids(); const current = ++generation;
  requirement.value = null; versions.value = []; versionCursor.value = null; clearSelection(); error.value = ""; versionError.value = ""; busy.value = true;
  try {
    const [root, page] = await Promise.all([requirements.getRequirement(request.projectId, request.requirementId),
      requirements.listVersions(request.projectId, request.requirementId)]);
    const latest = ids(); if (!mounted || current !== generation || latest.projectId !== request.projectId
      || latest.requirementId !== request.requirementId || !mayRead()) return;
    requirement.value = root; versions.value = page.items; versionCursor.value = page.next_cursor;
  } catch (failure) {
    const latest = ids(); if (!mounted || current !== generation || latest.projectId !== request.projectId
      || latest.requirementId !== request.requirementId) return;
    error.value = failure instanceof RequirementReadError ? failure.message : "暂时无法读取需求。";
  } finally { if (mounted && current === generation) busy.value = false; }
}
async function loadMoreVersions() {
  if (!mayRead() || versionBusy.value || !versionCursor.value) return;
  const request = ids(); const next = versionCursor.value; const current = ++generation; versionBusy.value = true; versionError.value = "";
  try {
    const page = await requirements.listVersions(request.projectId, request.requirementId, 50, next);
    if (!mounted || current !== generation || ids().projectId !== request.projectId || ids().requirementId !== request.requirementId || !mayRead()) return;
    const known = new Set(versions.value.map(item => item.requirement_version_id));
    if (page.items.some(item => known.has(item.requirement_version_id))) throw new RequirementReadError("REQUIREMENT_READ_UNAVAILABLE");
    versions.value = Object.freeze([...versions.value, ...page.items]); versionCursor.value = page.next_cursor;
  } catch (failure) {
    if (mounted && current === generation) { versions.value = []; versionCursor.value = null; clearSelection();
      versionError.value = failure instanceof RequirementReadError ? failure.message : "暂时无法读取需求版本。"; }
  } finally { if (mounted && current === generation) versionBusy.value = false; }
}
async function choose(summary: RequirementVersionSummary) {
  if (!mayRead() || detailBusy.value) return; const request = ids(); const current = ++detailGeneration;
  selected.value = null; detailError.value = ""; detailBusy.value = true; clearEvidence();
  try {
    const detail = await requirements.getVersion(request.projectId, request.requirementId, summary.requirement_version_id);
    if (!mounted || current !== detailGeneration || ids().projectId !== request.projectId
      || ids().requirementId !== request.requirementId || !mayRead()) return; selected.value = detail;
  } catch (failure) { if (mounted && current === detailGeneration) detailError.value = failure instanceof RequirementReadError
    ? failure.message : "暂时无法读取固定需求版本。";
  } finally { if (mounted && current === detailGeneration) detailBusy.value = false; }
}
async function locateEvidence(evidenceId: string) {
  if (!mayRead() || evidenceBusy.value || !selected.value) return;
  const versionId = selected.value.requirement_version_id; const request = ids(); const current = ++evidenceGeneration;
  selectedEvidence.value = null; selectedEvidenceId.value = evidenceId; evidenceError.value = ""; evidenceBusy.value = true;
  try {
    const result = await evidence.get({ kind: "PROJECT", projectId: request.projectId }, evidenceId);
    if (!mounted || current !== evidenceGeneration || selected.value?.requirement_version_id !== versionId
      || ids().projectId !== request.projectId || ids().requirementId !== request.requirementId || !mayRead()) return;
    selectedEvidence.value = result;
  } catch (failure) { if (mounted && current === evidenceGeneration) evidenceError.value = failure instanceof EvidenceViewerClientError
    ? failure.message : "暂时无法定位原文。";
  } finally { if (mounted && current === evidenceGeneration) evidenceBusy.value = false; }
}
function businessLink(source: RequirementSourceView) {
  if (source.source_type === "CONFIRMED_HANDOVER") return { name: "project-handover-detail", params: { projectId: ids().projectId,
    analysisId: source.source_object_id }, query: { version: source.source_version_ref ?? undefined } };
  if (source.source_type === "APPROVED_SURVEY_CONCLUSION") return { name: "project-survey-conclusions",
    params: { projectId: ids().projectId }, query: { conclusionId: source.source_object_id } };
  return null;
}
watch(() => [route.params.projectId, route.params.requirementId], () => {
  generation += 1; clearSelection(); busy.value = false; void load();
}, { immediate: true });
onUnmounted(() => { mounted = false; generation += 1; detailGeneration += 1; evidenceGeneration += 1; });
</script>

<template>
  <section class="requirement-detail" aria-labelledby="requirement-detail-title" :aria-busy="busy">
    <p class="section-kicker">项目需求</p><h1 id="requirement-detail-title">需求版本、待维护内容与原文定位</h1>
    <p class="fact-warning"><strong>AI 任务仅是建议，来源摘要不是权威正文。</strong>证据仅在明确点击后按当前权限定位。</p>
    <p><RouterLink :to="{ name: 'project-requirements', params: { projectId: route.params.projectId } }">返回需求列表</RouterLink></p>
    <p><RouterLink :to="{ name: 'project-requirement-draft', params: { projectId: route.params.projectId,
      requirementId: route.params.requirementId } }">创建结构化需求版本草稿</RouterLink></p>
    <template v-if="!identity"><p role="status">尚未读取当前身份。请先登录。</p></template>
    <template v-else-if="identity.password_change_required"><p role="status">当前账户须先修改密码，暂不能读取项目需求。</p></template>
    <template v-else>
      <button type="button" :disabled="busy" @click="load()">{{ busy ? "正在读取…" : "刷新需求与版本" }}</button>
      <p v-if="error" role="alert">{{ error }}</p>
      <dl v-if="requirement"><dt>需求编号</dt><dd>{{ requirement.requirement_code }}</dd><dt>状态</dt><dd>{{ requirement.state }}</dd>
        <dt>当前批准版本</dt><dd>{{ requirement.current_approved_version_ref ? "已形成" : "尚未形成" }}</dd><dt>版本标记</dt><dd>{{ requirement.etag }}</dd></dl>
      <section v-if="requirement" aria-labelledby="versions-title"><h2 id="versions-title">固定版本</h2>
        <p v-if="!versions.length">暂无可见版本。</p><p v-if="versionError" role="alert">{{ versionError }}</p>
        <ol class="cards"><li v-for="version in versions" :key="version.requirement_version_id">
          <strong>版本 {{ version.version_no }}{{ version.title ? ` · ${version.title}` : "" }}</strong>
          <span>{{ stateLabels[version.state] }} · {{ classLabels[version.classification] }} · {{ version.domain_name }}</span>
          <span>优先级 {{ version.priority }} · 风险 {{ version.risk }}</span>
          <button type="button" :disabled="detailBusy" @click="choose(version)">查看版本 {{ version.version_no }} 的详情与原文入口</button>
        </li></ol>
        <button v-if="versionCursor" type="button" :disabled="versionBusy" @click="loadMoreVersions">加载更多版本</button>
        <p v-if="detailError" role="alert">{{ detailError }}</p>
      </section>
      <article v-if="selected" aria-labelledby="selected-title"><h2 id="selected-title">版本 {{ selected.version_no }} · {{ selected.title ?? selected.domain_name }}</h2>
        <p v-if="selected.classification === 'PENDING_CONFIRMATION'" class="fact-warning"><strong>该版本属于待确认项。</strong>确认完成前不得作为正式业务事实或提交正式评审。</p>
        <h3>需求陈述</h3><p>{{ selected.statement }}</p><h3>理由</h3><p>{{ selected.rationale }}</p>
        <section><h3>来源与原文入口</h3><p>页面仅显示固定标识；不会把来源正文复制进表格。</p>
          <ol class="cards"><li v-for="source in selected.sources" :key="source.ordinal">
            <strong>{{ sourceLabels[source.source_type] }}</strong><span>来源标识：{{ source.source_object_id }}</span>
            <span v-if="source.source_version_ref">固定版本：{{ source.source_version_ref }}</span>
            <RouterLink v-if="businessLink(source)" :to="businessLink(source)!">打开对应业务记录</RouterLink>
            <span v-else-if="source.source_type === 'HUMAN_DECISION'">人工决策没有独立正文页，请通过下列固定证据核验。</span>
            <button v-for="entry in source.evidence_refs" :key="entry.evidence_id" type="button"
              :disabled="evidenceBusy" @click="locateEvidence(entry.evidence_id)">定位该来源的原文证据</button>
          </li></ol>
        </section>
        <section><h3>验收标准：需要维护什么</h3><ol class="cards"><li v-for="item in selected.acceptance_criteria" :key="item.ordinal">
          <span><strong>可观察结果：</strong>{{ item.observable_result }}</span><span><strong>验证方法：</strong>{{ item.verification_method }}</span>
          <span><strong>所需数据：</strong>{{ item.required_data }}</span><span><strong>所需环境：</strong>{{ item.required_environment }}</span>
          <span><strong>证据要求：</strong>{{ item.evidence_requirement }}</span></li></ol></section>
        <section><h3>标准能力匹配：需要人工确认</h3><ol class="cards"><li v-for="item in selected.capability_assessments" :key="item.ordinal">
          <span>匹配结论：{{ item.match_type }} · {{ item.confirmation_state }}</span><span><strong>Fit/Gap：</strong>{{ item.fit_gap }}</span>
          <span><strong>约束：</strong>{{ item.constraints_text }}</span><span>评估方式：{{ item.assessor_kind }}</span>
          <button v-for="entry in item.evidence_refs" :key="entry.evidence_id" type="button" :disabled="evidenceBusy"
            @click="locateEvidence(entry.evidence_id)">定位能力评估证据（{{ entry.evidence_role }}）</button></li></ol></section>
        <div class="columns"><section><h3>假设</h3><ol><li v-for="item in selected.assumptions" :key="item.ordinal">{{ item.text }}</li></ol></section>
          <section><h3>排除项</h3><ol><li v-for="item in selected.exclusions" :key="item.ordinal">{{ item.text }}</li></ol></section>
          <section><h3>依赖</h3><ol><li v-for="item in selected.dependencies" :key="item.ordinal">{{ item.text }}</li></ol></section></div>
        <section><h3>AI 建议任务</h3><p>以下任务仅用于辅助分析，必须经人工确认后才能成为业务事实。</p>
          <ul><li v-for="item in selected.ai_tasks" :key="item.ai_task_id">任务 {{ item.ai_task_id }}</li></ul></section>
      </article>
      <aside v-if="selectedEvidence || evidenceError" class="viewer" aria-live="polite"><h2>原文定位结果</h2>
        <p v-if="evidenceError" role="alert">{{ evidenceError }}</p><template v-if="selectedEvidence && selectedEvidence.evidence_id === selectedEvidenceId">
          <strong>{{ selectedEvidence.display_label }}</strong><p v-if="selectedEvidence.short_preview">{{ selectedEvidence.short_preview }}（仅为定位预览，不是权威正文）</p>
          <a :href="selectedEvidence.content_url" target="_blank" rel="noopener">打开经授权的固定版本原文</a></template></aside>
    </template>
  </section>
</template>

<style scoped>
.requirement-detail { max-width: 68rem; margin: 1rem auto; padding: 1.5rem; background: #fff; border-radius: 1rem; }
.requirement-detail p,.requirement-detail li { line-height: 1.65; }.requirement-detail dl { display: grid; grid-template-columns: 10rem 1fr; }
.requirement-detail dd { overflow-wrap: anywhere; }.cards { display: grid; gap: .75rem; padding: 0; list-style: none; }
.cards li { display: grid; gap: .35rem; padding: .9rem; border: 1px solid #d8dee7; border-radius: .7rem; overflow-wrap: anywhere; }
.fact-warning { padding: .8rem 1rem; border-left: .3rem solid #d29b42; background: #fff8e9; }
.columns { display: grid; grid-template-columns: repeat(auto-fit,minmax(13rem,1fr)); gap: 1rem; }.viewer { margin-top: 1rem; padding: 1rem; background: #eef6ff; }
.requirement-detail [role="alert"] { color: #a21d25; }
</style>
