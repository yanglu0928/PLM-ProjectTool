<script setup lang="ts">
import { inject, onUnmounted, ref, shallowRef, toRaw } from "vue";
import { RouterLink } from "vue-router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { sessionClientKey } from "@/modules/auth/api/sessionContext";
import { DocumentReadClient, DocumentReadError, type DocumentView } from "@/modules/document/api/documentReadClient";
import { DocumentUploadIntentClient, DocumentUploadIntentError,
  type CreatedProjectUploadIntent, type ProjectUploadIntentInput } from "@/modules/document/api/documentUploadIntentClient";
import { DocumentUploadContentClient, DocumentUploadContentError,
  type ReceivedProjectUploadContent } from "@/modules/document/api/documentUploadContentClient";
import { DocumentUploadFinalizeClient, DocumentUploadFinalizeError,
  type ProjectUploadCommitFirstReceipt, type ProjectUploadAbortFirstReceipt } from "@/modules/document/api/documentUploadFinalizeClient";

const props = defineProps<{ session?: SessionClient; documents?: DocumentReadClient;
  creator?: DocumentUploadIntentClient; receiver?: DocumentUploadContentClient;
  finalizer?: DocumentUploadFinalizeClient }>();
const session = toRaw(props.session ?? inject(sessionClientKey, null) ?? new SessionClient());
const documents = toRaw(props.documents ?? new DocumentReadClient());
const creator = toRaw(props.creator ?? new DocumentUploadIntentClient(session));
const receiver = toRaw(props.receiver ?? new DocumentUploadContentClient(session));
const finalizer = toRaw(props.finalizer ?? new DocumentUploadFinalizeClient(session));
const actorId = session.view?.user.user_id;
const title = ref("");
const file = shallowRef<File | null>(null);
const confirmed = ref(false);
const confirmRecovery = ref(false);
const confirmAbort = ref(false);
const busy = ref(false);
const error = ref("");
const status = ref<"READY" | "WORKING" | "UNKNOWN" | "NEEDS_ABORT" | "ABORT_UNKNOWN" | "DONE" | "ABORTED">("READY");
const committed = ref<ProjectUploadCommitFirstReceipt | null>(null);
const aborted = ref<ProjectUploadAbortFirstReceipt | null>(null);
const observed = ref<DocumentView | null>(null);
const observedAvailable = ref(false);
const observing = ref(false);
type Stage = "CREATE" | "CONTENT" | "COMMIT";
type Attempt = Readonly<{ actorId: string; input: ProjectUploadIntentInput; file: File;
  createKey: string; commitKey: string; abortKey: string | null; stage: Stage;
  intent: CreatedProjectUploadIntent | null; received: ReceivedProjectUploadContent | null }>;
const attempt = shallowRef<Attempt | null>(null);
let mounted = true;
let generation = 0;
function mayWrite(): boolean {
  const view = session.view;
  return mounted && !!actorId && view?.user.user_id === actorId && !view.password_change_required
    && view.deployment_role === "DEPLOYMENT_ADMIN" && session.canSubmit;
}
function clearForSession(): void {
  generation += 1; attempt.value = null; file.value = null; committed.value = null; aborted.value = null;
  observed.value = null; observedAvailable.value = false; observing.value = false;
  busy.value = false; confirmed.value = false; confirmRecovery.value = false; confirmAbort.value = false;
  status.value = "READY"; error.value = "会话已变化；原操作记录不再可用。请先核对全局文档历史与审计。";
}
const unsubscribe = session.subscribe(clearForSession);
function onFile(event: Event): void {
  file.value = (event.target as HTMLInputElement).files?.item(0) ?? null;
  confirmed.value = false;
}
function snapshot(): Attempt | null {
  const chosen = file.value;
  if (!actorId || !chosen || chosen.size < 1 || chosen.size > 100_000_000) return null;
  const input: ProjectUploadIntentInput = { kind: "NEW", purpose: "CAPABILITY_SOURCE",
    category: "STANDARD_CAPABILITY", title: title.value.trim(), displayName: chosen.name,
    sizeHintBytes: chosen.size, ...(chosen.type ? { mimeHint: chosen.type } : {}) };
  return Object.freeze({ actorId, input: Object.freeze(input), file: chosen,
    createKey: crypto.randomUUID(), commitKey: crypto.randomUUID(), abortKey: null,
    stage: "CREATE", intent: null, received: null });
}
function still(run: number, operationActorId: string): boolean {
  if (!mounted || run !== generation) return false;
  if (!mayWrite() || operationActorId !== session.view?.user.user_id) {
    clearForSession(); return false;
  }
  return true;
}
async function advance(): Promise<void> {
  const first = attempt.value;
  if (!first || !mayWrite() || busy.value) return;
  const run = generation;
  busy.value = true; status.value = "WORKING"; error.value = ""; confirmRecovery.value = false;
  try {
    let current = first;
    if (current.stage === "CREATE") {
      const intent = await creator.createGlobal(current.input, current.createKey);
      if (!still(run, current.actorId)) return;
      current = Object.freeze({ ...current, intent, stage: "CONTENT" as const }); attempt.value = current;
    }
    if (current.stage === "CONTENT") {
      if (!current.intent) throw new DocumentUploadContentError("DOCUMENT_UPLOAD_CONTENT_INVALID");
      const received = await receiver.putGlobal(current.intent, current.file);
      if (!still(run, current.actorId)) return;
      current = Object.freeze({ ...current, received, stage: "COMMIT" as const }); attempt.value = current;
    }
    if (current.stage === "COMMIT") {
      if (!current.received) throw new DocumentUploadFinalizeError("DOCUMENT_UPLOAD_FINALIZE_INVALID");
      const result = await finalizer.commitGlobal(current.received, current.commitKey);
      if (!still(run, current.actorId)) return;
      committed.value = result; attempt.value = null; file.value = null; status.value = "DONE";
    }
  } catch (failure) {
    if (!mounted || run !== generation) return;
    if (!mayWrite()) { clearForSession(); return; }
    if (failure instanceof DocumentUploadIntentError || failure instanceof DocumentUploadContentError
      || failure instanceof DocumentUploadFinalizeError) {
      if (failure.uncertain) {
        status.value = "UNKNOWN";
        error.value = `${failure.message} 原文件与操作号仅在本页内存；请先核对历史，再决定是否同号重试。`;
      } else if (attempt.value?.stage === "CREATE") {
        attempt.value = null; status.value = "READY"; error.value = failure.message;
      } else {
        status.value = "NEEDS_ABORT"; error.value = `${failure.message} 请核对历史，必要时显式终止此意图。`;
      }
    } else {
      status.value = "UNKNOWN";
      error.value = "操作结果暂无法确认；请核对历史，勿更换操作号自动重试。";
    }
  } finally { if (mounted && run === generation) busy.value = false; }
}
function submit(): void {
  if (!mayWrite() || busy.value || attempt.value || !confirmed.value) return;
  const next = snapshot();
  if (!next) { error.value = "请填写标题并选择 1～100 MB 文件。"; return; }
  attempt.value = next; confirmed.value = false; void advance();
}
function recover(): void {
  if (status.value === "UNKNOWN" && confirmRecovery.value && attempt.value && mayWrite()) void advance();
}
async function abort(): Promise<void> {
  const pending = attempt.value;
  if (!pending?.intent || !mayWrite() || busy.value || !confirmAbort.value
    || !["NEEDS_ABORT", "ABORT_UNKNOWN"].includes(status.value)) return;
  const run = generation;
  const withKey = pending.abortKey ? pending : Object.freeze({ ...pending, abortKey: crypto.randomUUID() });
  attempt.value = withKey; busy.value = true; confirmAbort.value = false; error.value = "";
  try {
    const result = await finalizer.abortGlobal(withKey.intent!.uploadId, withKey.abortKey!);
    if (!still(run, withKey.actorId)) return;
    aborted.value = result; attempt.value = null; file.value = null; status.value = "ABORTED";
  } catch (failure) {
    if (!mounted || run !== generation) return;
    if (!mayWrite()) { clearForSession(); return; }
    status.value = failure instanceof DocumentUploadFinalizeError && !failure.uncertain
      ? "NEEDS_ABORT" : "ABORT_UNKNOWN";
    error.value = "终止结果尚不能视为成功；请核对历史，需要重试时只复用原终止操作号。";
  } finally { if (mounted && run === generation) busy.value = false; }
}
async function observe(): Promise<void> {
  const receipt = committed.value;
  if (!receipt || !mayWrite() || observing.value) return;
  const run = generation; observing.value = true; error.value = ""; observed.value = null; observedAvailable.value = false;
  try {
    const id = receipt.first_result.documentId; const versionId = receipt.first_result.documentVersionId;
    const document = await documents.get({ kind: "GLOBAL" }, id);
    if (!still(run, actorId!)) return;
    if (document.scope !== "GLOBAL" || document.category !== "STANDARD_CAPABILITY" || document.state !== "ACTIVE") {
      throw new DocumentReadError("DOCUMENT_CLIENT_UNAVAILABLE");
    }
    let cursor: string | null = null; let found = false;
    const visited = new Set<string>();
    for (let pageNo = 0; pageNo < 20; pageNo += 1) {
      const page = await documents.listVersions({ kind: "GLOBAL" }, id, cursor);
      if (!still(run, actorId!)) return;
      if (page.items.some(item => item.document_version_id === versionId && item.availability_state === "AVAILABLE")) {
        found = true; break;
      }
      if (!page.next_cursor || visited.has(page.next_cursor)) break;
      visited.add(page.next_cursor); cursor = page.next_cursor;
    }
    observed.value = document; observedAvailable.value = found;
    if (!found) error.value = "尚未在可用版本列表中观察到本次固定版本；请等待解析/发布并重新核对。";
  } catch (failure) { if (mounted && run === generation) error.value = failure instanceof DocumentReadError
    ? failure.message : "暂时无法核对全局文档状态。"; }
  finally { if (mounted && run === generation) observing.value = false; }
}
onUnmounted(() => { mounted = false; generation += 1; attempt.value = null; file.value = null; unsubscribe(); });
</script>

<template>
  <section class="document-upload" aria-labelledby="global-capability-upload-title" :aria-busy="busy || observing">
    <RouterLink to="/capability-baselines">返回标准能力基线</RouterLink>
    <h1 id="global-capability-upload-title">上传全局标准能力文档</h1>
    <p>仅部署管理员可操作。文件上传至本系统的 GLOBAL 标准能力库；上传回执不代表已解析、已批准为能力基线。</p>
    <p>上传意图、文件内容和提交分三步进行。离开或刷新页面会失去内存中的原操作记录；结果不明时先核对历史与审计。</p>
    <p v-if="error" role="alert">{{ error }}</p>
    <p v-if="!mayWrite()" role="status">需要已登录且可提交的部署管理员会话。</p>
    <template v-else>
      <form v-if="status === 'READY' && !committed && !aborted" @submit.prevent="submit">
        <label for="capability-document-title">文档标题</label>
        <input id="capability-document-title" v-model="title" required maxlength="255" :disabled="busy" />
        <label for="capability-document-file">选择文件（1～100 MB）</label>
        <input id="capability-document-file" type="file" required :disabled="busy" @change="onFile" />
        <p v-if="file">{{ file.name }} · {{ file.size }} 字节；服务器会重新校验类型、大小和摘要。</p>
        <label><input v-model="confirmed" type="checkbox" :disabled="busy" /> 我确认将此文件加入全局标准能力库</label>
        <button type="submit" :disabled="busy || !file || !confirmed">上传并提交</button>
      </form>
      <p v-if="status === 'WORKING'" role="status">正在执行 {{ attempt?.stage === 'CREATE' ? '建立上传意图' : attempt?.stage === 'CONTENT' ? '校验并传输文件' : '提交固定文档版本' }}…</p>
      <template v-if="status === 'UNKNOWN' && attempt">
        <p role="status">结果未知：{{ attempt.stage }}；原操作记录仅保留在当前页面内存。</p>
        <label><input v-model="confirmRecovery" type="checkbox" :disabled="busy" /> 我已核对历史，确认只按原阶段、原文件、原操作号重试</label>
        <button type="button" :disabled="busy || !confirmRecovery" @click="recover">按原记录重试</button>
      </template>
      <template v-if="(status === 'NEEDS_ABORT' || status === 'ABORT_UNKNOWN') && attempt?.intent">
        <label><input v-model="confirmAbort" type="checkbox" :disabled="busy" /> 我确认{{ status === 'ABORT_UNKNOWN' ? '复用原终止号' : '终止此上传意图' }}</label>
        <button type="button" :disabled="busy || !confirmAbort" @click="abort">{{ status === 'ABORT_UNKNOWN' ? '同号重试终止' : '终止上传意图' }}</button>
      </template>
      <template v-if="committed">
        <p role="status">首次提交回执：文档 {{ committed.first_result.documentId }}，版本 {{ committed.first_result.versionNo }}。这不是当前可用性证明。</p>
        <button type="button" :disabled="observing" @click="observe">重新读取文档及固定版本状态</button>
        <p v-if="observedAvailable && observed" role="status">已独立读取到全局文档 {{ observed.title }} 的本次 AVAILABLE 固定版本；仍需另行创建并审批能力基线。</p>
      </template>
      <p v-if="aborted" role="status">首次终止回执：{{ aborted.first_result.state }}；{{ aborted.first_result.cleanupPending ? '物理清理仍待执行。' : '服务端未报告待清理项。' }}这不是当前状态证明。</p>
    </template>
  </section>
</template>
