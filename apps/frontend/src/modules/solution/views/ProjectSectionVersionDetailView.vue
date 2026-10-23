<script setup lang="ts">
import { inject, onUnmounted, ref, toRaw, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { sessionClientKey } from "@/modules/auth/api/sessionContext";
import { SectionVersionReadClient, type SectionVersionDetail } from
  "@/modules/solution/api/sectionVersionReadClient";
import { SectionVersionValidateClient, SectionVersionValidateError,
  type SectionVersionValidationReport, type ValidationStatus } from
  "@/modules/solution/api/sectionVersionValidateClient";
import SectionReviewSubmitPanel from "./SectionReviewSubmitPanel.vue";

const props = defineProps<{ session?: SessionClient; reader?: SectionVersionReadClient;
  validator?: SectionVersionValidateClient }>();
const session = toRaw(props.session ?? inject(sessionClientKey, null) ?? new SessionClient());
const reader = toRaw(props.reader ?? new SectionVersionReadClient());
const validator = toRaw(props.validator ?? new SectionVersionValidateClient(session));
const route = useRoute();
const current = ref<SectionVersionDetail | null>(null);
const busy = ref(false); const error = ref("");
const validating = ref(false); const validationError = ref("");
const validationReport = ref<SectionVersionValidationReport | null>(null);
const confirmRetry = ref(false); const validationLocked = ref(false);
const pending = ref<{ actor: string; project: string; section: string; version: string; key: string } | null>(null);
let generation = 0; let mounted = true;
const projectId = () => typeof route.params.projectId === "string" ? route.params.projectId : "";
const sectionId = () => typeof route.params.sectionId === "string" ? route.params.sectionId : "";
const versionId = () => typeof route.params.versionId === "string" ? route.params.versionId : "";
function mayRead() {
  return mounted && !!session.view && !session.view.password_change_required
    && session.view.authorized_projects.some(item => item.project_id === projectId());
}
function mayValidate() {
  return mayRead() && session.canSubmit && !!current.value
    && current.value.project_id === projectId()
    && current.value.solution_section_id === sectionId()
    && current.value.solution_section_version_id === versionId()
    && session.view!.authorized_projects.some(item => item.project_id === projectId()
      && (item.role === "PROJECT_MANAGER" || item.role === "IMPLEMENTATION_MEMBER"));
}
function storageKey() {
  return `plm.sol.section.version.validate.pending.${session.view?.user.user_id ?? "none"}`
    + `.${projectId()}.${sectionId()}.${versionId()}`;
}
function restorePending() {
  pending.value = null; confirmRetry.value = false; validationLocked.value = false;
  validationReport.value = null; validationError.value = "";
  if (!mayRead() || !session.view?.authorized_projects.some(item => item.project_id === projectId()
    && (item.role === "PROJECT_MANAGER" || item.role === "IMPLEMENTATION_MEMBER"))) return;
  try {
    const raw = window.sessionStorage.getItem(storageKey());
    if (!raw) return;
    const value: unknown = JSON.parse(raw);
    if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("invalid");
    const item = value as Record<string, unknown>;
    if (item.actor !== session.view.user.user_id || item.project !== projectId()
      || item.section !== sectionId() || item.version !== versionId()
      || typeof item.key !== "string" || !/^[\x20-\x7e]{16,128}$/.test(item.key)) {
      throw new Error("invalid");
    }
    pending.value = { actor: item.actor as string, project: item.project as string,
      section: item.section as string, version: item.version as string, key: item.key as string };
  } catch {
    validationLocked.value = true;
    validationError.value = "原验证操作记录无法读取，已停止再次提交；请核对审计记录。";
  }
}
async function load() {
  if (!mayRead() || busy.value || validating.value) return;
  const project = projectId(), section = sectionId(), version = versionId(), run = ++generation;
  busy.value = true; error.value = ""; current.value = null; validationReport.value = null;
  try {
    const result = await reader.detail(project, section, version);
    if (!mounted || run !== generation || project !== projectId()
      || section !== sectionId() || version !== versionId()) return;
    current.value = result;
  } catch (failure) {
    if (mounted && run === generation) error.value = failure instanceof Error
      ? failure.message : "暂时无法读取章节版本。";
  } finally { if (mounted && run === generation) busy.value = false; }
}
watch(() => [route.params.projectId, route.params.sectionId, route.params.versionId], () => {
  generation += 1; current.value = null; busy.value = false; validating.value = false;
  error.value = ""; restorePending(); void load();
}, { immediate: true });
onUnmounted(() => { mounted = false; generation += 1; });
async function validate() {
  if (!mayValidate() || busy.value || validating.value || validationLocked.value
    || pending.value && !confirmRetry.value) return;
  const actor = session.view!.user.user_id;
  const project = projectId(), section = sectionId(), version = versionId(), run = generation;
  let attempt = pending.value;
  if (!attempt) {
    attempt = { actor, project, section, version, key: crypto.randomUUID() };
    try { window.sessionStorage.setItem(storageKey(), JSON.stringify(attempt)); }
    catch { validationError.value = "无法保存原操作号，本次未发送验证。"; return; }
    pending.value = attempt;
  }
  if (attempt.actor !== actor || attempt.project !== project
    || attempt.section !== section || attempt.version !== version) {
    validationLocked.value = true; return;
  }
  validating.value = true; confirmRetry.value = false;
  validationError.value = ""; validationReport.value = null;
  try {
    const result = await validator.validate(project, section, version, attempt.key);
    if (!mounted || run !== generation || actor !== session.view?.user.user_id) return;
    if (!current.value || result.version_no !== current.value.version_no
      || result.version_state !== current.value.version_state
      || result.content_fingerprint !== current.value.content_fingerprint
      || result.requirement_count !== current.value.declared_requirement_count
      || result.evidence_count !== current.value.declared_evidence_count) {
      validationLocked.value = true;
      validationError.value = "验证报告与固定版本不一致，已停止提交；请核对版本与审计记录。";
      return;
    }
    validationReport.value = result;
    try { window.sessionStorage.removeItem(storageKey()); pending.value = null; }
    catch {
      validationLocked.value = true;
      validationError.value = "报告已生成，但原操作号清理失败；请勿再次提交。";
    }
  } catch (failure) {
    if (!mounted || run !== generation) return;
    if (failure instanceof SectionVersionValidateError && failure.code === "CONFLICT_IDEMPOTENCY") {
      validationLocked.value = true;
    }
    validationError.value = failure instanceof Error ? failure.message
      : "验证结果无法确认，请保留原操作号。";
  } finally { if (mounted && run === generation) validating.value = false; }
}
const dimensions = [
  { field: "integrity", label: "固定版本完整性" },
  { field: "content", label: "正文来源" },
  { field: "requirements", label: "需求来源" },
  { field: "evidence", label: "证据来源" },
  { field: "trace", label: "追溯覆盖" },
  { field: "spec", label: "结构化规格" },
] as const;
function statusLabel(status: ValidationStatus): string {
  return status === "PASS" ? "通过" : status === "FAIL" ? "未通过" : "暂无法核验";
}
function dimensionHint(field: typeof dimensions[number]["field"], status: ValidationStatus): string {
  if (status === "PASS") return "";
  return {
    integrity: "请核对固定版本及历史记录完整性。",
    content: "请核对正文文档版本、文件可用性与访问权限。",
    requirements: "请核对所引用需求版本是否仍为当前已批准版本。",
    evidence: "请核对项目证据资格与关联文件。",
    trace: "当前尚无可信的章节追溯覆盖核对；需后续功能补齐。",
    spec: "当前尚无可信的结构化规格核对；需后续功能补齐。",
  }[field];
}
</script>

<template>
  <section class="section-version-detail" aria-labelledby="section-version-detail-title" :aria-busy="busy || validating">
    <p class="section-kicker">项目方案</p><h1 id="section-version-detail-title">章节固定版本详情</h1>
    <p class="warning">本页仅展示历史固定引用；Document、Requirement 和 Evidence 当前可用性需另行核查，评审及客户确认也不能由本页推定。</p>
    <p><RouterLink :to="{ name: 'project-section-versions', params: { projectId: route.params.projectId,
      sectionId: route.params.sectionId } }">返回版本历史</RouterLink></p>
    <p v-if="mayValidate()"><RouterLink :to="{ name: 'project-structured-spec-create', params: {
      projectId: route.params.projectId } }">基于当前项目需求与章节创建结构化专项草案</RouterLink></p>
    <p v-if="!session.view" role="status">尚未读取当前身份，请先登录。</p>
    <p v-else-if="session.view.password_change_required" role="status">当前账户须先修改密码。</p>
    <template v-else>
      <button type="button" :disabled="busy || validating || !mayRead()" @click="load()">{{ busy ? "正在读取…" : "重新读取版本" }}</button>
      <p v-if="error" role="alert">{{ error }}</p>
      <template v-if="current">
        <h2>{{ current.title }} · 版本 {{ current.version_no }} · {{ current.version_state }}</h2>
        <dl><dt>固定正文来源</dt><dd v-if="current.content_document_version_ref">DocumentVersion <code>{{ current.content_document_version_ref }}</code></dd>
          <dd v-else>ArtifactRef <code>{{ current.content_artifact_ref }}</code></dd>
          <dt>固定内容摘要</dt><dd><code>{{ current.content_fingerprint }}</code></dd>
          <dt>前一版本</dt><dd>{{ current.supersedes_version_ref ?? "无" }}</dd>
          <dt>评审引用</dt><dd>{{ current.review_ref ?? "尚无" }}</dd>
          <dt>评审轮次引用</dt><dd>{{ current.review_round_ref ?? "尚无" }}</dd>
          <dt>创建时间</dt><dd><time :datetime="current.created_at">{{ new Date(current.created_at).toLocaleString("zh-CN") }}</time></dd></dl>
        <p>当前接口未提供来源文档的精确定位信息，不能从固定 UUID 推断下载地址或原文位置。</p>
        <h3>固定需求版本（{{ current.requirement_refs.length }}）</h3>
        <p v-if="!current.requirement_refs.length">无</p>
        <ol v-else><li v-for="item in current.requirement_refs" :key="item.requirement_version_id">
          <RouterLink :to="{ name: 'project-requirement-detail', params: { projectId: current.project_id,
            requirementId: item.requirement_id } }">需求 {{ item.requirement_id }}</RouterLink>
          · 固定版本 {{ item.requirement_version_id }}</li></ol>
        <h3>固定 Evidence（{{ current.evidence_ids.length }}）</h3>
        <p v-if="!current.evidence_ids.length">无</p>
        <ol v-else><li v-for="evidence in current.evidence_ids" :key="evidence"><code>{{ evidence }}</code></li></ol>
        <h3>假设声明（{{ current.assumptions.length }}）</h3>
        <p v-if="!current.assumptions.length">无</p>
        <ol v-else><li v-for="(item, index) in current.assumptions" :key="index"><pre>{{ JSON.stringify(item, null, 2) }}</pre></li></ol>
        <h3>排除声明（{{ current.exclusions.length }}）</h3>
        <p v-if="!current.exclusions.length">无</p>
        <ol v-else><li v-for="(item, index) in current.exclusions" :key="index"><pre>{{ JSON.stringify(item, null, 2) }}</pre></li></ol>
        <section aria-labelledby="section-version-validation-title">
          <h3 id="section-version-validation-title">当前来源验证</h3>
          <p class="warning">验证会保存一次审计观察，不会批准章节，也不会创建评审。再次使用新操作号会重新观察当前来源。</p>
          <p v-if="!mayValidate()" role="status">仅当前项目负责人或实施成员可验证；请确认会话与项目权限。</p>
          <template v-else>
            <p v-if="pending" role="status">存在未确认的原验证操作。请先核对审计；结果不确定时必须保持原操作号。</p>
            <label v-if="pending"><input v-model="confirmRetry" type="checkbox" :disabled="validating || validationLocked" /> 我已核对原操作，确认按原操作号重试</label>
            <p v-if="validationError" role="alert">{{ validationError }}</p>
            <button type="button" :disabled="busy || validating || validationLocked || !!pending && !confirmRetry"
              @click="validate()">{{ validating ? "正在验证…" : pending ? "按原操作号重试验证" : "验证当前来源" }}</button>
          </template>
          <div v-if="validationReport" class="validation-report" role="status">
            <h4>验证报告 · {{ validationReport.valid ? "固定内容与来源核验通过" : "固定内容或来源存在问题" }}</h4>
            <p>{{ validationReport.ready_for_review ? "验证条件满足；仍需正式评审与客户确认。" : "尚不具备送审条件；不得视为已批准。" }}</p>
            <p>观察时间：<time :datetime="validationReport.observed_at">{{ new Date(validationReport.observed_at).toLocaleString("zh-CN") }}</time></p>
            <p>审计记录：<code>{{ validationReport.audit_event_id }}</code> · 首次观察 Trace：<code>{{ validationReport.observation_trace_id }}</code></p>
            <ul><li v-for="item in dimensions" :key="item.field">{{ item.label }}：{{ statusLabel(validationReport.facts[item.field]) }}
              <span v-if="validationReport.facts[item.field] !== 'PASS'"> — {{ dimensionHint(item.field, validationReport.facts[item.field]) }}</span></li></ul>
            <p v-if="validationReport.issue_codes.length">需处理：{{ validationReport.issue_codes.join("、") }}</p>
            <p>当前接口尚不能给出来源文档的精确位置；请从固定正文与项目证据/需求记录核查，不得凭 UUID 猜测原文位置。</p>
          </div>
        </section>
        <SectionReviewSubmitPanel :key="current.solution_section_version_id"
          :session="session" :detail="current" :report="validationReport" />
      </template>
    </template>
  </section>
</template>

<style scoped>
.section-version-detail{max-width:64rem;margin:1rem auto;padding:1.5rem;background:#fff;border-radius:1rem}
.section-version-detail dl{display:grid;grid-template-columns:10rem 1fr;gap:.5rem}
.section-version-detail dd{margin:0;overflow-wrap:anywhere}
.section-version-detail pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f5f7fa;padding:.7rem}
.validation-report{margin-top:1rem;padding:1rem;border:1px solid #94a3b8;border-radius:.5rem;overflow-wrap:anywhere}
.warning{padding:.8rem 1rem;border-left:.3rem solid #d29b42;background:#fff8e9}
.section-version-detail [role=alert]{color:#a21d25}
</style>
