<script setup lang="ts">
import { inject, onMounted, onUnmounted, ref, toRaw } from "vue";
import { RouterLink } from "vue-router";

import { SessionClient } from "@/modules/auth/api/sessionClient";
import { sessionClientKey } from "@/modules/auth/api/sessionContext";
import { EvidenceListClient, type EvidenceSummary } from "@/modules/evidence/api/evidenceListClient";
import { EvidenceViewerClient, type EvidenceViewerDescriptor } from "@/modules/evidence/api/evidenceViewerClient";
import { EvidenceEligibilityClient } from "@/modules/evidence/api/evidenceEligibilityClient";

const props = defineProps<{ session?: SessionClient; listClient?: EvidenceListClient;
  viewerClient?: EvidenceViewerClient; eligibilityClient?: EvidenceEligibilityClient }>();
const session = toRaw(props.session ?? inject(sessionClientKey, null) ?? new SessionClient());
const lists = toRaw(props.listClient ?? new EvidenceListClient());
const viewers = toRaw(props.viewerClient ?? new EvidenceViewerClient());
const eligibility = toRaw(props.eligibilityClient ?? new EvidenceEligibilityClient(session));
type Selected = Readonly<{ evidence: EvidenceSummary; viewer: EvidenceViewerDescriptor }>;
const items = ref<readonly EvidenceSummary[]>([]);
const selected = ref<readonly Selected[]>([]);
const cursor = ref<string | null>(null);
const loaded = ref(false);
const busy = ref(false);
const error = ref("");
let generation = 0; let mounted = true;
const mayRead = () => mounted && session.view?.deployment_role === "DEPLOYMENT_ADMIN"
  && !session.view.password_change_required;
const selectedIds = () => new Set(selected.value.map((entry) => entry.evidence.evidence_id));
const documentVersionIds = () => [...new Set(selected.value.map((entry) => entry.viewer.document_version_id))];

async function load(refresh = false) {
  if (!mayRead() || busy.value || !refresh && loaded.value && !cursor.value) return;
  if (refresh) {
    generation += 1; items.value = []; selected.value = []; cursor.value = null; loaded.value = false;
  }
  const after = cursor.value, run = ++generation;
  busy.value = true; error.value = "";
  try {
    const page = await lists.list({ kind: "GLOBAL" }, after);
    if (!mounted || run !== generation || !mayRead()) return;
    if (page.items.some((item) => items.value.some((prior) => prior.evidence_id === item.evidence_id))) {
      throw new Error("duplicate Evidence in pagination");
    }
    items.value = [...items.value, ...page.items]; cursor.value = page.next_cursor; loaded.value = true;
  } catch {
    if (mounted && run === generation) error.value = "无法确认全局证据列表；请重新读取。";
  } finally { if (mounted && run === generation) busy.value = false; }
}

async function choose(item: EvidenceSummary) {
  if (!mayRead() || busy.value || item.eligibility_state !== "ELIGIBLE"
    || selectedIds().has(item.evidence_id)
    || !items.value.some((candidate) => candidate.evidence_id === item.evidence_id)
    || selected.value.length >= 500) return;
  const run = ++generation;
  busy.value = true; error.value = "";
  try {
    const viewer = await viewers.get({ kind: "GLOBAL" }, item.evidence_id);
    const state = await eligibility.currentGlobal(item.evidence_id);
    if (!mounted || run !== generation || !mayRead()) return;
    if (viewer.evidence_id !== item.evidence_id || viewer.document_id !== item.document_id
      || viewer.document_version_id !== item.document_version_id
      || state.evidence_id !== item.evidence_id || state.document_id !== viewer.document_id
      || state.document_version_id !== viewer.document_version_id
      || state.eligibility_state !== "ELIGIBLE"
      || documentVersionIds().length >= 100
        && !documentVersionIds().includes(viewer.document_version_id)) {
      throw new Error("source no longer eligible or exceeds limit");
    }
    selected.value = [...selected.value, { evidence: item, viewer }];
  } catch {
    if (mounted && run === generation) error.value = "固定来源已变化、不可用或超过集合限制；请刷新列表后重选。";
  } finally { if (mounted && run === generation) busy.value = false; }
}
function remove(evidenceId: string) {
  if (busy.value) return;
  selected.value = selected.value.filter((entry) => entry.evidence.evidence_id !== evidenceId);
  error.value = "";
}
onMounted(() => { void load(true); });
onUnmounted(() => { mounted = false; generation += 1; selected.value = []; });
</script>

<template>
  <section class="global-source-picker" aria-labelledby="picker-title" :aria-busy="busy">
    <p class="section-kicker">全局参考方案</p>
    <h1 id="picker-title">多来源核查候选</h1>
    <p>仅部署管理员可选择。此页是只读候选集合，不进行脱敏确认；最终仍须逐项打开原文并由本人判断。</p>
    <p><RouterLink to="/admin/evidence">返回全局证据</RouterLink></p>
    <template v-if="!mayRead()">
      <p role="status">需要当前 DeploymentAdmin 登录且已完成密码设置。</p>
      <RouterLink to="/login">前往账户与登录</RouterLink>
    </template>
    <template v-else>
      <button type="button" :disabled="busy" @click="load(true)">重新读取并清空候选</button>
      <p v-if="busy" role="status">正在核验来源…</p>
      <p v-if="error" role="alert">{{ error }}</p>
      <p v-if="loaded && !items.length">暂无全局证据。</p>
      <ol aria-label="可选全局证据">
        <li v-for="item in items" :key="item.evidence_id">
          {{ item.display_label }} · {{ item.eligibility_state === 'ELIGIBLE' ? '当前列表显示可用' : '当前列表不可选' }}
          <button type="button" :disabled="busy || item.eligibility_state !== 'ELIGIBLE'
            || selectedIds().has(item.evidence_id) || selected.length >= 500"
            @click="choose(item)">加入核查候选</button>
        </li>
      </ol>
      <button v-if="cursor" type="button" :disabled="busy" @click="load()">继续加载</button>
      <section aria-labelledby="selected-title">
        <h2 id="selected-title">待逐项核查的来源（{{ selected.length }} 条证据、{{ documentVersionIds().length }} 个固定文档版本）</h2>
        <p>选择顺序保留；相同固定文档版本只计一次。当前选择不是预览证明或人工确认，重新读取会清空。</p>
        <ol aria-label="已选固定来源">
          <li v-for="entry in selected" :key="entry.evidence.evidence_id">
            <strong>{{ entry.viewer.display_label }}</strong> · 第 {{ entry.viewer.document_version_no }} 版 ·
            {{ entry.viewer.precision === 'DOCUMENT' ? '整文档' : '解析节点' }}
            <a :href="entry.viewer.content_url" target="_blank" rel="noopener">打开受权固定版本原文</a>
            <button type="button" :disabled="busy" @click="remove(entry.evidence.evidence_id)">移出候选</button>
          </li>
        </ol>
      </section>
      <p role="status">多来源预览/确认尚未接入，本页不能提交；请勿把候选当成已核定资料。</p>
    </template>
  </section>
</template>

<style scoped>
.global-source-picker { max-width: 66rem; margin: 1rem auto; padding: 1.5rem; background: #fff; border-radius: 1rem; }
li { padding: .55rem 0; line-height: 1.6; }
button, a { margin-left: .6rem; }
button:disabled { opacity: .55; cursor: not-allowed; }
[role="alert"] { color: #a21d25; }
</style>
