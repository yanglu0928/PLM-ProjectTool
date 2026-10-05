<script setup lang="ts">
import { inject, onUnmounted, ref, toRaw, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";
import { SessionClient } from "@/modules/auth/api/sessionClient"; import { sessionClientKey } from "@/modules/auth/api/sessionContext";
import { EvidenceViewerClient, EvidenceViewerClientError, type EvidenceViewerDescriptor } from "@/modules/evidence/api/evidenceViewerClient";
import { HandoverActionReadClient, HandoverActionReadError, type HandoverActionCursor,
  type HandoverActionDetail, type HandoverActionSummary } from "@/modules/handover/api/handoverActionReadClient";
const props = defineProps<{ session?: SessionClient; actions?: HandoverActionReadClient; evidence?: EvidenceViewerClient }>();
const session = toRaw(props.session ?? inject(sessionClientKey, null) ?? new SessionClient());
const actions = toRaw(props.actions ?? new HandoverActionReadClient()); const evidence = toRaw(props.evidence ?? new EvidenceViewerClient());
const identity = session.view; const route = useRoute(); const items = ref<readonly HandoverActionSummary[]>([]);
const cursor = ref<HandoverActionCursor | null>(null); const loaded = ref(false); const busy = ref(false); const error = ref("");
const detail = ref<HandoverActionDetail | null>(null); const detailBusy = ref(false); const detailError = ref("");
const located = ref<EvidenceViewerDescriptor | null>(null); const locationError = ref(""); const locationBusy = ref(false);
let generation = 0; let detailGeneration = 0; let locationGeneration = 0; let mounted = true;
const stateLabels = Object.freeze({ OPEN: "待开始", IN_PROGRESS: "处理中", SUBMITTED: "已提交待验证", VERIFIED: "已验证待关闭", CLOSED: "已关闭", CANCELLED: "已取消" });
function projectId() { return typeof route.params.projectId === "string" ? route.params.projectId : ""; }
function mayRead() { return mounted && !!identity && !identity.password_change_required && session.view?.user.user_id === identity.user.user_id; }
function clearDetail() { detailGeneration += 1; locationGeneration += 1; detail.value = null; detailError.value = ""; located.value = null; locationError.value = ""; }
async function load(next: HandoverActionCursor | null = null, replace = false) { if (!mayRead() || busy.value) return; const project = projectId(); const current = ++generation;
  if (replace) { items.value = []; cursor.value = null; loaded.value = false; clearDetail(); } busy.value = true; error.value = "";
  try { const page = await actions.list(project, 50, next); if (!mounted || current !== generation || projectId() !== project || !mayRead()) return;
    const known = new Set(items.value.map(item => item.action_item_id)); if (page.items.some(item => known.has(item.action_item_id))) throw new HandoverActionReadError("HANDOVER_ACTION_UNAVAILABLE");
    items.value = Object.freeze([...items.value, ...page.items]); cursor.value = page.next_cursor; loaded.value = true;
  } catch (failure) { if (mounted && current === generation) { items.value = []; cursor.value = null; loaded.value = false; clearDetail();
    error.value = failure instanceof HandoverActionReadError ? failure.message : "暂时无法读取交接待办。"; } }
  finally { if (mounted && current === generation) busy.value = false; } }
async function show(item: HandoverActionSummary) { if (!mayRead() || detailBusy.value) return; const project = projectId(); const current = ++detailGeneration;
  locationGeneration += 1; detail.value = null; located.value = null; locationError.value = ""; detailError.value = ""; detailBusy.value = true;
  try { const value = await actions.get(project, item.action_item_id); if (!mounted || current !== detailGeneration || projectId() !== project || !mayRead()) return; detail.value = value; }
  catch (failure) { if (mounted && current === detailGeneration) detailError.value = failure instanceof HandoverActionReadError ? failure.message : "暂时无法读取待办详情。"; }
  finally { if (mounted && current === detailGeneration) detailBusy.value = false; } }
async function locate(evidenceId: string) { if (!detail.value || !detail.value.evidence.some(item => item.evidence_id === evidenceId) || locationBusy.value) return;
  const project = projectId(); const actionId = detail.value.action_item_id; const current = ++locationGeneration; located.value = null; locationError.value = ""; locationBusy.value = true;
  try { const value = await evidence.get({ kind: "PROJECT", projectId: project }, evidenceId); if (!mounted || current !== locationGeneration
    || projectId() !== project || detail.value?.action_item_id !== actionId || !mayRead()) return; located.value = value; }
  catch (failure) { if (mounted && current === locationGeneration) locationError.value = failure instanceof EvidenceViewerClientError ? failure.message : "暂时无法定位待办依据。"; }
  finally { if (mounted && current === locationGeneration) locationBusy.value = false; } }
watch(() => route.params.projectId, () => { generation += 1; items.value = []; cursor.value = null; loaded.value = false; busy.value = false; error.value = ""; clearDetail(); void load(null, true); }, { immediate: true });
onUnmounted(() => { mounted = false; generation += 1; clearDetail(); });
</script>
<template><section class="action-workbench" aria-labelledby="action-title" :aria-busy="busy">
  <p class="section-kicker">项目交接</p><h1 id="action-title">交接待办与验证状态</h1>
  <p class="fact-warning"><strong>已提交不等于已完成。</strong> SUBMITTED 必须经过受权验证，VERIFIED 仍须正式关闭并形成 Resolution Trace。</p>
  <p><RouterLink :to="{ name: 'project-handover', params: { projectId: route.params.projectId } }">返回交接分析</RouterLink></p>
  <template v-if="!identity"><p role="status">尚未读取当前身份。请先登录。</p></template>
  <template v-else-if="identity.password_change_required"><p role="status">当前账户须先修改密码，暂不能读取交接待办。</p></template>
  <template v-else><button type="button" :disabled="busy" @click="load(null, true)">{{ busy ? '正在读取…' : '刷新交接待办' }}</button>
    <p v-if="error" role="alert">{{ error }}</p><p v-if="loaded && !items.length">当前项目没有可见待办。</p>
    <ol v-if="items.length" aria-label="交接待办"><li v-for="item in items" :key="item.action_item_id">
      <strong>{{ item.title }}</strong><span>{{ stateLabels[item.action_state] }} · {{ item.priority }} · 截止 {{ new Date(item.due_at).toLocaleString('zh-CN') }}</span>
      <span>负责人：{{ item.owner_ref }}</span><button type="button" :disabled="detailBusy" @click="show(item)">查看待办详情</button></li></ol>
    <button v-if="cursor" type="button" :disabled="busy" @click="load(cursor)">加载更多待办</button>
    <p v-if="detailBusy" role="status">正在读取待办详情…</p><p v-if="detailError" role="alert">{{ detailError }}</p>
    <article v-if="detail" class="action-detail"><h2>{{ detail.title }}</h2><p><strong>当前状态：</strong>{{ stateLabels[detail.action_state] }}</p>
      <p v-if="detail.action_state === 'SUBMITTED'" class="status-warning">响应已经提交，但尚未验证和关闭。</p>
      <p v-if="detail.action_state === 'VERIFIED'" class="status-warning">响应已经验证，但尚未关闭，也未形成最终 Resolution Trace。</p>
      <p><strong>创建原因：</strong>{{ detail.created_reason }}</p><p v-if="detail.human_source_reason"><strong>人工来源：</strong>{{ detail.human_source_reason }}</p>
      <section><h3>需要维护的信息</h3><ul><li v-for="field in detail.requested_input_spec.fields" :key="field.name"><strong>{{ field.name }}</strong>
        · {{ field.required ? '必填' : '选填' }} · {{ field.format }} · 示例：{{ field.example }}</li></ul></section>
      <section><h3>响应文档</h3><p v-if="!detail.responses.length">尚未提交响应文档。</p><ul><li v-for="response in detail.responses" :key="response.document_version_id">
        固定版本 {{ response.document_version_id }} · <RouterLink :to="{ name: 'project-document-detail', params: { projectId: route.params.projectId,
          documentId: response.document_id } }">查看受权文档历史</RouterLink></li></ul></section>
      <section><h3>依据</h3><p v-if="!detail.evidence.length">尚无提交、验证或解决依据。</p><div class="evidence-actions">
        <button v-for="entry in detail.evidence" :key="entry.evidence_id" type="button" :disabled="locationBusy" @click="locate(entry.evidence_id)">
          定位{{ entry.purpose }}依据</button></div><p v-if="locationError" role="alert">{{ locationError }}</p>
        <div v-if="located" class="located"><strong>已核验位置：</strong>{{ located.display_label }}
          <a :href="located.content_url" target="_blank" rel="noopener noreferrer">打开固定版本</a></div></section>
      <p><strong>最新状态事件：</strong>{{ detail.current_event.from_state ?? '初始' }} → {{ detail.current_event.to_state }}；{{ detail.current_event.reason }}</p>
    </article>
  </template></section></template>
<style scoped>.action-workbench{max-width:58rem;margin:1rem auto;padding:1.5rem;background:#fff;border-radius:1rem}.action-workbench ol{display:grid;gap:.7rem;padding:0;list-style:none}.action-workbench li{display:grid;gap:.35rem;padding:1rem;border:1px solid #d8dee7;border-radius:.7rem;overflow-wrap:anywhere}.action-detail{margin-top:1rem;padding:1rem;border:1px solid #aebfc8;border-radius:.8rem}.fact-warning,.status-warning{padding:.8rem;background:#fff8e9;border-left:.3rem solid #d29b42}.evidence-actions{display:flex;gap:.5rem;flex-wrap:wrap}.located{margin-top:.7rem;padding:.7rem;background:#eef7f1}.action-workbench [role=alert]{color:#a21d25}</style>
