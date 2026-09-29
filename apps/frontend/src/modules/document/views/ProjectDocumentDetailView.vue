<script setup lang="ts">
import { inject, onUnmounted, ref, toRaw, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";

import { SessionClient } from "@/modules/auth/api/sessionClient";
import { sessionClientKey } from "@/modules/auth/api/sessionContext";
import { DocumentReadClient, DocumentReadError, type DocumentVersionView, type DocumentView } from "@/modules/document/api/documentReadClient";

const props = defineProps<{ session?: SessionClient; documents?: DocumentReadClient }>();
const session = toRaw(props.session ?? inject(sessionClientKey, null) ?? new SessionClient());
const documents = toRaw(props.documents ?? new DocumentReadClient());
const identity = session.view;
const route = useRoute();
const writeRoles = new Set(["PROJECT_MANAGER", "IMPLEMENTATION_MEMBER", "CUSTOMER_MANAGER"]);
function mayUpload() {
  return !!identity && !identity.password_change_required && session.canSubmit
    && session.view?.user.user_id === identity.user.user_id
    && session.view.authorized_projects.some((item) => item.project_id === route.params.projectId && writeRoles.has(item.role));
}
const document = ref<DocumentView | null>(null);
const busy = ref(false);
const error = ref("");
const versions = ref<readonly DocumentVersionView[]>([]);
const versionsLoaded = ref(false);
const versionsBusy = ref(false);
const versionsError = ref("");
const versionCursor = ref<string | null>(null);
let generation = 0;
let versionGeneration = 0;
let mounted = true;

function clearVersions() {
  versionGeneration += 1;
  versions.value = [];
  versionsLoaded.value = false;
  versionsBusy.value = false;
  versionsError.value = "";
  versionCursor.value = null;
}

function mayRead() {
  return mounted && !!identity && !identity.password_change_required
    && session.view?.user.user_id === identity.user.user_id;
}
async function load() {
  if (!mayRead() || busy.value) return;
  const current = ++generation;
  const projectId = typeof route.params.projectId === "string" ? route.params.projectId : "";
  const documentId = typeof route.params.documentId === "string" ? route.params.documentId : "";
  clearVersions();
  document.value = null;
  busy.value = true;
  error.value = "";
  try {
    const result = await documents.get({ kind: "PROJECT", projectId }, documentId);
    if (!mounted || current !== generation || route.params.projectId !== projectId
      || route.params.documentId !== documentId || !mayRead()) return;
    document.value = result;
  } catch (failure) {
    if (!mounted || current !== generation || route.params.projectId !== projectId
      || route.params.documentId !== documentId) return;
    error.value = failure instanceof DocumentReadError ? failure.message : "暂时无法读取文档，请稍后重试。";
  } finally { if (mounted && current === generation) busy.value = false; }
}

async function loadVersions() {
  if (!mayRead() || !document.value || versionsBusy.value || versionsLoaded.value && !versionCursor.value) return;
  const projectId = typeof route.params.projectId === "string" ? route.params.projectId : "";
  const documentId = document.value.document_id;
  const cursor = versionCursor.value;
  const current = ++versionGeneration;
  versionsBusy.value = true;
  versionsError.value = "";
  try {
    const page = await documents.listVersions({ kind: "PROJECT", projectId }, documentId, cursor);
    if (!mounted || current !== versionGeneration || route.params.projectId !== projectId
      || route.params.documentId !== documentId || document.value?.document_id !== documentId || !mayRead()) return;
    const previous = cursor ? versions.value : [];
    if (page.items.some((item) => previous.some((earlier) => earlier.document_version_id === item.document_version_id
        || item.version_no >= earlier.version_no))) {
      throw new DocumentReadError("DOCUMENT_CLIENT_UNAVAILABLE");
    }
    versions.value = [...previous, ...page.items];
    versionsLoaded.value = true;
    versionCursor.value = page.next_cursor;
  } catch (failure) {
    if (!mounted || current !== versionGeneration || route.params.projectId !== projectId
      || route.params.documentId !== documentId) return;
    versionsError.value = failure instanceof DocumentReadError ? failure.message : "暂时无法读取版本，请稍后重试。";
  } finally { if (mounted && current === versionGeneration) versionsBusy.value = false; }
}

watch([() => route.params.projectId, () => route.params.documentId], () => {
  generation += 1;
  clearVersions();
  document.value = null; busy.value = false; error.value = "";
  void load();
}, { immediate: true });
onUnmounted(() => { mounted = false; generation += 1; clearVersions(); });
</script>

<template>
  <section class="document-detail" aria-labelledby="document-detail-title" :aria-busy="busy">
    <p class="section-kicker">项目资料</p>
    <h1 id="document-detail-title">项目文档详情</h1>
    <p>当前页面仅展示服务器授权的元数据；文件正文和下载将由各自的受权入口提供。</p>
    <p><RouterLink :to="{ name: 'project-documents', params: { projectId: route.params.projectId } }">返回项目文档历史</RouterLink></p>
    <template v-if="!identity">
      <p role="status">尚未读取当前身份。请先登录，或在账户页读取当前身份。</p>
      <RouterLink to="/login">前往账户与登录</RouterLink>
    </template>
    <template v-else-if="identity.password_change_required">
      <p role="status">当前账户须先修改密码，暂不能读取项目文档。</p>
      <RouterLink to="/login">前往账户与登录</RouterLink>
    </template>
    <template v-else>
      <button type="button" :disabled="busy" @click="load()">{{ busy ? '正在读取…' : '刷新文档详情' }}</button>
      <p v-if="busy" role="status">正在确认项目文档访问权限…</p>
      <p v-if="error" role="alert">{{ error }}</p>
      <dl v-if="document" aria-label="当前授权文档元数据">
        <dt>标题</dt><dd>{{ document.title }}</dd>
        <dt>文件名</dt><dd>{{ document.display_name }}</dd>
        <dt>分类</dt><dd>{{ document.category }}</dd>
        <template v-if="document.subtype"><dt>细分类型</dt><dd>{{ document.subtype }}</dd></template>
        <dt>状态</dt><dd>{{ document.state === 'ACTIVE' ? '有效' : '已归档' }}</dd>
        <dt>最新版本引用</dt><dd>{{ document.latest_version_ref ?? '暂无' }}</dd>
        <dt>当前使用版本引用</dt><dd>{{ document.effective_version_ref ?? '暂无' }}</dd>
        <dt>创建时间</dt><dd><time :datetime="document.created_at">{{ new Date(document.created_at).toLocaleString('zh-CN') }}</time></dd>
        <dt>元数据版本</dt><dd>{{ document.etag }}</dd>
      </dl>
      <p v-if="document?.state === 'ACTIVE' && mayUpload()"><RouterLink :to="{ name: 'project-document-version-upload',
        params: { projectId: route.params.projectId, documentId: document.document_id } }">上传此文档的新版本</RouterLink></p>
      <section v-if="document" aria-labelledby="document-versions-title">
        <h2 id="document-versions-title">可用版本历史</h2>
        <p>仅列出当前有权读取且状态为可用的版本。下载由服务器重新检查权限与文件完整性；这里不提供文内预览或定位。</p>
        <button v-if="!versionsLoaded" type="button" :disabled="versionsBusy" @click="loadVersions()">
          {{ versionsBusy ? '正在读取版本…' : '查看版本历史' }}
        </button>
        <p v-if="versionsBusy" role="status">正在读取受权版本…</p>
        <p v-if="versionsError" role="alert">{{ versionsError }}</p>
        <p v-if="versionsLoaded && versions.length === 0">暂无可用版本。</p>
        <ol v-if="versions.length" aria-label="可用版本历史">
          <li v-for="item in versions" :key="item.document_version_id">
            <strong>版本 {{ item.version_no }}</strong>
            <span> · {{ item.detected_mime }} · {{ item.size_bytes }} 字节</span>
            <span> · <time :datetime="item.created_at">{{ new Date(item.created_at).toLocaleString('zh-CN') }}</time></span>
            <span> · <a :href="documents.contentUrl({ kind: 'PROJECT', projectId: String(route.params.projectId) },
              document.document_id, item.document_version_id)">
              下载版本 {{ item.version_no }}
            </a></span>
            <details><summary>完整性元数据</summary>
              <dl><dt>版本引用</dt><dd>{{ item.document_version_id }}</dd>
                <dt>SHA-256</dt><dd>{{ item.content_sha256 }}</dd>
                <dt>前驱版本引用</dt><dd>{{ item.supersedes_version_ref ?? '暂无' }}</dd>
                <dt>完整性检查时间</dt><dd>{{ item.integrity_checked_at ?? '暂无' }}</dd></dl>
            </details>
          </li>
        </ol>
        <button v-if="versionCursor" type="button" :disabled="versionsBusy" @click="loadVersions()">
          {{ versionsBusy ? '正在读取版本…' : '继续加载版本' }}
        </button>
      </section>
    </template>
  </section>
</template>

<style scoped>
.document-detail { max-width: 48rem; margin: 1rem auto; padding: 1.5rem; background: #fff; border-radius: 1rem; }
.document-detail p { line-height: 1.65; }
.document-detail dl { display: grid; grid-template-columns: minmax(8rem, auto) 1fr; gap: .65rem 1rem; }
.document-detail dt { font-weight: 700; }
.document-detail dd { margin: 0; overflow-wrap: anywhere; }
.document-detail li { margin-block: .8rem; overflow-wrap: anywhere; }
.document-detail [role="alert"] { color: #a21d25; }
</style>
