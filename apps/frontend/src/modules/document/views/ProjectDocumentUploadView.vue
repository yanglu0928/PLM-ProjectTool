<script setup lang="ts">
import { computed, inject, onUnmounted, ref, shallowRef, toRaw, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";

import { SessionClient } from "@/modules/auth/api/sessionClient";
import { sessionClientKey } from "@/modules/auth/api/sessionContext";
import { DocumentReadClient, DocumentReadError, type DocumentView } from "@/modules/document/api/documentReadClient";
import { DocumentUploadIntentClient, DocumentUploadIntentError,
  type CreatedProjectUploadIntent, type ProjectUploadIntentInput } from "@/modules/document/api/documentUploadIntentClient";
import { DocumentUploadContentClient, DocumentUploadContentError,
  type ReceivedProjectUploadContent } from "@/modules/document/api/documentUploadContentClient";
import { DocumentUploadFinalizeClient, DocumentUploadFinalizeError,
  type ProjectUploadCommitTarget, type ProjectUploadCommitFirstReceipt,
  type ProjectUploadAbortFirstReceipt } from "@/modules/document/api/documentUploadFinalizeClient";

const props = defineProps<{ session?: SessionClient; documents?: DocumentReadClient;
  creator?: DocumentUploadIntentClient; receiver?: DocumentUploadContentClient;
  finalizer?: DocumentUploadFinalizeClient }>();
const session = toRaw(props.session ?? inject(sessionClientKey, null) ?? new SessionClient());
const documents = toRaw(props.documents ?? new DocumentReadClient());
const creator = toRaw(props.creator ?? new DocumentUploadIntentClient(session));
const receiver = toRaw(props.receiver ?? new DocumentUploadContentClient(session));
const finalizer = toRaw(props.finalizer ?? new DocumentUploadFinalizeClient(session));
const route = useRoute();
const identity = session.view;
const versionMode = computed(() => route.name === "project-document-version-upload");
const source = ref<DocumentView | null>(null);
const sourceBusy = ref(false);
const busy = ref(false);
const status = ref<"READY" | "WORKING" | "UNKNOWN" | "NEEDS_ABORT" | "ABORT_UNKNOWN" | "DONE" | "ABORTED">("READY");
const error = ref("");
const purpose = ref("SOURCE");
const category = ref("PROJECT_RECORD");
const title = ref("");
const subtype = ref("");
const documentPurpose = ref("");
const file = shallowRef<File | null>(null);
const confirmed = ref(false);
const confirmRecovery = ref(false);
const confirmAbort = ref(false);
const committed = ref<ProjectUploadCommitFirstReceipt | null>(null);
const aborted = ref<ProjectUploadAbortFirstReceipt | null>(null);
type Stage = "CREATE" | "CONTENT" | "COMMIT";
type Attempt = Readonly<{ projectId: string; documentId: string | null; actorId: string;
  input: ProjectUploadIntentInput; target: ProjectUploadCommitTarget; file: File;
  createKey: string; commitKey: string; abortKey: string | null; stage: Stage;
  intent: CreatedProjectUploadIntent | null; received: ReceivedProjectUploadContent | null }>;
const attempt = shallowRef<Attempt | null>(null);
let mounted = true;
let generation = 0;

const writeRoles = new Set(["PROJECT_MANAGER", "IMPLEMENTATION_MEMBER", "CUSTOMER_MANAGER"]);
function projectId() { return typeof route.params.projectId === "string" ? route.params.projectId : ""; }
function documentId() { return versionMode.value && typeof route.params.documentId === "string"
  ? route.params.documentId : null; }
function mayWrite() {
  return mounted && !!identity && !identity.password_change_required && session.canSubmit
    && session.view?.user.user_id === identity.user.user_id
    && session.view.authorized_projects.some((item) => item.project_id === projectId() && writeRoles.has(item.role));
}
function sameRoute(run: number, snapshot: Attempt) {
  return mounted && run === generation && projectId() === snapshot.projectId
    && documentId() === snapshot.documentId;
}
function continueFor(run: number, snapshot: Attempt) {
  if (!sameRoute(run, snapshot)) return false;
  if (session.view?.user.user_id !== snapshot.actorId || !session.canSubmit) {
    status.value = "UNKNOWN";
    error.value = "当前会话已变化；已停止后续上传步骤。请先核对文档历史，重新登录后再处理原操作。";
    return false;
  }
  return true;
}
async function loadSource() {
  if (!versionMode.value || !identity || identity.password_change_required) return;
  const run = ++generation;
  const project = projectId();
  const document = documentId();
  if (!document) return;
  sourceBusy.value = true;
  source.value = null;
  error.value = "";
  try {
    const result = await documents.get({ kind: "PROJECT", projectId: project }, document);
    if (!mounted || run !== generation || projectId() !== project || documentId() !== document) return;
    if (result.state !== "ACTIVE") throw new DocumentReadError("DOCUMENT_CLIENT_UNAVAILABLE");
    source.value = result;
  } catch (failure) {
    if (!mounted || run !== generation || projectId() !== project || documentId() !== document) return;
    error.value = failure instanceof DocumentReadError ? failure.message : "暂时无法读取原文档。";
  } finally { if (mounted && run === generation) sourceBusy.value = false; }
}
function onFile(event: Event) {
  const selected = (event.target as HTMLInputElement).files?.item(0) ?? null;
  file.value = selected;
  confirmed.value = false;
}
function snapshot(): Attempt | null {
  const selected = file.value;
  if (!identity || !selected || selected.size < 1 || selected.size > 100_000_000) return null;
  const common = { purpose: purpose.value.trim(), displayName: selected.name,
    sizeHintBytes: selected.size, ...(selected.type ? { mimeHint: selected.type } : {}) };
  let input: ProjectUploadIntentInput;
  let target: ProjectUploadCommitTarget;
  if (versionMode.value) {
    const before = source.value;
    if (!before || before.state !== "ACTIVE" || before.document_id !== documentId()) return null;
    input = { kind: "VERSION", ...common, documentId: before.document_id,
      ...(before.latest_version_ref ? { supersedesVersionId: before.latest_version_ref } : {}) };
    target = { kind: "VERSION", documentId: before.document_id, parentEtag: before.etag };
  } else {
    input = { kind: "NEW", ...common, category: category.value, title: title.value.trim(),
      ...(category.value === "OTHER" ? { subtype: subtype.value.trim(),
        documentPurpose: documentPurpose.value.trim() } : {}) };
    target = { kind: "NEW" };
  }
  return Object.freeze({ projectId: projectId(), documentId: documentId(), actorId: identity.user.user_id,
    input: Object.freeze(input), target: Object.freeze(target), file: selected,
    createKey: crypto.randomUUID(), commitKey: crypto.randomUUID(), abortKey: null,
    stage: "CREATE" as const, intent: null, received: null });
}
async function advance() {
  const first = attempt.value;
  if (!first || busy.value || !mayWrite()) return;
  const run = generation;
  status.value = "WORKING";
  busy.value = true;
  error.value = "";
  confirmRecovery.value = false;
  try {
    let step = first;
    if (step.stage === "CREATE") {
      const intent = await creator.createProject(step.projectId, step.input, step.createKey);
      if (!continueFor(run, step)) return;
      step = Object.freeze({ ...step, intent, stage: "CONTENT" as const });
      attempt.value = step;
    }
    if (step.stage === "CONTENT") {
      if (!step.intent) throw new DocumentUploadContentError("DOCUMENT_UPLOAD_CONTENT_INVALID");
      const received = await receiver.putProject(step.projectId, step.intent, step.file);
      if (!continueFor(run, step)) return;
      step = Object.freeze({ ...step, received, stage: "COMMIT" as const });
      attempt.value = step;
    }
    if (step.stage === "COMMIT") {
      if (!step.received) throw new DocumentUploadFinalizeError("DOCUMENT_UPLOAD_FINALIZE_INVALID");
      const result = await finalizer.commitProject(step.projectId, step.received, step.target, step.commitKey);
      if (!continueFor(run, step)) return;
      committed.value = result;
      attempt.value = null;
      file.value = null;
      status.value = "DONE";
    }
  } catch (failure) {
    if (!sameRoute(run, first)) return;
    if (session.view?.user.user_id !== first.actorId || !session.canSubmit) {
      status.value = "UNKNOWN";
      error.value = "当前会话已失效或切换；已停止后续步骤。先核对文档历史，重新登录后再处理原操作。";
      return;
    }
    const pending = attempt.value;
    if (failure instanceof DocumentUploadIntentError || failure instanceof DocumentUploadContentError
      || failure instanceof DocumentUploadFinalizeError) {
      if (failure.uncertain) {
        status.value = "UNKNOWN";
        error.value = `${failure.message} 原文件与原操作记录仅保留在本页内存。先核对文档历史，再明确确认复用原阶段。`;
      } else if (pending?.stage === "CREATE") {
        attempt.value = null;
        status.value = "READY";
        error.value = failure.message;
      } else {
        status.value = "NEEDS_ABORT";
        error.value = `${failure.message} 本次意图尚未被确认提交，可明确终止后重新开始。`;
      }
    } else {
      status.value = "UNKNOWN";
      error.value = "操作结果无法确认；保留原文件与操作记录，先核对文档历史，勿直接重新上传。";
    }
  } finally { if (mounted && run === generation) busy.value = false; }
}
function submit() {
  if (!mayWrite() || sourceBusy.value || busy.value || attempt.value || !confirmed.value) return;
  const next = snapshot();
  if (!next) { error.value = "请选择 1～100 MB 文件并填写必需的文档信息。"; return; }
  attempt.value = next;
  confirmed.value = false;
  void advance();
}
function recover() {
  if (status.value !== "UNKNOWN" || !confirmRecovery.value || !attempt.value) return;
  void advance();
}
async function abort() {
  const pending = attempt.value;
  if (!pending || !pending.intent || !mayWrite() || busy.value || !confirmAbort.value
    || (status.value !== "NEEDS_ABORT" && status.value !== "ABORT_UNKNOWN")) return;
  const run = generation;
  const withKey = pending.abortKey ? pending : Object.freeze({ ...pending, abortKey: crypto.randomUUID() });
  attempt.value = withKey;
  busy.value = true;
  confirmAbort.value = false;
  error.value = "";
  try {
    const result = await finalizer.abortProject(withKey.projectId, withKey.intent!.uploadId, withKey.abortKey!);
    if (!continueFor(run, withKey)) return;
    aborted.value = result;
    attempt.value = null;
    file.value = null;
    status.value = "ABORTED";
  } catch (failure) {
    if (!sameRoute(run, withKey)) return;
    if (session.view?.user.user_id !== withKey.actorId || !session.canSubmit) {
      status.value = "ABORT_UNKNOWN";
      error.value = "当前会话已变化，无法确认终止结果；先核对历史并重新登录。";
      return;
    }
    if (failure instanceof DocumentUploadFinalizeError && !failure.uncertain) {
      status.value = "NEEDS_ABORT";
      error.value = `${failure.message} 请核对文档历史；不能把终止视为成功。`;
    } else {
      status.value = "ABORT_UNKNOWN";
      error.value = "终止结果无法确认。请核对文档历史；如需重试，明确确认后只复用原终止记录。";
    }
  } finally { if (mounted && run === generation) busy.value = false; }
}

watch([() => route.params.projectId, () => route.params.documentId, () => route.name], () => {
  generation += 1;
  source.value = null; sourceBusy.value = false; busy.value = false;
  attempt.value = null; committed.value = null; aborted.value = null;
  status.value = "READY"; error.value = ""; file.value = null;
  confirmed.value = false; confirmRecovery.value = false; confirmAbort.value = false;
  void loadSource();
}, { immediate: true });
onUnmounted(() => { mounted = false; generation += 1; attempt.value = null; file.value = null; });
</script>

<template>
  <section class="document-upload" aria-labelledby="upload-title" :aria-busy="busy || sourceBusy">
    <p class="section-kicker">项目资料</p>
    <h1 id="upload-title">{{ versionMode ? '上传文档新版本' : '上传新文档' }}</h1>
    <p><RouterLink :to="{ name: 'project-documents', params: { projectId: route.params.projectId } }">返回项目文档历史</RouterLink></p>
    <p>文件仅经受权接口上传；上传意图、内容和提交是三个独立步骤。离开或刷新本页会丢失内存中的原操作记录，结果未知时请先核对历史与审计。</p>
    <template v-if="!identity || identity.password_change_required || !mayWrite() && !attempt && status === 'READY'">
      <p role="status">需要当前项目具有上传权限且已重新登录的可提交会话；页面入口不代替服务器授权。</p>
      <RouterLink to="/login">前往账户与登录</RouterLink>
    </template>
    <template v-else>
      <p v-if="sourceBusy" role="status">正在读取原文档和版本…</p>
      <p v-if="error" role="alert">{{ error }}</p>
      <p v-if="!session.canSubmit"><RouterLink to="/login">重新登录后继续核对</RouterLink></p>
      <p v-if="versionMode && source">原文档：{{ source.title }} · 元数据版本 {{ source.etag }} · 最新版本引用 {{ source.latest_version_ref ?? '暂无' }}</p>
      <p v-if="committed" role="status">首次提交回执：文档 {{ committed.first_result.documentId }}，版本 {{ committed.first_result.versionNo }}，解析任务 {{ committed.first_result.parseJobId }}。这不是当前状态证明，请独立读取文档详情和解析状态。</p>
      <p v-if="committed"><RouterLink :to="{ name: 'project-document-detail', params: { projectId: route.params.projectId,
        documentId: committed.first_result.documentId } }">重新读取文档详情</RouterLink></p>
      <p v-if="aborted" role="status">首次终止回执：{{ aborted.first_result.state }}。{{ aborted.first_result.cleanupPending ? '物理清理仍待执行。' : '服务端未报告待清理项。' }}这不是当前状态证明。</p>
      <form v-if="status === 'READY' && !attempt && !committed && !aborted" @submit.prevent="submit">
        <label for="upload-purpose">资料用途代码</label>
        <input id="upload-purpose" v-model="purpose" required maxlength="64" pattern="[A-Z][A-Z0-9_]*" :disabled="busy" />
        <template v-if="!versionMode">
          <label for="upload-category">文档分类</label>
          <select id="upload-category" v-model="category" :disabled="busy">
            <option value="PROJECT_RECORD">项目记录</option><option value="CONTRACTUAL">合同/协议</option>
            <option value="STANDARD_CAPABILITY">标准能力</option><option value="REFERENCE_MATERIAL">参考资料</option>
            <option value="TEMPLATE">模板</option><option value="OTHER">其他</option>
          </select>
          <label for="upload-title-input">文档标题</label>
          <input id="upload-title-input" v-model="title" required maxlength="255" :disabled="busy" />
          <template v-if="category === 'OTHER'">
            <label for="upload-subtype">其他分类细分</label>
            <input id="upload-subtype" v-model="subtype" required maxlength="128" :disabled="busy" />
            <label for="upload-document-purpose">文档具体用途</label>
            <input id="upload-document-purpose" v-model="documentPurpose" required maxlength="255" :disabled="busy" />
          </template>
        </template>
        <label for="upload-file">选择文件（1～100 MB）</label>
        <input id="upload-file" type="file" required :disabled="busy || sourceBusy || versionMode && !source" @change="onFile" />
        <p v-if="file">{{ file.name }} · {{ file.size }} 字节。服务器会重新检查文件类型、大小与完整性。</p>
        <label><input v-model="confirmed" type="checkbox" :disabled="busy || sourceBusy" /> 我确认将此文件上传至当前项目{{ versionMode ? '并为原文档升版' : '作为新文档' }}</label>
        <button type="submit" :disabled="busy || sourceBusy || !file || !confirmed || versionMode && !source || !session.canSubmit">开始上传并提交</button>
      </form>
      <p v-if="status === 'WORKING'" role="status">正在执行 {{ attempt?.stage === 'CREATE' ? '创建上传意图' : attempt?.stage === 'CONTENT' ? '校验并传输文件' : '提交文档版本' }}…请勿离开本页。</p>
      <template v-if="status === 'UNKNOWN' && attempt">
        <p role="status">未知阶段：{{ attempt.stage }}。同一文件和原操作记录仅在本页内存中保留。</p>
        <label><input v-model="confirmRecovery" type="checkbox" :disabled="busy" /> 我已核对文档历史，确认仅复用原阶段与原操作记录</label>
        <button type="button" :disabled="busy || !confirmRecovery || !session.canSubmit" @click="recover">按原记录重试当前阶段</button>
      </template>
      <template v-if="(status === 'NEEDS_ABORT' || status === 'ABORT_UNKNOWN') && attempt?.intent">
        <p role="status">当前上传意图需显式终止或核对；终止不等于已完成物理清理。</p>
        <label><input v-model="confirmAbort" type="checkbox" :disabled="busy" /> 我确认{{ status === 'ABORT_UNKNOWN' ? '复用原终止操作记录' : '终止此上传意图' }}</label>
        <button type="button" :disabled="busy || !confirmAbort || !session.canSubmit" @click="abort">{{ status === 'ABORT_UNKNOWN' ? '按原记录重试终止' : '终止上传意图' }}</button>
      </template>
    </template>
  </section>
</template>

<style scoped>
.document-upload { max-width: 48rem; margin: 1rem auto; padding: 1.5rem; background: #fff; border-radius: 1rem; }
.document-upload form { display: grid; gap: .7rem; margin-top: 1rem; }
.document-upload input:not([type="checkbox"]), .document-upload select { width: 100%; padding: .55rem; }
.document-upload p { line-height: 1.65; overflow-wrap: anywhere; }
.document-upload [role="alert"] { color: #a21d25; }
.document-upload button:disabled { opacity: .55; cursor: not-allowed; }
</style>
