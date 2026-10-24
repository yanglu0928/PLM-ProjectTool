<script setup lang="ts">
import { computed, inject, onMounted, onUnmounted, ref, shallowRef, toRaw, watch } from "vue";
import { RouterLink, useRoute, useRouter } from "vue-router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { sessionClientKey } from "@/modules/auth/api/sessionContext";
import { CapabilityReadClient, type CapabilityBaseline } from "@/modules/capability/api/capabilityReadClient";
import { CapabilityVersionCreateClient, CapabilityVersionCreateError, normalizeCapabilityVersionItems,
  type CapabilityVersionItemDraft } from "@/modules/capability/api/capabilityVersionCreateClient";
import { capabilitySourceCollectionRef } from "@/modules/capability/api/capabilitySourceCollection";
import { DocumentReadClient, type DocumentView, type DocumentVersionView } from "@/modules/document/api/documentReadClient";
import { EvidenceListClient, type EvidenceSummary } from "@/modules/evidence/api/evidenceListClient";
import { EvidenceEligibilityClient } from "@/modules/evidence/api/evidenceEligibilityClient";

const props = defineProps<{ session?: SessionClient; baselines?: CapabilityReadClient;
  documents?: DocumentReadClient; evidence?: EvidenceListClient;
  eligibility?: EvidenceEligibilityClient; creator?: CapabilityVersionCreateClient }>();
const session = toRaw(props.session ?? inject(sessionClientKey, null) ?? new SessionClient());
const baselines = toRaw(props.baselines ?? new CapabilityReadClient());
const documents = toRaw(props.documents ?? new DocumentReadClient());
const evidence = toRaw(props.evidence ?? new EvidenceListClient());
const eligibility = toRaw(props.eligibility ?? new EvidenceEligibilityClient(session));
const creator = toRaw(props.creator ?? new CapabilityVersionCreateClient(session));
const route = useRoute(); const router = useRouter(); const actorId = session.view?.user.user_id;
type Chosen = { readonly document: DocumentView; readonly version: DocumentVersionView };
type Pending = { readonly actor: string; readonly baselineId: string; readonly etag: string;
  readonly item: CapabilityVersionItemDraft; readonly key: string };
const baseline = shallowRef<CapabilityBaseline | null>(null);
const docs = ref<readonly DocumentView[]>([]); const docsCursor = ref<string | null>(null);
const activeDoc = shallowRef<DocumentView | null>(null);
const versions = ref<readonly DocumentVersionView[]>([]); const versionsCursor = ref<string | null>(null);
const chosen = shallowRef<readonly Chosen[]>([]);
const evidenceItems = ref<readonly EvidenceSummary[]>([]); const evidenceCursor = ref<string | null>(null);
const chosenEvidence = ref<readonly string[]>([]);
const code = ref(""); const domain = ref(""); const moduleName = ref(""); const feature = ref("");
const name = ref(""); const description = ref(""); const boundary = ref("");
const prerequisites = ref(""); const interfaces = ref("");
const itemState = ref<"AVAILABLE" | "WITHDRAWN">("AVAILABLE");
const attested = ref(false); const busy = ref(false); const loading = ref(false);
const error = ref(""); const pending = shallowRef<Pending | null>(null);
const confirmRetry = ref(false); const locked = ref(false); const createdId = ref("");
let mounted = true; let generation = 0;
function baselineId(): string { return typeof route.params.baselineId === "string" ? route.params.baselineId : ""; }
function mayCreate(): boolean {
  const view = session.view;
  return mounted && !!actorId && view?.user.user_id === actorId && !view.password_change_required
    && view.deployment_role === "DEPLOYMENT_ADMIN" && session.canSubmit;
}
function storageKey(): string { return `plm.cap.version.create.pending.${actorId ?? "none"}.${baselineId()}`; }
function restore(): void {
  if (!actorId) return;
  try {
    const raw = window.sessionStorage.getItem(storageKey()); if (!raw) return;
    const value: unknown = JSON.parse(raw);
    if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("invalid");
    const entry = value as Record<string, unknown>;
    if (Object.keys(entry).length !== 5 || entry.actor !== actorId || entry.baselineId !== baselineId()
      || typeof entry.etag !== "string" || !/^"v(?:0|[1-9]\d*)"$/.test(entry.etag)
      || typeof entry.key !== "string" || !/^[\x20-\x7e]{16,128}$/.test(entry.key)) throw new Error("invalid");
    const item = normalizeCapabilityVersionItems([entry.item])[0]!;
    pending.value = { actor: actorId, baselineId: baselineId(), etag: entry.etag,
      item, key: entry.key };
  } catch { locked.value = true; error.value = "原操作记录无法安全读取；请核对版本历史和审计，勿换号重建。"; }
}
function resetProjection(): void {
  generation += 1; baseline.value = null; docs.value = []; docsCursor.value = null;
  activeDoc.value = null; versions.value = []; versionsCursor.value = null;
  chosen.value = []; evidenceItems.value = []; evidenceCursor.value = null;
  chosenEvidence.value = []; attested.value = false; loading.value = false;
  if (pending.value || busy.value) error.value = "会话或基线已变化；请核对原操作历史，勿换号重建。";
}
async function load(): Promise<void> {
  resetProjection(); if (!mayCreate()) return;
  const request = ++generation; loading.value = true; error.value = "";
  try {
    const [current, docPage, evPage] = await Promise.all([
      baselines.getBaseline(baselineId()), documents.list({ kind: "GLOBAL" }),
      evidence.list({ kind: "GLOBAL" }),
    ]);
    if (!mounted || request !== generation || !mayCreate()) return;
    if (current.state !== "ACTIVE") throw new Error("基线已归档，不能写入新版本。");
    baseline.value = current;
    docs.value = docPage.items.filter(item => item.scope === "GLOBAL"
      && item.category === "STANDARD_CAPABILITY" && item.state === "ACTIVE");
    docsCursor.value = docPage.next_cursor;
    evidenceItems.value = evPage.items; evidenceCursor.value = evPage.next_cursor;
  } catch (failure) { if (request === generation) error.value = failure instanceof Error
    ? failure.message : "暂时无法读取能力来源。"; }
  finally { if (request === generation) loading.value = false; }
}
async function moreDocs(): Promise<void> {
  const cursor = docsCursor.value; if (!cursor || loading.value || !mayCreate() || pending.value) return;
  const request = generation; loading.value = true;
  try {
    const page = await documents.list({ kind: "GLOBAL" }, cursor);
    if (request !== generation || !mayCreate()) return;
    const added = page.items.filter(item => item.scope === "GLOBAL"
      && item.category === "STANDARD_CAPABILITY" && item.state === "ACTIVE");
    if (new Set([...docs.value, ...added].map(item => item.document_id)).size
      !== docs.value.length + added.length) throw new Error("文档分页出现重复；请刷新。");
    docs.value = [...docs.value, ...added]; docsCursor.value = page.next_cursor;
  } catch (failure) { if (request === generation) error.value = failure instanceof Error ? failure.message : "文档加载失败。"; }
  finally { if (request === generation) loading.value = false; }
}
async function openVersions(doc: DocumentView): Promise<void> {
  if (!mayCreate() || loading.value || pending.value || doc.state !== "ACTIVE") return;
  activeDoc.value = doc; versions.value = []; versionsCursor.value = null;
  await moreVersions(true);
}
async function moreVersions(first = false): Promise<void> {
  const doc = activeDoc.value; if (!doc || loading.value || !mayCreate() || pending.value) return;
  if (!first && !versionsCursor.value) return;
  const request = generation; loading.value = true;
  try {
    const page = await documents.listVersions({ kind: "GLOBAL" }, doc.document_id,
      first ? null : versionsCursor.value);
    if (request !== generation || !mayCreate() || activeDoc.value?.document_id !== doc.document_id) return;
    if (new Set([...versions.value, ...page.items].map(item => item.document_version_id)).size
      !== versions.value.length + page.items.length) throw new Error("版本分页出现重复；请刷新。");
    versions.value = [...versions.value, ...page.items]; versionsCursor.value = page.next_cursor;
  } catch (failure) { if (request === generation) error.value = failure instanceof Error ? failure.message : "版本加载失败。"; }
  finally { if (request === generation) loading.value = false; }
}
function chooseVersion(version: DocumentVersionView): void {
  const doc = activeDoc.value;
  if (!doc || !mayCreate() || pending.value || loading.value || chosen.value.length >= 100
    && !chosen.value.some(item => item.document.document_id === doc.document_id)) return;
  chosen.value = [...chosen.value.filter(item => item.document.document_id !== doc.document_id),
    { document: doc, version }];
  const pairs = new Set(chosen.value.map(item => `${item.document.document_id}/${item.version.document_version_id}`));
  chosenEvidence.value = chosenEvidence.value.filter(id => {
    const value = evidenceItems.value.find(item => item.evidence_id === id);
    return value && pairs.has(`${value.document_id}/${value.document_version_id}`);
  });
  activeDoc.value = null; versions.value = []; versionsCursor.value = null; attested.value = false;
}
function removeSource(documentId: string): void {
  if (pending.value || busy.value) return;
  chosen.value = chosen.value.filter(item => item.document.document_id !== documentId);
  const pairs = new Set(chosen.value.map(item => `${item.document.document_id}/${item.version.document_version_id}`));
  chosenEvidence.value = chosenEvidence.value.filter(id => {
    const value = evidenceItems.value.find(item => item.evidence_id === id);
    return value && pairs.has(`${value.document_id}/${value.document_version_id}`);
  });
  attested.value = false;
}
const eligibleForSources = computed(() => {
  const pairs = new Set(chosen.value.map(item => `${item.document.document_id}/${item.version.document_version_id}`));
  return evidenceItems.value.filter(item => item.eligibility_state === "ELIGIBLE"
    && pairs.has(`${item.document_id}/${item.document_version_id}`));
});
async function moreEvidence(refresh = false): Promise<void> {
  if (!mayCreate() || loading.value || pending.value || !refresh && !evidenceCursor.value) return;
  const request = generation; loading.value = true;
  try {
    const page = await evidence.list({ kind: "GLOBAL" }, refresh ? null : evidenceCursor.value);
    if (request !== generation || !mayCreate()) return;
    const before = refresh ? [] : evidenceItems.value;
    if (new Set([...before, ...page.items].map(item => item.evidence_id)).size
      !== before.length + page.items.length) throw new Error("证据分页出现重复；请刷新。");
    evidenceItems.value = [...before, ...page.items]; evidenceCursor.value = page.next_cursor;
    if (refresh) chosenEvidence.value = [];
  } catch (failure) { if (request === generation) error.value = failure instanceof Error ? failure.message : "证据加载失败。"; }
  finally { if (request === generation) loading.value = false; }
}
function toggleEvidence(id: string): void {
  if (pending.value || busy.value || !eligibleForSources.value.some(item => item.evidence_id === id)) return;
  chosenEvidence.value = chosenEvidence.value.includes(id)
    ? chosenEvidence.value.filter(value => value !== id)
    : chosenEvidence.value.length < 200 ? [...chosenEvidence.value, id] : chosenEvidence.value;
  attested.value = false;
}
function lines(value: string): string[] { return value.split(/\r?\n/).map(line => line.trim()).filter(Boolean); }
async function recheck(item: CapabilityVersionItemDraft, etag: string): Promise<void> {
  const current = await baselines.getBaseline(baselineId());
  if (current.state !== "ACTIVE" || current.etag !== etag) throw new Error("基线版本已变化；请刷新并核对历史。");
  const sourceRef = await capabilitySourceCollectionRef(item.document_refs.map(ref => ref.document_version_id));
  if (sourceRef !== current.source_collection_ref) throw new Error("所选固定来源与基线来源集合不一致。");
  for (const ref of item.document_refs) {
    const doc = await documents.get({ kind: "GLOBAL" }, ref.document_id);
    const version = await documents.getVersion({ kind: "GLOBAL" }, ref.document_id, ref.document_version_id);
    if (doc.state !== "ACTIVE" || doc.category !== "STANDARD_CAPABILITY"
      || version.availability_state !== "AVAILABLE") throw new Error("固定来源现已不可用，请刷新。");
  }
  const pairs = new Set(item.document_refs.map(ref => `${ref.document_id}/${ref.document_version_id}`));
  for (const id of item.evidence_refs) {
    const currentEvidence = await eligibility.currentGlobal(id);
    if (currentEvidence.eligibility_state !== "ELIGIBLE"
      || !pairs.has(`${currentEvidence.document_id}/${currentEvidence.document_version_id}`)) {
      throw new Error("证据资格或同源关系已变化；请重新核对。");
    }
  }
}
async function submit(): Promise<void> {
  if (!mayCreate() || !baseline.value || busy.value || loading.value || locked.value || createdId.value
    || pending.value && !confirmRetry.value) return;
  let attempt = pending.value;
  if (!attempt) {
    if (!attested.value || !chosen.value.length || !chosenEvidence.value.length) return;
    const item: CapabilityVersionItemDraft = {
      stable_item_id: crypto.randomUUID(), capability_code: code.value.trim().toUpperCase(),
      domain_name: domain.value.trim(), module_name: moduleName.value.trim(),
      feature_name: feature.value.trim(), name: name.value.trim(),
      description: description.value.trim(), boundary: boundary.value.trim(),
      prerequisites: lines(prerequisites.value), interface_refs: lines(interfaces.value),
      item_state: itemState.value, document_refs: chosen.value.map(value => ({
        document_id: value.document.document_id, document_version_id: value.version.document_version_id })),
      evidence_refs: chosenEvidence.value,
    };
    try { normalizeCapabilityVersionItems([item]); }
    catch (failure) { error.value = failure instanceof Error ? failure.message : "条目输入无效。"; return; }
    attempt = { actor: actorId!, baselineId: baselineId(), etag: baseline.value.etag,
      item, key: crypto.randomUUID() };
  }
  if (attempt.actor !== actorId || attempt.baselineId !== baselineId()) { locked.value = true; return; }
  busy.value = true; error.value = "";
  try {
    // A possible previous commit must retain its exact original body, ETag and key.
    if (!pending.value) {
      await recheck(attempt.item, attempt.etag);
      if (!mounted || !mayCreate()) return;
      const encoded = JSON.stringify(attempt);
      window.sessionStorage.setItem(storageKey(), encoded);
      if (window.sessionStorage.getItem(storageKey()) !== encoded) throw new Error("原操作号无法安全保存，未发送请求。");
      pending.value = attempt;
    }
    confirmRetry.value = false;
    const receipt = await creator.create(attempt.baselineId, attempt.etag, [attempt.item], attempt.key);
    if (!mounted || !mayCreate()) return;
    createdId.value = receipt.baseline_version_id;
    try { window.sessionStorage.removeItem(storageKey()); pending.value = null; }
    catch { locked.value = true; error.value = "已创建但无法清除原操作号；请勿重复提交。"; return; }
    try { await router.push({ name: "capability-baseline-detail", params: { baselineId: attempt.baselineId } }); }
    catch { error.value = "已创建 DRAFT，但自动跳转失败；请使用下方详情链接。"; }
  } catch (failure) {
    if (!mounted) return;
    if (failure instanceof CapabilityVersionCreateError && failure.code === "CONFLICT_IDEMPOTENCY") locked.value = true;
    if (failure instanceof CapabilityVersionCreateError && !failure.uncertain
      && failure.code !== "CONFLICT_IDEMPOTENCY" && pending.value) {
      try { window.sessionStorage.removeItem(storageKey()); pending.value = null; }
      catch { locked.value = true; }
    }
    error.value = failure instanceof Error ? failure.message : "结果无法确认；请保留原操作号。";
  } finally { if (mounted) busy.value = false; }
}
const unsubscribe = session.subscribe(() => { resetProjection(); if (mayCreate()) void load(); });
watch(() => route.params.baselineId, () => {
  resetProjection(); pending.value = null; confirmRetry.value = false; createdId.value = "";
  locked.value = false; restore(); void load();
});
onMounted(() => { restore(); void load(); });
onUnmounted(() => { mounted = false; resetProjection(); unsubscribe(); });
</script>

<template>
  <section class="page-panel" :aria-busy="loading || busy">
    <RouterLink :to="{ name: 'capability-baseline-detail', params: { baselineId: baselineId() } }">返回基线详情</RouterLink>
    <h1>创建标准能力 DRAFT 版本</h1>
    <p>从基线的固定来源和已人工确认合格的同源证据，建立一条完整能力项。保存不会自动批准。</p>
    <p v-if="!mayCreate()" role="status">仅部署管理员可提交。</p>
    <template v-else>
      <p v-if="error" role="alert">{{ error }}</p>
      <p v-if="loading" role="status">正在读取或核对当前来源…</p>
      <p v-if="createdId"><RouterLink :to="{ name: 'capability-baseline-detail', params: { baselineId: baselineId() } }">查看新建 DRAFT 版本</RouterLink></p>
      <template v-if="baseline && !createdId">
        <p>基线：{{ baseline.baseline_code }} · {{ baseline.name }}；当前 ETag：{{ baseline.etag }}</p>
        <p v-if="pending" role="status">原操作号与原条目已保留。请先查看版本历史；若结果仍不明，才按原内容和原号重试。</p>
        <template v-if="!pending">
          <h2>固定来源版本</h2>
          <p>必须选齐该基线的固定来源集合；提交前会核对集合摘要。</p>
          <ul><li v-for="doc in docs" :key="doc.document_id">{{ doc.title }}
            <button type="button" :disabled="loading || busy" @click="openVersions(doc)">选择版本</button>
          </li></ul>
          <button v-if="docsCursor" type="button" :disabled="loading" @click="moreDocs">加载更多文档</button>
          <div v-if="activeDoc">
            <h3>{{ activeDoc.title }} 的可用版本</h3>
            <ul><li v-for="version in versions" :key="version.document_version_id">
              第 {{ version.version_no }} 版 · {{ version.availability_state }}
              <button type="button" :disabled="loading" @click="chooseVersion(version)">选用此固定版本</button>
            </li></ul>
            <button v-if="versionsCursor" type="button" :disabled="loading" @click="moreVersions()">加载更多版本</button>
          </div>
          <ul aria-label="已选固定来源"><li v-for="source in chosen" :key="source.document.document_id">
            {{ source.document.title }} · 第 {{ source.version.version_no }} 版
            <button type="button" :disabled="loading || busy" @click="removeSource(source.document.document_id)">移除</button>
          </li></ul>
          <h2>已确认合格的同源证据</h2>
          <RouterLink to="/admin/evidence">查看证据与资格确认</RouterLink>
          <ul><li v-for="item in eligibleForSources" :key="item.evidence_id">
            <label><input type="checkbox" :checked="chosenEvidence.includes(item.evidence_id)"
              :disabled="loading || busy" @change="toggleEvidence(item.evidence_id)" />
              {{ item.display_label }} · {{ item.evidence_id }}</label>
          </li></ul>
          <p v-if="!eligibleForSources.length" role="status">当前页暂无已确认合格的同源证据；请先完成人工资格确认，或继续加载。</p>
          <button v-if="evidenceCursor" type="button" :disabled="loading" @click="moreEvidence()">加载更多证据</button>
          <button type="button" :disabled="loading" @click="moreEvidence(true)">刷新证据资格</button>
          <h2>能力条目</h2>
          <form @submit.prevent="submit">
            <label for="cap-code">能力代码</label><input id="cap-code" v-model="code" required maxlength="64" />
            <label for="cap-domain">业务域</label><input id="cap-domain" v-model="domain" required maxlength="255" />
            <label for="cap-module">模块</label><input id="cap-module" v-model="moduleName" required maxlength="255" />
            <label for="cap-feature">功能</label><input id="cap-feature" v-model="feature" required maxlength="255" />
            <label for="cap-name">能力名称</label><input id="cap-name" v-model="name" required maxlength="255" />
            <label for="cap-description">能力描述</label><textarea id="cap-description" v-model="description" required maxlength="2000" />
            <label for="cap-boundary">适用边界</label><textarea id="cap-boundary" v-model="boundary" required maxlength="2000" />
            <label for="cap-prerequisites">前置条件（每行一项，最多100项）</label><textarea id="cap-prerequisites" v-model="prerequisites" />
            <label for="cap-interfaces">接口引用（每行一项，最多100项）</label><textarea id="cap-interfaces" v-model="interfaces" />
            <label for="cap-state">条目状态</label><select id="cap-state" v-model="itemState">
              <option value="AVAILABLE">可用</option><option value="WITHDRAWN">撤回</option>
            </select>
            <label><input v-model="attested" type="checkbox" /> 我已核对固定来源和已合格证据；本次只建立 DRAFT，不代表批准。</label>
            <button type="submit" :disabled="loading || busy || locked || !chosen.length || !chosenEvidence.length || !attested">创建 DRAFT 版本</button>
          </form>
        </template>
        <form v-else @submit.prevent="submit">
          <label><input v-model="confirmRetry" type="checkbox" :disabled="busy || locked" /> 我已核对版本历史，确认沿用原内容、原 ETag 和原操作号重试</label>
          <button type="submit" :disabled="busy || locked || !confirmRetry">按原操作号重试</button>
        </form>
      </template>
      <button v-if="error && !loading && !busy" type="button" @click="load">重新读取</button>
    </template>
  </section>
</template>
