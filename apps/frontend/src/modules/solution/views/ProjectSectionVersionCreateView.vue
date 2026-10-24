<script setup lang="ts">
import { inject, onUnmounted, ref, toRaw, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { sessionClientKey } from "@/modules/auth/api/sessionContext";
import { DocumentReadClient, type DocumentVersionView } from "@/modules/document/api/documentReadClient";
import { EvidenceListClient } from "@/modules/evidence/api/evidenceListClient";
import { RequirementReadClient } from "@/modules/requirement/api/requirementReadClient";
import { loadProjectDocumentVersionCandidates, loadProjectSectionVersionCandidates,
  type SectionVersionCandidates } from "@/modules/solution/api/sectionVersionCandidates";
import { SectionReadClient, type SectionCurrent } from "@/modules/solution/api/sectionReadClient";
import { SectionVersionCreateClient, SectionVersionCreateError, type SectionVersionDraft } from
  "@/modules/solution/api/sectionVersionCreateClient";

type CandidateLoader = typeof loadProjectSectionVersionCandidates;
type VersionLoader = typeof loadProjectDocumentVersionCandidates;
const props = defineProps<{ session?: SessionClient; reader?: SectionReadClient;
  documents?: DocumentReadClient; creator?: SectionVersionCreateClient;
  candidateLoader?: CandidateLoader; versionLoader?: VersionLoader }>();
const session = toRaw(props.session ?? inject(sessionClientKey, null) ?? new SessionClient());
const reader = toRaw(props.reader ?? new SectionReadClient());
const documents = toRaw(props.documents ?? new DocumentReadClient());
const creator = toRaw(props.creator ?? new SectionVersionCreateClient(session));
const candidateLoader = props.candidateLoader ?? loadProjectSectionVersionCandidates;
const versionLoader = props.versionLoader ?? loadProjectDocumentVersionCandidates;
const route = useRoute();
const projectId = () => typeof route.params.projectId === "string" ? route.params.projectId : "";
const sectionId = () => typeof route.params.sectionId === "string" ? route.params.sectionId : "";
const parent = ref<SectionCurrent | null>(null);
const candidates = ref<SectionVersionCandidates | null>(null);
const versions = ref<readonly DocumentVersionView[]>([]);
const title = ref(""); const selectedDocument = ref(""); const selectedVersion = ref("");
const selectedRequirements = ref<string[]>([]); const selectedEvidence = ref<string[]>([]);
const assumptionText = ref(""); const exclusionText = ref("");
const loading = ref(false); const versionLoading = ref(false); const busy = ref(false); const error = ref("");
const confirmCreate = ref(false); const confirmRetry = ref(false); const locked = ref(false); const createdId = ref("");
const pending = ref<{ project: string; section: string; actor: string; draft: SectionVersionDraft; key: string } | null>(null);
let mounted = true; let generation = 0; let versionGeneration = 0;
function authorized() {
  return mounted && !!session.view && !session.view.password_change_required && session.canSubmit
    && session.view.authorized_projects.some(item => item.project_id === projectId()
      && (item.role === "PROJECT_MANAGER" || item.role === "IMPLEMENTATION_MEMBER"));
}
function storageKey() {
  return `plm.sol.section.version.create.pending.${session.view?.user.user_id ?? "none"}.${projectId()}.${sectionId()}`;
}
function restore() {
  pending.value = null; locked.value = false; confirmRetry.value = false; confirmCreate.value = false;
  createdId.value = ""; error.value = "";
  if (!authorized()) return;
  try {
    const raw = window.sessionStorage.getItem(storageKey());
    if (!raw) return;
    const value: unknown = JSON.parse(raw);
    if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("invalid");
    const item = value as Record<string, unknown>;
    if (item.project !== projectId() || item.section !== sectionId() || item.actor !== session.view?.user.user_id
      || typeof item.key !== "string" || !/^[\x20-\x7e]{16,128}$/.test(item.key)
      || !item.draft || typeof item.draft !== "object" || Array.isArray(item.draft)
      || new TextEncoder().encode(JSON.stringify(item.draft)).length > 512 * 1024) throw new Error("invalid");
    pending.value = item as unknown as typeof pending.value;
  } catch {
    locked.value = true; error.value = "原版本操作记录无法读取，已停止提交；请核对章节版本和审计记录。";
  }
}
async function load() {
  if (!authorized() || loading.value) return;
  const project = projectId(), section = sectionId(), run = ++generation;
  loading.value = true; parent.value = null; candidates.value = null;
  if (!locked.value) error.value = "";
  try {
    const [current, available] = await Promise.all([reader.current(project, section),
      candidateLoader(project, documents, new RequirementReadClient(), new EvidenceListClient())]);
    if (!mounted || run !== generation || project !== projectId() || section !== sectionId()) return;
    if (current.project_id !== project || current.solution_section_id !== section) throw new Error("章节身份不匹配。");
    parent.value = current; candidates.value = available;
  } catch (failure) {
    if (mounted && run === generation && !locked.value) error.value = failure instanceof Error
      ? failure.message : "暂时无法核对来源候选。";
  } finally { if (mounted && run === generation) loading.value = false; }
}
async function loadVersions() {
  const project = projectId(), section = sectionId(), document = selectedDocument.value;
  const run = ++versionGeneration;
  versions.value = []; selectedVersion.value = ""; confirmCreate.value = false;
  if (!document || !candidates.value?.documents.some(item => item.document_id === document)) return;
  versionLoading.value = true; error.value = "";
  try {
    const available = await versionLoader(project, document, documents);
    if (!mounted || run !== versionGeneration || project !== projectId() || section !== sectionId()
      || document !== selectedDocument.value) return;
    versions.value = available;
  } catch (failure) {
    if (mounted && run === versionGeneration) error.value = failure instanceof Error
      ? failure.message : "无法核对文档版本。";
  } finally { if (mounted && run === versionGeneration) versionLoading.value = false; }
}
watch(() => [route.params.projectId, route.params.sectionId], () => {
  if (route.name !== "project-section-version-create") return;
  generation += 1; versionGeneration += 1; loading.value = false; versionLoading.value = false;
  parent.value = null; candidates.value = null; versions.value = [];
  title.value = ""; selectedDocument.value = ""; selectedVersion.value = "";
  selectedRequirements.value = []; selectedEvidence.value = [];
  assumptionText.value = ""; exclusionText.value = "";
  restore(); void load();
}, { immediate: true });
onUnmounted(() => { mounted = false; generation += 1; versionGeneration += 1; });
function canCreate() {
  if (pending.value) return authorized();
  return authorized() && parent.value?.section_state === "ACTIVE"
    && parent.value.project_id === projectId() && parent.value.solution_section_id === sectionId()
    && !!candidates.value && !loading.value && !versionLoading.value;
}
function statements(raw: string, label: string): readonly Record<string, unknown>[] {
  const lines = raw.split(/\r?\n/).map(value => value.trim()).filter(Boolean);
  if (lines.length > 100 || lines.some(value => value.length > 2000 || /\p{C}/u.test(value))) {
    throw new Error(`${label}最多 100 条，每条最多 2000 字且不能包含控制字符。`);
  }
  return lines.map(description => ({ description }));
}
function draftFromSelection(): SectionVersionDraft {
  const available = candidates.value;
  const normalizedTitle = title.value.trim().normalize("NFC");
  if (!available || !normalizedTitle || normalizedTitle.length > 500 || /[\p{Cc}\p{Cs}]/u.test(normalizedTitle)
    || !available.documents.some(item => item.document_id === selectedDocument.value)
    || !versions.value.some(item => item.document_version_id === selectedVersion.value)
    || selectedRequirements.value.length > 500 || selectedEvidence.value.length > 500
    || new Set(selectedRequirements.value).size !== selectedRequirements.value.length
    || new Set(selectedEvidence.value).size !== selectedEvidence.value.length) {
    throw new Error("请输入标题并选择当前项目的可用文档固定版本；来源不得重复。");
  }
  const requirements = selectedRequirements.value.map(identity => {
    const item = available.requirements.find(value => value.requirement_id === identity);
    if (!item?.current_approved_version_ref) throw new Error("需求候选已变化，请刷新后核对。");
    return { requirement_id: item.requirement_id, requirement_version_id: item.current_approved_version_ref };
  });
  const evidence = selectedEvidence.value.map(identity => {
    const item = available.evidence.find(value => value.evidence_id === identity);
    if (!item) throw new Error("证据候选已变化，请刷新后核对。");
    return item.evidence_id;
  });
  return { title: normalizedTitle, content_document_version_ref: selectedVersion.value,
    content_artifact_ref: null, requirement_refs: requirements, evidence_ids: evidence,
    assumptions: statements(assumptionText.value, "假设"), exclusions: statements(exclusionText.value, "排除项") };
}
async function submit() {
  if (!canCreate() || busy.value || locked.value || createdId.value
    || (pending.value ? !confirmRetry.value : !confirmCreate.value)) return;
  const project = projectId(), section = sectionId(), actor = session.view!.user.user_id;
  let attempt = pending.value;
  if (!attempt) {
    let draft: SectionVersionDraft;
    try { draft = draftFromSelection(); }
    catch (failure) { error.value = failure instanceof Error ? failure.message : "来源无效。"; return; }
    attempt = { project, section, actor, draft, key: crypto.randomUUID() };
    try { window.sessionStorage.setItem(storageKey(), JSON.stringify(attempt)); }
    catch { error.value = "无法保存原操作号，本次未提交。"; return; }
    pending.value = attempt;
  }
  if (attempt.project !== project || attempt.section !== section || attempt.actor !== actor) {
    locked.value = true; return;
  }
  confirmRetry.value = false; busy.value = true; error.value = "";
  try {
    const result = await creator.create(project, section, attempt.draft, attempt.key);
    if (!mounted || project !== projectId() || section !== sectionId() || actor !== session.view?.user.user_id) return;
    createdId.value = result.solution_section_version_id;
    try { window.sessionStorage.removeItem(storageKey()); pending.value = null; }
    catch { locked.value = true; error.value = "版本已创建，但原操作号清理失败；请停止再次提交。"; }
  } catch (failure) {
    if (!mounted) return;
    if (failure instanceof SectionVersionCreateError && failure.code === "CONFLICT_IDEMPOTENCY") locked.value = true;
    error.value = failure instanceof Error ? failure.message : "创建结果无法确认，请保留原操作号。";
  } finally { if (mounted) busy.value = false; }
}
</script>

<template>
  <section class="section-version-create" aria-labelledby="section-version-create-title" :aria-busy="loading || versionLoading || busy">
    <p class="section-kicker">项目方案</p><h1 id="section-version-create-title">创建章节草案版本</h1>
    <p class="warning">仅建立待评审 DRAFT，不代表已批准或已交付。提交时服务器会再次核对当前来源资格。</p>
    <p><RouterLink :to="{ name: 'project-section-detail', params: { projectId: route.params.projectId,
      sectionId: route.params.sectionId } }">返回章节详情</RouterLink></p>
    <p v-if="!authorized()" role="status">仅当前项目负责人或实施成员可创建；请确认会话与项目权限。</p>
    <template v-else>
      <button type="button" :disabled="loading || busy || !!pending || locked" @click="load()">{{ loading ? "正在核对…" : "刷新当前候选" }}</button>
      <p v-if="error" role="alert">{{ error }}</p>
      <p v-if="createdId" role="status">草案版本已创建。
        <RouterLink :to="{ name: 'project-section-version-detail', params: { projectId: route.params.projectId,
          sectionId: route.params.sectionId, versionId: createdId } }">查看固定版本详情</RouterLink></p>
      <p v-else-if="loading" role="status">正在读取章节与固定来源候选…</p>
      <p v-else-if="parent?.section_state === 'ARCHIVED' && !pending" role="status">章节已归档，不可创建草案。</p>
      <form v-else-if="canCreate()" @submit.prevent="submit">
        <template v-if="pending">
          <p class="warning" role="status">存在原创建操作。结果不确定时，请先核对版本历史；不得更改来源或换操作号。</p>
          <p>原内容：{{ pending.draft.title }}；需求 {{ pending.draft.requirement_refs.length }} 项，证据 {{ pending.draft.evidence_ids.length }} 项。重试保持首次固定正文与原操作号。</p>
          <label><input v-model="confirmRetry" type="checkbox" :disabled="busy || locked" /> 我已核对原操作，确认按原内容和原操作号重试</label>
          <p><RouterLink :to="{ name: 'project-section-versions', params: { projectId: route.params.projectId,
            sectionId: route.params.sectionId } }">先查看版本历史</RouterLink></p>
        </template>
        <template v-else>
          <label for="section-version-title">1. 章节版本标题</label>
          <input id="section-version-title" v-model="title" maxlength="500" :disabled="busy" placeholder="例如：产品数据管理方案草案" />
          <label for="section-version-document">2. 正文来源文档（当前项目活动文档）</label>
          <select id="section-version-document" v-model="selectedDocument" :disabled="busy" @change="loadVersions()">
            <option value="">请选择文档</option>
            <option v-for="item in candidates?.documents" :key="item.document_id" :value="item.document_id">{{ item.title || item.display_name }}</option>
          </select>
          <p v-if="!candidates?.documents.length">当前没有活动文档；请先上传文档并刷新。</p>
          <p v-if="selectedDocument"><RouterLink :to="{ name: 'project-document-detail', params: {
            projectId: route.params.projectId, documentId: selectedDocument } }">查看所选文档</RouterLink></p>
          <label for="section-version-document-version">3. 固定正文版本</label>
          <select id="section-version-document-version" v-model="selectedVersion" :disabled="busy || versionLoading || !selectedDocument">
            <option value="">{{ versionLoading ? "正在核对版本…" : "请选择可用版本" }}</option>
            <option v-for="item in versions" :key="item.document_version_id" :value="item.document_version_id">版本 {{ item.version_no }} · {{ new Date(item.created_at).toLocaleString('zh-CN') }}</option>
          </select>
          <fieldset :disabled="busy"><legend>4. 当前已批准需求版本（可选）</legend>
            <p v-if="!candidates?.requirements.length">暂无当前已批准需求。</p>
            <label v-for="item in candidates?.requirements" :key="item.requirement_id"><input v-model="selectedRequirements" type="checkbox" :value="item.requirement_id" /> {{ item.requirement_code }}
              <RouterLink :to="{ name: 'project-requirement-detail', params: { projectId: item.project_id,
                requirementId: item.requirement_id } }">查看需求</RouterLink></label>
          </fieldset>
          <fieldset :disabled="busy"><legend>5. 当前合格的本项目证据（可选）</legend>
            <p v-if="!candidates?.evidence.length">暂无当前合格证据。</p>
            <label v-for="item in candidates?.evidence" :key="item.evidence_id"><input v-model="selectedEvidence" type="checkbox" :value="item.evidence_id" /> {{ item.display_label }}</label>
            <p><RouterLink :to="{ name: 'project-evidence', params: { projectId: route.params.projectId } }">查看项目证据列表</RouterLink></p>
          </fieldset>
          <label for="section-version-assumptions">6. 假设（每行一条，可选）</label>
          <textarea id="section-version-assumptions" v-model="assumptionText" rows="3" maxlength="64000" :disabled="busy" placeholder="例如：接口字段清单将在联调前确认。" />
          <label for="section-version-exclusions">7. 排除项（每行一条，可选）</label>
          <textarea id="section-version-exclusions" v-model="exclusionText" rows="3" maxlength="64000" :disabled="busy" placeholder="例如：本阶段不包含历史数据清洗。" />
          <label><input v-model="confirmCreate" type="checkbox" :disabled="busy" /> 我已核对正文固定版本与可选来源，确认仅创建待评审草案</label>
        </template>
        <button type="submit" :disabled="busy || locked || (pending ? !confirmRetry : !confirmCreate)">{{ busy ? "正在提交…" : pending ? "按原操作号重试" : "创建 DRAFT 草案" }}</button>
      </form>
    </template>
  </section>
</template>

<style scoped>
.section-version-create{max-width:64rem;margin:1rem auto;padding:1.5rem;background:#fff;border-radius:1rem}
.section-version-create form{display:grid;gap:.9rem}.section-version-create fieldset{display:grid;gap:.5rem;border:1px solid #aaa;border-radius:.5rem}
.section-version-create textarea,.section-version-create select,.section-version-create input:not([type=checkbox]){width:100%;box-sizing:border-box}
.section-version-create [role=alert]{color:#a21d25}.warning{padding:.8rem 1rem;border-left:.3rem solid #d29b42;background:#fff8e9}
</style>
