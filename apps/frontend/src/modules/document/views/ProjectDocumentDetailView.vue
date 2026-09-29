<script setup lang="ts">
import { inject, onUnmounted, ref, toRaw, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";

import { SessionClient } from "@/modules/auth/api/sessionClient";
import { sessionClientKey } from "@/modules/auth/api/sessionContext";
import { DocumentReadClient, DocumentReadError, type DocumentView } from "@/modules/document/api/documentReadClient";

const props = defineProps<{ session?: SessionClient; documents?: DocumentReadClient }>();
const session = toRaw(props.session ?? inject(sessionClientKey, null) ?? new SessionClient());
const documents = toRaw(props.documents ?? new DocumentReadClient());
const identity = session.view;
const route = useRoute();
const document = ref<DocumentView | null>(null);
const busy = ref(false);
const error = ref("");
let generation = 0;
let mounted = true;

function mayRead() {
  return mounted && !!identity && !identity.password_change_required
    && session.view?.user.user_id === identity.user.user_id;
}
async function load() {
  if (!mayRead() || busy.value) return;
  const current = ++generation;
  const projectId = typeof route.params.projectId === "string" ? route.params.projectId : "";
  const documentId = typeof route.params.documentId === "string" ? route.params.documentId : "";
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

watch([() => route.params.projectId, () => route.params.documentId], () => {
  generation += 1;
  document.value = null; busy.value = false; error.value = "";
  void load();
}, { immediate: true });
onUnmounted(() => { mounted = false; generation += 1; });
</script>

<template>
  <section class="document-detail" aria-labelledby="document-detail-title" :aria-busy="busy">
    <p class="section-kicker">项目资料</p>
    <h1 id="document-detail-title">项目文档详情</h1>
    <p>当前页面仅展示服务器授权的元数据；文件正文、版本和下载将由各自的受权入口提供。</p>
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
    </template>
  </section>
</template>

<style scoped>
.document-detail { max-width: 48rem; margin: 1rem auto; padding: 1.5rem; background: #fff; border-radius: 1rem; }
.document-detail p { line-height: 1.65; }
.document-detail dl { display: grid; grid-template-columns: minmax(8rem, auto) 1fr; gap: .65rem 1rem; }
.document-detail dt { font-weight: 700; }
.document-detail dd { margin: 0; overflow-wrap: anywhere; }
.document-detail [role="alert"] { color: #a21d25; }
</style>
