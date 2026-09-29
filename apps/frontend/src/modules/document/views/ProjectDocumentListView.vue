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
const writeRoles = new Set(["PROJECT_MANAGER", "IMPLEMENTATION_MEMBER", "CUSTOMER_MANAGER"]);
function mayUpload() {
  return !!identity && !identity.password_change_required && session.canSubmit
    && session.view?.user.user_id === identity.user.user_id
    && session.view.authorized_projects.some((item) => item.project_id === route.params.projectId && writeRoles.has(item.role));
}
const items = ref<readonly DocumentView[]>([]);
const nextCursor = ref<string | null>(null);
const loaded = ref(false);
const busy = ref(false);
const error = ref("");
let generation = 0;
let mounted = true;

function mayRead() {
  return mounted && !!identity && !identity.password_change_required
    && session.view?.user.user_id === identity.user.user_id;
}
async function load(cursor: string | null = null, replace = false) {
  if (!mayRead() || busy.value) return;
  const current = ++generation;
  const projectId = typeof route.params.projectId === "string" ? route.params.projectId : "";
  busy.value = true;
  error.value = "";
  if (replace) { items.value = []; nextCursor.value = null; loaded.value = false; }
  try {
    const page = await documents.list({ kind: "PROJECT", projectId }, cursor);
    if (!mounted || current !== generation || route.params.projectId !== projectId || !mayRead()) return;
    const known = new Set(items.value.map((item) => item.document_id));
    if (page.items.some((item) => known.has(item.document_id))) {
      throw new DocumentReadError("DOCUMENT_CLIENT_UNAVAILABLE");
    }
    items.value = Object.freeze([...items.value, ...page.items]);
    nextCursor.value = page.next_cursor;
    loaded.value = true;
  } catch (failure) {
    if (!mounted || current !== generation || route.params.projectId !== projectId) return;
    items.value = []; nextCursor.value = null; loaded.value = false;
    error.value = failure instanceof DocumentReadError ? failure.message : "暂时无法读取文档，请稍后重试。";
  } finally { if (mounted && current === generation) busy.value = false; }
}

watch(() => route.params.projectId, () => {
  generation += 1;
  items.value = []; nextCursor.value = null; loaded.value = false; error.value = ""; busy.value = false;
  void load(null, true);
}, { immediate: true });
onUnmounted(() => { mounted = false; generation += 1; });
</script>

<template>
  <section class="document-panel" aria-labelledby="document-list-title" :aria-busy="busy">
    <p class="section-kicker">项目资料</p>
    <h1 id="document-list-title">项目文档历史</h1>
    <p>由服务器按当前项目实时确认可见范围；列表只显示元数据，不含文档正文。跨页内容不代表同一时刻的快照。</p>
    <p><RouterLink :to="{ name: 'project-detail', params: { projectId: route.params.projectId } }">返回项目详情</RouterLink></p>
    <template v-if="!identity">
      <p role="status">尚未读取当前身份。请先登录，或在账户页读取当前身份。</p>
      <RouterLink to="/login">前往账户与登录</RouterLink>
    </template>
    <template v-else-if="identity.password_change_required">
      <p role="status">当前账户须先修改密码，暂不能读取项目文档。</p>
      <RouterLink to="/login">前往账户与登录</RouterLink>
    </template>
    <template v-else>
      <p v-if="mayUpload()"><RouterLink :to="{ name: 'project-document-upload', params: { projectId: route.params.projectId } }">上传新文档</RouterLink></p>
      <button type="button" :disabled="busy" @click="load(null, true)">{{ busy ? '正在读取…' : '刷新文档列表' }}</button>
      <p v-if="busy" role="status">正在确认项目文档访问权限…</p>
      <p v-if="error" role="alert">{{ error }}</p>
      <p v-if="loaded && items.length === 0" role="status">当前项目没有可见文档记录。</p>
      <ul v-if="items.length" aria-label="项目文档历史">
        <li v-for="item in items" :key="item.document_id">
          <strong><RouterLink :to="{ name: 'project-document-detail', params: { projectId: route.params.projectId, documentId: item.document_id } }">{{ item.title }}</RouterLink></strong>
          <span>文件名：{{ item.display_name }} · 分类：{{ item.category }} · {{ item.state === 'ACTIVE' ? '有效' : '已归档' }}</span>
          <span>创建：<time :datetime="item.created_at">{{ new Date(item.created_at).toLocaleString('zh-CN') }}</time></span>
          <span>元数据版本：{{ item.etag }}</span>
        </li>
      </ul>
      <button v-if="nextCursor && loaded" type="button" :disabled="busy" @click="load(nextCursor)">加载更多文档</button>
    </template>
  </section>
</template>

<style scoped>
.document-panel { max-width: 48rem; margin: 1rem auto; padding: 1.5rem; background: #fff; border-radius: 1rem; }
.document-panel p { line-height: 1.65; }
.document-panel li { display: grid; gap: .35rem; padding: .8rem 0; border-bottom: 1px solid #d8dee7; overflow-wrap: anywhere; }
.document-panel [role="alert"] { color: #a21d25; }
</style>
