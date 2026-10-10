<script setup lang="ts">
import { inject, onUnmounted, ref, toRaw, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { sessionClientKey } from "@/modules/auth/api/sessionContext";
import { EvidenceViewerClient, EvidenceViewerClientError, type EvidenceViewerDescriptor } from "@/modules/evidence/api/evidenceViewerClient";
import { HandoverReadClient, HandoverReadError, type HandoverAnalysisItemView, type HandoverAnalysisView,
  type HandoverAnalysisVersionView, type HandoverItemCursor, type HandoverVersionCursor } from "@/modules/handover/api/handoverReadClient";

const props = defineProps<{ session?: SessionClient; handover?: HandoverReadClient; evidence?: EvidenceViewerClient }>();
const session = toRaw(props.session ?? inject(sessionClientKey, null) ?? new SessionClient());
const handover = toRaw(props.handover ?? new HandoverReadClient()); const evidence = toRaw(props.evidence ?? new EvidenceViewerClient());
const identity = session.view; const route = useRoute();
const analysis = ref<HandoverAnalysisView | null>(null); const versions = ref<readonly HandoverAnalysisVersionView[]>([]);
const versionCursor = ref<HandoverVersionCursor | null>(null); const selectedVersion = ref<HandoverAnalysisVersionView | null>(null);
const items = ref<readonly HandoverAnalysisItemView[]>([]); const itemCursor = ref<HandoverItemCursor | null>(null);
const selectedEvidence = ref<EvidenceViewerDescriptor | null>(null); const selectedEvidenceItem = ref("");
const busy = ref(false); const versionBusy = ref(false); const itemBusy = ref(false); const evidenceBusy = ref(false);
const error = ref(""); const versionError = ref(""); const itemError = ref(""); const evidenceError = ref("");
let generation = 0; let itemGeneration = 0; let evidenceGeneration = 0; let mounted = true;
const typeLabels = Object.freeze({ GAP: "差距", MISSING: "缺失", CONFLICT: "冲突", RISK: "风险", SCOPE: "范围", NEED_CONFIRM: "待确认" });

function ids() { return { projectId: typeof route.params.projectId === "string" ? route.params.projectId : "",
  analysisId: typeof route.params.analysisId === "string" ? route.params.analysisId : "" }; }
function mayRead() { return mounted && !!identity && !identity.password_change_required
  && session.view?.user.user_id === identity.user.user_id; }
function clearSelection() { itemGeneration += 1; evidenceGeneration += 1; selectedVersion.value = null; items.value = [];
  itemCursor.value = null; selectedEvidence.value = null; selectedEvidenceItem.value = ""; itemError.value = ""; evidenceError.value = ""; }
async function load() { if (!mayRead() || busy.value) return; const request = ids(); const current = ++generation;
  analysis.value = null; versions.value = []; versionCursor.value = null; clearSelection(); error.value = ""; versionError.value = ""; busy.value = true;
  try { const [root, page] = await Promise.all([handover.getAnalysis(request.projectId, request.analysisId),
    handover.listVersions(request.projectId, request.analysisId)]);
    const latest = ids(); if (!mounted || current !== generation || latest.projectId !== request.projectId
      || latest.analysisId !== request.analysisId || !mayRead()) return;
    analysis.value = root; versions.value = page.items; versionCursor.value = page.next_cursor;
  } catch (failure) { const latest = ids(); if (!mounted || current !== generation || latest.projectId !== request.projectId
    || latest.analysisId !== request.analysisId) return; error.value = failure instanceof HandoverReadError ? failure.message : "暂时无法读取交接分析。";
  } finally { if (mounted && current === generation) busy.value = false; } }
async function loadMoreVersions() { if (!mayRead() || versionBusy.value || !versionCursor.value) return; const request = ids();
  const next = versionCursor.value; const current = ++generation; versionBusy.value = true; versionError.value = "";
  try { const page = await handover.listVersions(request.projectId, request.analysisId, 50, next);
    if (!mounted || current !== generation || ids().projectId !== request.projectId || ids().analysisId !== request.analysisId || !mayRead()) return;
    const known = new Set(versions.value.map(value => value.handover_analysis_version_id));
    if (page.items.some(value => known.has(value.handover_analysis_version_id))) throw new HandoverReadError("HANDOVER_READ_UNAVAILABLE");
    versions.value = Object.freeze([...versions.value, ...page.items]); versionCursor.value = page.next_cursor;
  } catch (failure) { if (mounted && current === generation) { versions.value = []; versionCursor.value = null; clearSelection();
    versionError.value = failure instanceof HandoverReadError ? failure.message : "暂时无法读取版本。"; }
  } finally { if (mounted && current === generation) versionBusy.value = false; } }
async function choose(summary: HandoverAnalysisVersionView) { if (!mayRead() || itemBusy.value) return; const request = ids();
  const current = ++itemGeneration; evidenceGeneration += 1; selectedVersion.value = null; items.value = []; itemCursor.value = null;
  selectedEvidence.value = null; selectedEvidenceItem.value = ""; itemError.value = ""; evidenceError.value = ""; itemBusy.value = true;
  try { const [detail, page] = await Promise.all([handover.getVersion(request.projectId, request.analysisId,
    summary.handover_analysis_version_id), handover.listItems(request.projectId, request.analysisId,
    summary.handover_analysis_version_id)]);
    if (!mounted || current !== itemGeneration || ids().projectId !== request.projectId || ids().analysisId !== request.analysisId
      || !mayRead()) return; selectedVersion.value = detail; items.value = page.items; itemCursor.value = page.next_cursor;
  } catch (failure) { if (mounted && current === itemGeneration) itemError.value = failure instanceof HandoverReadError
    ? failure.message : "暂时无法读取问题清单。";
  } finally { if (mounted && current === itemGeneration) itemBusy.value = false; } }
async function loadMoreItems() { if (!selectedVersion.value || !itemCursor.value || itemBusy.value) return; const request = ids();
  const versionId = selectedVersion.value.handover_analysis_version_id; const next = itemCursor.value; const current = ++itemGeneration;
  itemBusy.value = true; itemError.value = "";
  try { const page = await handover.listItems(request.projectId, request.analysisId, versionId, 50, next);
    if (!mounted || current !== itemGeneration || selectedVersion.value?.handover_analysis_version_id !== versionId || !mayRead()) return;
    const known = new Set(items.value.map(value => value.analysis_item_id)); if (page.items.some(value => known.has(value.analysis_item_id)))
      throw new HandoverReadError("HANDOVER_READ_UNAVAILABLE"); items.value = Object.freeze([...items.value, ...page.items]); itemCursor.value = page.next_cursor;
  } catch (failure) { if (mounted && current === itemGeneration) { items.value = []; itemCursor.value = null; selectedEvidence.value = null;
    itemError.value = failure instanceof HandoverReadError ? failure.message : "暂时无法读取问题清单。"; }
  } finally { if (mounted && current === itemGeneration) itemBusy.value = false; } }
async function locate(item: HandoverAnalysisItemView, evidenceId: string) { if (!mayRead() || evidenceBusy.value
    || !items.value.some(value => value.analysis_item_id === item.analysis_item_id && value.evidence_refs.includes(evidenceId))) return;
  const request = ids(); const current = ++evidenceGeneration; selectedEvidence.value = null; selectedEvidenceItem.value = "";
  evidenceError.value = ""; evidenceBusy.value = true;
  try { const value = await evidence.get({ kind: "PROJECT", projectId: request.projectId }, evidenceId);
    if (!mounted || current !== evidenceGeneration || ids().projectId !== request.projectId || ids().analysisId !== request.analysisId
      || !items.value.some(entry => entry.analysis_item_id === item.analysis_item_id) || !mayRead()) return;
    selectedEvidence.value = value; selectedEvidenceItem.value = item.analysis_item_id;
  } catch (failure) { if (mounted && current === evidenceGeneration) evidenceError.value = failure instanceof EvidenceViewerClientError
    ? failure.message : "暂时无法定位原文。";
  } finally { if (mounted && current === evidenceGeneration) evidenceBusy.value = false; } }
watch(() => [route.params.projectId, route.params.analysisId], () => { generation += 1; clearSelection(); busy.value = false; void load(); }, { immediate: true });
onUnmounted(() => { mounted = false; generation += 1; itemGeneration += 1; evidenceGeneration += 1; });
</script>

<template>
  <section class="handover-detail" aria-labelledby="handover-detail-title" :aria-busy="busy">
    <p class="section-kicker">项目交接</p><h1 id="handover-detail-title">交接分析版本与问题清单</h1>
    <p class="fact-warning"><strong>候选问题不是正式业务事实。</strong> 原文定位、人工补充、评审批准是彼此独立的动作。</p>
    <p><RouterLink :to="{ name: 'project-handover', params: { projectId: route.params.projectId } }">返回交接分析列表</RouterLink></p>
    <template v-if="!identity"><p role="status">尚未读取当前身份。请先登录。</p></template>
    <template v-else-if="identity.password_change_required"><p role="status">当前账户须先修改密码，暂不能读取交接分析。</p></template>
    <template v-else>
      <button type="button" :disabled="busy" @click="load()">{{ busy ? "正在读取…" : "刷新分析与版本" }}</button>
      <p v-if="error" role="alert">{{ error }}</p>
      <dl v-if="analysis"><dt>分析目的</dt><dd>{{ analysis.analysis_purpose }}</dd><dt>状态</dt><dd>{{ analysis.state }}</dd>
        <dt>正式版本</dt><dd>{{ analysis.current_approved_version_ref ?? "尚未形成" }}</dd><dt>版本标记</dt><dd>{{ analysis.etag }}</dd></dl>
      <section v-if="analysis" aria-labelledby="handover-versions-title"><h2 id="handover-versions-title">固定版本</h2>
        <p v-if="!versions.length">暂无可见版本。</p><p v-if="versionError" role="alert">{{ versionError }}</p>
        <ol><li v-for="value in versions" :key="value.handover_analysis_version_id"><strong>版本 {{ value.version_no }}</strong>
          <span> · {{ value.state }} · {{ value.declared_item_count }} 项问题</span>
          <button type="button" :disabled="itemBusy" @click="choose(value)">查看版本 {{ value.version_no }} 的问题</button></li></ol>
        <button v-if="versionCursor" type="button" :disabled="versionBusy" @click="loadMoreVersions">加载更多版本</button>
      </section>
      <section v-if="selectedVersion || itemBusy || itemError" aria-labelledby="handover-items-title"><h2 id="handover-items-title">问题卡片</h2>
        <p v-if="selectedVersion">固定版本 {{ selectedVersion.version_no }}；仅显示服务器授权的引用，不复制资料原文。</p>
        <details v-if="selectedVersion"><summary>查看固定输入引用</summary>
          <ul><li v-for="source in selectedVersion.source_documents" :key="source.document_version_id">文档版本 {{ source.document_version_id }} ·
            <RouterLink :to="{ name: 'project-document-detail', params: { projectId: route.params.projectId,
              documentId: source.document_id } }">查看受权文档历史</RouterLink></li></ul>
          <ul><li v-for="task in selectedVersion.ai_tasks" :key="task.ai_task_id">AI任务 {{ task.ai_task_id }} ·
            <RouterLink :to="{ name: 'project-ai-task-detail', params: { projectId: route.params.projectId,
              taskId: task.ai_task_id } }">查看任务与非正式建议状态</RouterLink></li></ul>
        </details>
        <p v-if="itemBusy" role="status">正在读取固定版本与问题清单…</p><p v-if="itemError" role="alert">{{ itemError }}</p>
        <p v-if="selectedVersion && !items.length && !itemBusy">该版本没有可见问题。</p>
        <article v-for="item in items" :key="item.analysis_item_id" class="issue-card">
          <header><strong>{{ typeLabels[item.item_type] }}：{{ item.title }}</strong><span>{{ item.state }} · {{ item.severity }}/{{ item.priority }}</span></header>
          <p>{{ item.statement }}</p><p><strong>影响：</strong>{{ item.impact }}</p><p v-if="item.recommendation"><strong>建议：</strong>{{ item.recommendation }}</p>
          <section v-if="item.item_type === 'NEED_CONFIRM'" class="input-guide"><h3>需要人工确认</h3>
            <p><strong>问题：</strong>{{ item.confirmation_question }}</p><p>请维护以下信息；示例仅说明格式，不是客户事实。</p>
            <ul><li v-for="field in item.required_input_spec.fields" :key="field.name"><strong>{{ field.name }}</strong>
              <span> · {{ field.required ? '必填' : '选填' }} · 格式：{{ field.format }} · 示例：{{ field.example }}</span></li></ul>
            <p><strong>可选方案：</strong></p><ul><li v-for="option in item.options" :key="option.option_code">{{ option.label }}<template v-if="option.description">：{{ option.description }}</template></li></ul>
          </section>
          <p v-if="item.source_missing" role="status">当前项目资料缺失；必须由 Action 待办承接，不能用空白输入代替。</p>
          <div v-if="item.evidence_refs.length" class="evidence-actions"><span>原文依据：</span>
            <button v-for="ref in item.evidence_refs" :key="ref" type="button" :disabled="evidenceBusy" @click="locate(item, ref)">定位原文 {{ ref }}</button></div>
          <p v-else>本项标记为资料缺失，没有可定位的 Evidence。</p>
          <section v-if="selectedEvidence && selectedEvidenceItem === item.analysis_item_id" class="located-source">
            <h3>已核验的原文位置</h3><p>{{ selectedEvidence.display_label }} · 固定文档版本 {{ selectedEvidence.document_version_no }}</p>
            <p v-if="selectedEvidence.short_preview">短提示：{{ selectedEvidence.short_preview }}（不是权威正文）</p>
            <a :href="selectedEvidence.content_url" target="_blank" rel="noopener noreferrer">打开受权固定版本</a>
          </section>
        </article>
        <p v-if="evidenceError" role="alert">{{ evidenceError }}</p>
        <button v-if="itemCursor" type="button" :disabled="itemBusy" @click="loadMoreItems">加载更多问题</button>
      </section>
    </template>
  </section>
</template>

<style scoped>
.handover-detail { max-width: 60rem; margin: 1rem auto; padding: 1.5rem; background: #fff; border-radius: 1rem; }
.handover-detail dl { display: grid; grid-template-columns: 7rem 1fr; gap: .5rem 1rem; }.handover-detail dd { margin: 0; overflow-wrap: anywhere; }
.handover-detail ol { display: grid; gap: .6rem; }.handover-detail ol li { display: flex; flex-wrap: wrap; gap: .5rem; align-items: center; }
.issue-card { display: grid; gap: .45rem; margin: 1rem 0; padding: 1rem; border: 1px solid #d8dee7; border-radius: .75rem; overflow-wrap: anywhere; }
.issue-card header { display: flex; justify-content: space-between; gap: 1rem; }.input-guide { padding: .8rem; background: #fff8e9; border-radius: .5rem; }
.evidence-actions { display: flex; flex-wrap: wrap; gap: .5rem; align-items: center; }.located-source { padding: .8rem; background: #eef7f1; }
.fact-warning { padding: .8rem 1rem; border-left: .3rem solid #d29b42; background: #fff8e9; }.handover-detail [role="alert"] { color: #a21d25; }
</style>
