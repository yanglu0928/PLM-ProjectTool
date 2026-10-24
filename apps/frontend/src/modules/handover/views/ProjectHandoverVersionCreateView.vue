<script setup lang="ts">
import { computed, inject, onUnmounted, ref, shallowRef, toRaw, watch } from "vue";
import { RouterLink, useRoute, useRouter } from "vue-router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { sessionClientKey } from "@/modules/auth/api/sessionContext";
import { DocumentReadClient, type DocumentView, type DocumentVersionView } from "@/modules/document/api/documentReadClient";
import { CapabilityReadClient, type CapabilityBaseline, type CapabilityItem,
  type CapabilityVersion } from "@/modules/capability/api/capabilityReadClient";
import { EvidenceListClient, type EvidenceSummary } from "@/modules/evidence/api/evidenceListClient";
import { EvidenceViewerClient, type EvidenceViewerDescriptor } from "@/modules/evidence/api/evidenceViewerClient";
import { HandoverReadClient, type HandoverAnalysisView } from "@/modules/handover/api/handoverReadClient";
import { HandoverVersionCreateClient, HandoverVersionCreateError, normalizeHandoverVersionItems,
  type HandoverVersionCreateInput, type HandoverVersionItemDraft } from "@/modules/handover/api/handoverVersionCreateClient";
import { normalizeHandoverSources, type HandoverCreateSource } from "@/modules/handover/api/handoverCreateClient";
import { matchesHandoverSourceSet } from "@/modules/handover/api/handoverSourceSetMatch";

const props = defineProps<{ session?: SessionClient; handover?: HandoverReadClient;
  documents?: DocumentReadClient; capabilities?: CapabilityReadClient; evidence?: EvidenceListClient;
  viewer?: EvidenceViewerClient; creator?: HandoverVersionCreateClient }>();
const session = toRaw(props.session ?? inject(sessionClientKey, null) ?? new SessionClient());
const handover = toRaw(props.handover ?? new HandoverReadClient());
const documents = toRaw(props.documents ?? new DocumentReadClient());
const capabilities = toRaw(props.capabilities ?? new CapabilityReadClient());
const evidence = toRaw(props.evidence ?? new EvidenceListClient());
const viewer = toRaw(props.viewer ?? new EvidenceViewerClient());
const creator = toRaw(props.creator ?? new HandoverVersionCreateClient(session));
const route = useRoute(); const router = useRouter(); const identity = session.view;
function ids() { return { project: typeof route.params.projectId === "string" ? route.params.projectId : "",
  analysis: typeof route.params.analysisId === "string" ? route.params.analysisId : "" }; }
const authorized = computed(() => !!identity && !identity.password_change_required && session.canSubmit
  && identity.user.user_id === session.view?.user.user_id && identity.authorized_projects.some(item =>
    item.project_id === ids().project && (item.role === "PROJECT_MANAGER" || item.role === "IMPLEMENTATION_MEMBER")));
interface SelectedSource extends HandoverCreateSource { readonly title: string; readonly version_no: number; }
interface Card { id: string; type: HandoverVersionItemDraft["item_type"]; title: string; statement: string;
  impact: string; severity: HandoverVersionItemDraft["severity"]; priority: HandoverVersionItemDraft["priority"];
  recommendation: string; question: string; fieldName: string; fieldFormat: string; fieldExample: string;
  optionA: string; optionB: string; evidenceIds: string[]; capabilityIds: string[]; }
interface Pending { project: string; analysis: string; actor: string; etag: string; key: string;
  input: HandoverVersionCreateInput; }
function newCard(): Card { return { id: crypto.randomUUID(), type: "GAP", title: "", statement: "", impact: "",
  severity: "MEDIUM", priority: "MEDIUM", recommendation: "", question: "", fieldName: "",
  fieldFormat: "", fieldExample: "", optionA: "", optionB: "", evidenceIds: [], capabilityIds: [] }; }
const analysis = shallowRef<HandoverAnalysisView | null>(null);
const docs = ref<readonly DocumentView[]>([]); const docsCursor = ref<string | null>(null);
const activeDoc = shallowRef<DocumentView | null>(null); const versions = ref<readonly DocumentVersionView[]>([]);
const versionsCursor = ref<string | null>(null); const chosen = ref<SelectedSource[]>([]);
const baselines = ref<readonly CapabilityBaseline[]>([]); const baselineCursor = ref<string | null>(null);
const selectedBaseline = shallowRef<CapabilityBaseline | null>(null);
const selectedVersion = shallowRef<CapabilityVersion | null>(null);
const capabilityItems = ref<readonly CapabilityItem[]>([]); const capabilityCursor = ref<string | null>(null);
const evidenceItems = ref<readonly EvidenceSummary[]>([]); const evidenceCursor = ref<string | null>(null);
const selectedEvidence = shallowRef<EvidenceViewerDescriptor | null>(null);
const cards = ref<Card[]>([newCard()]); const sourceMatch = ref<boolean | null>(null);
const busy = ref(false); const lookupBusy = ref(false); const writeBusy = ref(false);
const error = ref(""); const sourceError = ref(""); const createdId = ref("");
const pending = ref<Pending | null>(null); const retryConfirmed = ref(false); const locked = ref(false);
let mounted = true; let generation = 0; let sourceGeneration = 0;
const eligible = computed(() => evidenceItems.value.filter(item => item.eligibility_state === "ELIGIBLE"
  && chosen.value.some(source => source.document_id === item.document_id
    && source.document_version_id === item.document_version_id)));
function storageKey() { const value = ids(); return `plm.hnd.version.create.pending.${identity?.user.user_id ?? "none"}.${value.project}.${value.analysis}`; }
function restore() {
  pending.value = null; retryConfirmed.value = false; locked.value = false;
  try {
    const raw = sessionStorage.getItem(storageKey()); if (!raw) return;
    const value: unknown = JSON.parse(raw);
    if (typeof value !== "object" || value === null || Array.isArray(value)) throw new Error("invalid");
    const entry = value as Record<string, unknown>; const current = ids();
    if (Object.keys(entry).length !== 6 || entry.project !== current.project || entry.analysis !== current.analysis
      || entry.actor !== identity?.user.user_id || typeof entry.etag !== "string"
      || !/^"v(0|[1-9][0-9]*)"$/.test(entry.etag) || typeof entry.key !== "string"
      || !/^[\x20-\x7e]{16,128}$/.test(entry.key) || typeof entry.input !== "object"
      || entry.input === null || Array.isArray(entry.input)) throw new Error("invalid");
    pending.value = entry as unknown as Pending;
  } catch { locked.value = true; error.value = "原操作记录损坏；已停止写入。请先核对版本列表与审计。"; }
}
async function load() {
  if (!authorized.value) return;
  const current = ++generation; const request = ids(); busy.value = true;
  if (!locked.value) error.value = "";
  analysis.value = null; docs.value = []; docsCursor.value = null; baselines.value = [];
  baselineCursor.value = null; evidenceItems.value = []; evidenceCursor.value = null;
  try {
    const [root, docPage, basePage, evPage] = await Promise.all([
      handover.getAnalysis(request.project, request.analysis),
      documents.list({ kind: "PROJECT", projectId: request.project }),
      capabilities.listBaselines(), evidence.list({ kind: "PROJECT", projectId: request.project }),
    ]);
    if (!mounted || current !== generation || ids().project !== request.project || ids().analysis !== request.analysis
      || !authorized.value) return;
    if (root.state !== "ACTIVE") throw new Error("分析已非 ACTIVE，不能创建版本。");
    analysis.value = root; docs.value = docPage.items; docsCursor.value = docPage.next_cursor;
    baselines.value = basePage.items; baselineCursor.value = basePage.next_cursor;
    evidenceItems.value = evPage.items; evidenceCursor.value = evPage.next_cursor;
  } catch (failure) { if (mounted && current === generation) error.value = failure instanceof Error
    ? failure.message : "暂时无法读取交接版本创建所需的资料。";
  } finally { if (mounted && current === generation) busy.value = false; }
}
async function moreDocs() { if (!docsCursor.value || lookupBusy.value || !authorized.value) return;
  const current = generation, request = ids(), cursor = docsCursor.value; lookupBusy.value = true;
  try { const page = await documents.list({ kind: "PROJECT", projectId: request.project }, cursor);
    if (!mounted || current !== generation || ids().project !== request.project) return;
    if (page.items.some(item => docs.value.some(old => old.document_id === item.document_id))) throw new Error("重复文档页");
    docs.value = [...docs.value, ...page.items]; docsCursor.value = page.next_cursor;
  } catch { error.value = "加载更多项目文档失败，请刷新。"; }
  finally { lookupBusy.value = false; } }
async function openDoc(doc: DocumentView) { if (!authorized.value || pending.value || doc.state !== "ACTIVE") return;
  activeDoc.value = doc; versions.value = []; versionsCursor.value = null; lookupBusy.value = true; error.value = "";
  const current = generation, request = ids();
  try { const page = await documents.listVersions({ kind: "PROJECT", projectId: request.project }, doc.document_id);
    if (!mounted || current !== generation || activeDoc.value?.document_id !== doc.document_id) return;
    versions.value = page.items; versionsCursor.value = page.next_cursor;
  } catch { error.value = "读取文档固定版本失败。"; }
  finally { lookupBusy.value = false; } }
async function moreVersions() { if (!activeDoc.value || !versionsCursor.value || lookupBusy.value) return;
  const doc = activeDoc.value, cursor = versionsCursor.value, current = generation, request = ids(); lookupBusy.value = true;
  try { const page = await documents.listVersions({ kind: "PROJECT", projectId: request.project }, doc.document_id, cursor);
    if (!mounted || current !== generation || activeDoc.value?.document_id !== doc.document_id) return;
    versions.value = [...versions.value, ...page.items]; versionsCursor.value = page.next_cursor;
  } catch { error.value = "加载更多文档版本失败。"; } finally { lookupBusy.value = false; } }
function chooseVersion(version: DocumentVersionView) { const doc = activeDoc.value;
  if (!doc || version.availability_state !== "AVAILABLE" || pending.value || !authorized.value) return;
  chosen.value = [...chosen.value.filter(item => item.document_id !== doc.document_id),
    { document_id: doc.document_id, document_version_id: version.document_version_id,
      title: doc.title, version_no: version.version_no }];
  activeDoc.value = null; versions.value = []; versionsCursor.value = null;
  for (const card of cards.value) card.evidenceIds = card.evidenceIds.filter(id =>
    evidenceItems.value.some(item => item.evidence_id === id && chosen.value.some(source =>
      source.document_id === item.document_id && source.document_version_id === item.document_version_id)));
}
async function moreBaselines() { if (!baselineCursor.value || lookupBusy.value) return;
  const cursor = baselineCursor.value, current = generation; lookupBusy.value = true;
  try { const page = await capabilities.listBaselines(cursor); if (!mounted || current !== generation) return;
    baselines.value = [...baselines.value, ...page.items]; baselineCursor.value = page.next_cursor;
  } catch { error.value = "加载更多标准能力失败。"; } finally { lookupBusy.value = false; } }
async function chooseBaseline(value: CapabilityBaseline) { if (!authorized.value || pending.value
  || value.state !== "ACTIVE" || !value.current_approved_version_ref) return;
  lookupBusy.value = true; error.value = ""; const current = generation;
  try { const [root, version, page] = await Promise.all([
    capabilities.getBaseline(value.baseline_id),
    capabilities.getVersion(value.baseline_id, value.current_approved_version_ref),
    capabilities.listItems(value.baseline_id, value.current_approved_version_ref),
  ]);
    if (!mounted || current !== generation) return;
    if (root.state !== "ACTIVE" || root.current_approved_version_ref !== version.baseline_version_id
      || version.state !== "APPROVED") throw new Error("该能力版本当前未获批准，请刷新。");
    selectedBaseline.value = root; selectedVersion.value = version;
    capabilityItems.value = page.items; capabilityCursor.value = page.next_cursor;
    for (const card of cards.value) card.capabilityIds = [];
  } catch (failure) { error.value = failure instanceof Error ? failure.message : "读取已批准标准能力失败。"; }
  finally { lookupBusy.value = false; } }
async function moreCapabilities() { const baseline = selectedBaseline.value, version = selectedVersion.value;
  if (!baseline || !version || !capabilityCursor.value || lookupBusy.value) return;
  const cursor = capabilityCursor.value, current = generation; lookupBusy.value = true;
  try { const page = await capabilities.listItems(baseline.baseline_id, version.baseline_version_id, cursor);
    if (!mounted || current !== generation) return;
    capabilityItems.value = [...capabilityItems.value, ...page.items]; capabilityCursor.value = page.next_cursor;
  } catch { error.value = "加载更多能力条目失败。"; } finally { lookupBusy.value = false; } }
async function moreEvidence() { if (!evidenceCursor.value || lookupBusy.value) return;
  const cursor = evidenceCursor.value, current = generation, request = ids(); lookupBusy.value = true;
  try { const page = await evidence.list({ kind: "PROJECT", projectId: request.project }, cursor);
    if (!mounted || current !== generation || ids().project !== request.project) return;
    evidenceItems.value = [...evidenceItems.value, ...page.items]; evidenceCursor.value = page.next_cursor;
  } catch { error.value = "加载更多项目证据失败。"; } finally { lookupBusy.value = false; } }
async function locate(item: EvidenceSummary) { if (!eligible.value.some(value => value.evidence_id === item.evidence_id)) return;
  lookupBusy.value = true; selectedEvidence.value = null; const current = generation, request = ids();
  try { const value = await viewer.get({ kind: "PROJECT", projectId: request.project }, item.evidence_id);
    if (!mounted || current !== generation || ids().project !== request.project) return;
    selectedEvidence.value = value;
  } catch { error.value = "暂时无法定位原文；该证据不可用于提交前核对。"; }
  finally { lookupBusy.value = false; } }
watch([chosen, analysis], () => { const current = ++sourceGeneration; sourceMatch.value = null; sourceError.value = "";
  if (!analysis.value || chosen.value.length === 0) return;
  void matchesHandoverSourceSet(chosen.value.map(item => ({ document_id: item.document_id,
    document_version_id: item.document_version_id })), analysis.value.source_set_ref)
    .then(match => { if (mounted && current === sourceGeneration) sourceMatch.value = match; })
    .catch(() => { if (mounted && current === sourceGeneration) sourceError.value = "无法校验固定来源，请重试。"; });
});
watch(() => [route.params.projectId, route.params.analysisId], () => {
  generation++; sourceGeneration++; analysis.value = null; chosen.value = []; activeDoc.value = null;
  selectedBaseline.value = null; selectedVersion.value = null; capabilityItems.value = []; capabilityCursor.value = null;
  selectedEvidence.value = null; cards.value = [newCard()]; createdId.value = "";
  sourceMatch.value = null; sourceError.value = ""; error.value = ""; restore(); void load();
}, { immediate: true });
onUnmounted(() => { mounted = false; generation++; sourceGeneration++; });
function removeCard(index: number) { if (!pending.value && cards.value.length > 1) cards.value.splice(index, 1); }
function addCard() { if (!pending.value && cards.value.length < 500) cards.value.push(newCard()); }
function buildInput(): HandoverVersionCreateInput {
  const baseline = selectedBaseline.value, version = selectedVersion.value;
  if (!baseline || !version || baseline.current_approved_version_ref !== version.baseline_version_id
    || version.state !== "APPROVED" || sourceMatch.value !== true) throw new Error("请先核对原固定来源和当前批准的标准能力版本。");
  const refs = new Set(eligible.value.map(item => item.evidence_id));
  const capabilityRefs = new Set(capabilityItems.value.filter(item => item.state === "AVAILABLE")
    .map(item => item.capability_item_id));
  const items = cards.value.map(card => {
    if (!card.evidenceIds.length || card.evidenceIds.some(id => !refs.has(id))
      || card.capabilityIds.some(id => !capabilityRefs.has(id))) {
      throw new Error("每张问题卡片至少选择一条同固定文档、当前已合格的项目证据。");
    }
    const confirm = card.type === "NEED_CONFIRM";
    const requiredInput: HandoverVersionItemDraft["required_input_spec"] = confirm
      ? { fields: [{ name: card.fieldName.trim(), format: card.fieldFormat.trim(),
        example: card.fieldExample.trim(), required: true }] } : {};
    return { analysis_item_id: card.id, item_type: card.type, title: card.title.trim(),
      statement: card.statement.trim(), impact: card.impact.trim(), severity: card.severity,
      priority: card.priority, recommendation: card.recommendation.trim() || null,
      confirmation_question: confirm ? card.question.trim() : null,
      required_input_spec: requiredInput,
      source_missing: false, evidence_refs: [...card.evidenceIds], capability_refs: [...card.capabilityIds],
      options: confirm ? [{ option_code: "A", label: card.optionA.trim(), description: null },
        { option_code: "B", label: card.optionB.trim(), description: null }] : [],
    } satisfies HandoverVersionItemDraft;
  });
  normalizeHandoverVersionItems(items);
  return { source_documents: normalizeHandoverSources(chosen.value.map(item => ({ document_id: item.document_id,
    document_version_id: item.document_version_id }))), capability_baseline_id: baseline.baseline_id,
    capability_baseline_version_id: version.baseline_version_id, items, ai_task_refs: [] };
}
async function submit() { if (!authorized.value || busy.value || writeBusy.value || locked.value || createdId.value
  || pending.value && !retryConfirmed.value) return;
  const request = ids(), actor = identity!.user.user_id;
  let attempt = pending.value;
  if (!attempt) {
    if (!analysis.value || analysis.value.state !== "ACTIVE") return;
    try { const input = buildInput();
      if (!await matchesHandoverSourceSet(input.source_documents, analysis.value.source_set_ref)) {
        throw new Error("所选固定来源与原分析不一致。");
      }
      attempt = { ...request, actor, etag: analysis.value.etag, key: crypto.randomUUID(), input };
      sessionStorage.setItem(storageKey(), JSON.stringify(attempt)); pending.value = attempt;
    } catch (failure) { error.value = failure instanceof Error ? failure.message : "请核对问题内容和来源。"; return; }
  }
  if (attempt.project !== request.project || attempt.analysis !== request.analysis || attempt.actor !== actor) {
    locked.value = true; return;
  }
  retryConfirmed.value = false; writeBusy.value = true; error.value = "";
  try { const result = await creator.create(request.project, request.analysis, attempt.etag, attempt.input, attempt.key);
    if (!mounted || ids().project !== request.project || ids().analysis !== request.analysis
      || session.view?.user.user_id !== actor) return;
    createdId.value = result.handover_analysis_version_id;
    try { sessionStorage.removeItem(storageKey()); pending.value = null; }
    catch { locked.value = true; error.value = "版本已创建，但原操作记录未能清理；请停止再次提交。"; return; }
    try { await router.push({ name: "project-handover-detail", params: { projectId: request.project,
      analysisId: request.analysis } }); }
    catch { error.value = "版本已创建，但自动跳转失败。请从下方链接进入详情。"; }
  } catch (failure) { if (!mounted) return;
    if (failure instanceof HandoverVersionCreateError && failure.code === "CONFLICT_IDEMPOTENCY") locked.value = true;
    if (failure instanceof HandoverVersionCreateError && !failure.uncertain
      && failure.code !== "CONFLICT_IDEMPOTENCY") {
      try { sessionStorage.removeItem(storageKey()); pending.value = null; }
      catch { locked.value = true; }
    }
    error.value = failure instanceof Error ? failure.message : "提交结果无法确认；请保留原操作号。";
  } finally { if (mounted) writeBusy.value = false; }
}
</script>

<template>
  <section class="handover-version-create" aria-labelledby="handover-version-create-title" :aria-busy="busy || lookupBusy || writeBusy">
    <p class="section-kicker">项目交接</p><h1 id="handover-version-create-title">创建问题卡片草稿版本</h1>
    <p class="fact-warning">这里仅创建 DRAFT 候选版本；AI 建议、证据资格和项目负责人编辑都不等于客户确认或正式批准。</p>
    <p><RouterLink :to="{ name: 'project-handover-detail', params: { projectId: route.params.projectId,
      analysisId: route.params.analysisId } }">返回交接分析详情与版本列表</RouterLink></p>
    <p v-if="!authorized" role="status">仅当前项目负责人或实施成员可编辑交接问题。</p>
    <template v-else>
      <p v-if="error" role="alert">{{ error }}</p>
      <p v-if="busy" role="status">正在读取分析、项目文档、标准能力和项目证据…</p>
      <p v-if="createdId" role="status">DRAFT 版本 {{ createdId }} 已创建；请进入详情查看，后续评审另行进行。</p>
      <template v-if="analysis && !createdId">
        <p>分析目的：{{ analysis.analysis_purpose }}。当前分析标记：{{ analysis.etag }}。</p>
        <button type="button" :disabled="busy || lookupBusy || !!pending" @click="load">刷新全部可选资料</button>
        <section aria-labelledby="source-title"><h2 id="source-title">1. 核对原分析固定文档</h2>
          <p>首个版本不能从分析指纹自动找回文档，请重新选择创建分析时的同一批固定版本；只有完全匹配才可提交。正文不会复制到表单。</p>
          <ul><li v-for="doc in docs" :key="doc.document_id">{{ doc.title }} · {{ doc.state }}
            <button type="button" :disabled="doc.state !== 'ACTIVE' || !!pending || lookupBusy" @click="openDoc(doc)">选择固定版本</button></li></ul>
          <button v-if="docsCursor" type="button" :disabled="lookupBusy || !!pending" @click="moreDocs">加载更多文档</button>
          <div v-if="activeDoc" class="picker"><h3>{{ activeDoc.title }} 的版本</h3>
            <ul><li v-for="version in versions" :key="version.document_version_id">版本 {{ version.version_no }} · {{ version.availability_state }}
              <button type="button" :disabled="version.availability_state !== 'AVAILABLE' || lookupBusy || !!pending"
                @click="chooseVersion(version)">选用此固定版本</button></li></ul>
            <button v-if="versionsCursor" type="button" :disabled="lookupBusy" @click="moreVersions">加载更多版本</button>
            <button type="button" @click="activeDoc = null">关闭</button></div>
          <ol><li v-for="source in chosen" :key="source.document_id">{{ source.title }} · 版本 {{ source.version_no }}
            <button type="button" :disabled="!!pending" @click="chosen = chosen.filter(item => item.document_id !== source.document_id)">移除</button></li></ol>
          <p v-if="sourceError" role="alert">{{ sourceError }}</p>
          <p v-else-if="sourceMatch === true" role="status">固定来源与原分析完全匹配。</p>
          <p v-else-if="sourceMatch === false" role="alert">所选固定来源与原分析不一致，请检查文档和版本。</p>
          <p v-else role="status">尚未完成原固定来源匹配。</p>
        </section>
        <section aria-labelledby="baseline-title"><h2 id="baseline-title">2. 选择当前已批准的标准能力版本</h2>
          <p>项目角色不能批准全局标准能力；此处只引用已有批准结果。</p>
          <ul><li v-for="value in baselines" :key="value.baseline_id">{{ value.name }} · {{ value.state }}
            <span>{{ value.current_approved_version_ref ? '有当前批准版' : '无当前批准版' }}</span>
            <button type="button" :disabled="value.state !== 'ACTIVE' || !value.current_approved_version_ref || lookupBusy || !!pending"
              @click="chooseBaseline(value)">选用已批准版</button></li></ul>
          <button v-if="baselineCursor" type="button" :disabled="lookupBusy || !!pending" @click="moreBaselines">加载更多基线</button>
          <p v-if="selectedVersion" role="status">已选 {{ selectedBaseline?.name }} · 批准版本 {{ selectedVersion.version_no }}。</p>
        </section>
        <section aria-labelledby="evidence-title"><h2 id="evidence-title">3. 逐项编写有来源的问题</h2>
          <p>先在项目证据页完成人工资格核定，再在每张卡片中勾选与原固定文档一致的证据。可点击原文位置核对，不要把建议直接当事实。</p>
          <p><RouterLink :to="{ name: 'project-evidence', params: { projectId: route.params.projectId } }">管理项目证据及资格</RouterLink></p>
          <p v-if="!eligible.length" role="status">当前已加载资料中，没有与所选固定文档匹配的 ELIGIBLE 项目证据。</p>
          <button v-if="evidenceCursor" type="button" :disabled="lookupBusy || !!pending" @click="moreEvidence">加载更多证据</button>
          <p v-if="selectedEvidence" class="located"><strong>原文位置：</strong>{{ selectedEvidence.display_label }} · 固定版本 {{ selectedEvidence.document_version_no }}
            <a :href="selectedEvidence.content_url" target="_blank" rel="noopener noreferrer">打开受权固定版本</a></p>
          <article v-for="(card, index) in cards" :key="card.id" class="issue-card">
            <header><h3>问题卡片 {{ index + 1 }}</h3><button type="button" :disabled="!!pending || cards.length === 1" @click="removeCard(index)">移除卡片</button></header>
            <label>问题类型<select v-model="card.type" :disabled="!!pending"><option value="GAP">标准差异</option><option value="MISSING">功能缺失</option>
              <option value="CONFLICT">协议冲突</option><option value="RISK">实施风险</option><option value="SCOPE">范围差异</option>
              <option value="NEED_CONFIRM">待人工确认</option></select></label>
            <label>标题<input v-model="card.title" required maxlength="255" :disabled="!!pending" placeholder="例如：物料编码映射规则待确认" /></label>
            <label>问题陈述<textarea v-model="card.statement" required maxlength="4000" :disabled="!!pending" placeholder="写明实际调研或协议中发现的具体情况，不粘贴整篇原文" /></label>
            <label>影响<textarea v-model="card.impact" required maxlength="2000" :disabled="!!pending" placeholder="说明对数据、接口、流程或上线的影响" /></label>
            <div class="two"><label>严重度<select v-model="card.severity" :disabled="!!pending"><option>LOW</option><option>MEDIUM</option><option>HIGH</option><option>CRITICAL</option></select></label>
              <label>优先级<select v-model="card.priority" :disabled="!!pending"><option>LOW</option><option>MEDIUM</option><option>HIGH</option><option>URGENT</option></select></label></div>
            <label>处理建议（非客户决定）<textarea v-model="card.recommendation" maxlength="2000" :required="card.type === 'NEED_CONFIRM'" :disabled="!!pending" placeholder="建议如何核对或处理，可暂不填" /></label>
            <div v-if="card.type === 'NEED_CONFIRM'" class="input-guide">
              <p>请具体说明需要客户或项目成员维护什么信息。下面示例仅说明格式，不代表客户事实。</p>
              <label>需确认的问题<textarea v-model="card.question" required maxlength="2000" :disabled="!!pending" placeholder="例如：历史物料编码如何与新系统编码对应？" /></label>
              <label>需填写的信息名称<input v-model="card.fieldName" required maxlength="128" :disabled="!!pending" placeholder="例如：旧编码、新编码、映射负责人" /></label>
              <label>填写格式<input v-model="card.fieldFormat" required maxlength="128" :disabled="!!pending" placeholder="例如：两列编码对照表" /></label>
              <label>格式示例<input v-model="card.fieldExample" required maxlength="500" :disabled="!!pending" placeholder="例如：OLD-001 → NEW-001（仅示例）" /></label>
              <label>可选方案 A<input v-model="card.optionA" required maxlength="255" :disabled="!!pending" placeholder="例如：沿用旧编码并建立映射" /></label>
              <label>可选方案 B<input v-model="card.optionB" required maxlength="255" :disabled="!!pending" placeholder="例如：统一切换新编码" /></label>
            </div>
            <fieldset><legend>原文依据（至少一条）</legend><p v-if="!eligible.length">请先核对固定来源并取得合格证据。</p>
              <label v-for="item in eligible" :key="item.evidence_id" class="choice"><input v-model="card.evidenceIds" type="checkbox"
                :value="item.evidence_id" :disabled="!!pending" />{{ item.display_label }}
                <button type="button" :disabled="lookupBusy" @click="locate(item)">定位原文</button></label></fieldset>
            <fieldset v-if="selectedVersion"><legend>关联标准能力（可选）</legend>
              <label v-for="item in capabilityItems.filter(entry => entry.state === 'AVAILABLE')" :key="item.capability_item_id" class="choice">
                <input v-model="card.capabilityIds" type="checkbox" :value="item.capability_item_id" :disabled="!!pending" />{{ item.name }}</label>
              <button v-if="capabilityCursor" type="button" :disabled="lookupBusy || !!pending" @click="moreCapabilities">加载更多能力条目</button></fieldset>
          </article>
          <button type="button" :disabled="!!pending || cards.length >= 500" @click="addCard">增加一张问题卡片</button>
        </section>
        <section aria-labelledby="submit-title"><h2 id="submit-title">4. 核对并保存草稿</h2>
          <p>提交后只形成不可覆盖的 DRAFT 版本；评审、客户确认和正式化在独立流程进行。</p>
          <p v-if="pending" role="status">原操作已保存。结果未确认时，请先核对版本列表；重试只使用原内容、原版本标记和原操作号。</p>
          <label v-if="pending && !locked"><input v-model="retryConfirmed" type="checkbox" :disabled="writeBusy" />我已核对版本列表，按原操作号重试</label>
          <button type="button" :disabled="writeBusy || busy || locked || (pending ? !retryConfirmed
            : sourceMatch !== true || !selectedVersion || !eligible.length)" @click="submit">{{ writeBusy ? '正在保存…' : pending ? '按原操作重试' : '保存 DRAFT 问题版本' }}</button>
        </section>
      </template>
    </template>
  </section>
</template>

<style scoped>
.handover-version-create { max-width: 68rem; margin: 1rem auto; padding: 1.5rem; background: #fff; border-radius: 1rem; }
.handover-version-create section { margin: 1.5rem 0; }.handover-version-create label { display: grid; gap: .3rem; margin: .6rem 0; }
.handover-version-create input:not([type="checkbox"]), .handover-version-create textarea, .handover-version-create select { width: 100%; padding: .55rem; }
.handover-version-create textarea { min-height: 5rem; }.handover-version-create ul, .handover-version-create ol { display: grid; gap: .45rem; }
.issue-card { border: 1px solid #d8dee7; border-radius: .75rem; padding: 1rem; margin: 1rem 0; }
.issue-card header { display: flex; justify-content: space-between; align-items: center; }.two { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }
.choice { display: flex !important; flex-wrap: wrap; align-items: center; gap: .5rem !important; }.choice input { width: auto; }
.fact-warning, .input-guide { padding: .8rem 1rem; background: #fff8e9; border-left: .3rem solid #d29b42; }
.located, .picker { padding: .8rem; background: #eef7f1; }.handover-version-create [role="alert"] { color: #a21d25; }
</style>
