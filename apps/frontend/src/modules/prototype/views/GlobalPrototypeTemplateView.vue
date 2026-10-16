<script setup lang="ts">
import { computed, inject, onUnmounted, reactive, ref, toRaw } from "vue";
import { RouterLink } from "vue-router";

import { SessionClient } from "@/modules/auth/api/sessionClient";
import { sessionClientKey } from "@/modules/auth/api/sessionContext";
import { DocumentReadClient, type DocumentView } from "@/modules/document/api/documentReadClient";
import { PrototypeReadError, PrototypeTemplateReadClient, type PrototypeTemplateCursor,
  type PrototypeTemplateView } from "@/modules/prototype/api/prototypeReadClient";
import { PrototypeWriteClient, PrototypeWriteError, type PrototypeTemplateContentInput } from "@/modules/prototype/api/prototypeWriteClient";
import { canonicalPrototypeTemplate, prototypeTemplateComponents, prototypeTemplateContent,
  prototypeTemplateLayouts, prototypeTemplateTerminals } from "./prototypeTemplateForm";

type Pending = Readonly<{ kind: "create"; name: string; content: PrototypeTemplateContentInput; key: string }>
  | Readonly<{ kind: "revise"; templateId: string; etag: string; content: PrototypeTemplateContentInput; key: string }>;
const props = defineProps<{ session?: SessionClient; templates?: PrototypeTemplateReadClient;
  documents?: DocumentReadClient; writer?: PrototypeWriteClient }>();
const session = toRaw(props.session ?? inject(sessionClientKey, null) ?? new SessionClient());
const templatesApi = toRaw(props.templates ?? new PrototypeTemplateReadClient());
const documentsApi = toRaw(props.documents ?? new DocumentReadClient());
const writer = toRaw(props.writer ?? new PrototypeWriteClient(session));
const identity = session.view; const templates = ref<readonly PrototypeTemplateView[]>([]);
const documents = ref<readonly DocumentView[]>([]); const selected = ref<PrototypeTemplateView | null>(null);
const pending = ref<Pending | null>(null); const busy = ref(false); const loaded = ref(false);
const error = ref(""); const notice = ref("");
const form = reactive({ name: "", layout: "SINGLE_COLUMN", components: ["FORM"] as string[],
  terminals: ["DESKTOP"] as string[], artifactVersions: [] as string[], confirmed: false });
let generation = 0; let mounted = true;
const layouts = prototypeTemplateLayouts; const componentOptions = prototypeTemplateComponents;
const terminalOptions = prototypeTemplateTerminals;
const canAdmin = computed(() => !!identity && identity.deployment_role === "DEPLOYMENT_ADMIN"
  && !identity.password_change_required && session.canSubmit && session.view?.user.user_id === identity.user.user_id);
const availableDocuments = computed(() => documents.value.filter(item => item.state === "ACTIVE"
  && (item.effective_version_ref ?? item.latest_version_ref)));
function versionOf(item: DocumentView) { return item.effective_version_ref ?? item.latest_version_ref!; }
function documentFor(versionId: string) { return documents.value.find(item => versionOf(item) === versionId) ?? null; }
function fixedContentUrl(documentId: string, versionId: string) {
  return documentsApi.contentUrl({ kind: "GLOBAL" }, documentId, versionId);
}
function reset() { form.name = ""; form.layout = "SINGLE_COLUMN"; form.components = ["FORM"]; form.terminals = ["DESKTOP"];
  form.artifactVersions = []; form.confirmed = false; }

async function load() {
  if (!canAdmin.value || busy.value) return; const run = ++generation; busy.value = true; loaded.value = false;
  error.value = ""; notice.value = "";
  try {
    const firstTemplates = await templatesApi.listGlobal(); const allTemplates = [...firstTemplates.items];
    let templateCursor = firstTemplates.next_cursor; let templatePages = 1;
    while (templateCursor && templatePages < 20) { const page = await templatesApi.listGlobal(50, templateCursor as PrototypeTemplateCursor);
      allTemplates.push(...page.items); templateCursor = page.next_cursor; templatePages += 1; }
    const firstDocuments = await documentsApi.list({ kind: "GLOBAL" }); const allDocuments = [...firstDocuments.items];
    let documentCursor = firstDocuments.next_cursor; let documentPages = 1;
    while (documentCursor && documentPages < 20) { const page = await documentsApi.list({ kind: "GLOBAL" }, documentCursor);
      allDocuments.push(...page.items); documentCursor = page.next_cursor; documentPages += 1; }
    if (templateCursor || documentCursor || new Set(allTemplates.map(item => item.prototype_template_id)).size !== allTemplates.length
      || allTemplates.some(item => item.scope !== "GLOBAL" || item.project_id !== null)
      || new Set(allDocuments.map(item => item.document_id)).size !== allDocuments.length
      || allDocuments.some(item => item.scope !== "GLOBAL")) throw new PrototypeReadError("PROTOTYPE_READ_UNAVAILABLE");
    if (!mounted || run !== generation || !canAdmin.value) return;
    templates.value = Object.freeze(allTemplates); documents.value = Object.freeze(allDocuments);
    selected.value = null; reset(); loaded.value = true;
  } catch (failure) { if (mounted && run === generation) { templates.value = []; documents.value = []; selected.value = null;
    error.value = failure instanceof Error ? failure.message : "暂时无法读取全局原型模板。"; } }
  finally { if (mounted && run === generation) busy.value = false; }
}
function beginRevise(item: PrototypeTemplateView) {
  if (!canAdmin.value) return; const parsed = canonicalPrototypeTemplate(item);
  if (!parsed) { error.value = "该历史模板不符合当前结构化表单合同，只能查看；不会降级为任意JSON编辑。"; return; }
  if (item.artifact_refs.some(ref => ref.artifact_kind !== "DOCUMENT_VERSION" || ref.document_id === null)) {
    error.value = "该模板包含无法安全定位的制品，只能查看；请先完成服务端受权定位。"; return;
  }
  selected.value = item; form.name = item.name; form.layout = parsed.layout; form.components = [...parsed.components];
  form.terminals = [...item.applicable_terminals]; form.artifactVersions = item.artifact_refs.map(ref => ref.target_id);
  form.confirmed = false; error.value = ""; notice.value = "";
}
async function submit(attempt: Pending | null = null) {
  if (!canAdmin.value || busy.value || (!form.confirmed && attempt === null)) return;
  if (attempt === null && (!form.components.length || !form.terminals.length)) { error.value = "至少选择一个组件和一个适用终端。"; return; }
  const value = attempt ?? (selected.value ? Object.freeze({ kind: "revise" as const,
    templateId: selected.value.prototype_template_id, etag: selected.value.etag,
    content: prototypeTemplateContent(form), key: `global-prototype-template-revise-${crypto.randomUUID()}` })
    : Object.freeze({ kind: "create" as const, name: form.name.trim(), content: prototypeTemplateContent(form),
      key: `global-prototype-template-create-${crypto.randomUUID()}` }));
  const run = ++generation; let completion = ""; busy.value = true; error.value = ""; notice.value = ""; pending.value = value;
  try { if (value.kind === "create") await writer.createGlobalTemplate(value.name, value.content, value.key);
    else await writer.reviseGlobalTemplate(value.templateId, value.etag, value.content, value.key);
    if (!mounted || run !== generation || !canAdmin.value) return; pending.value = null; selected.value = null; reset();
    completion = value.kind === "create" ? "全局模板首版已发布；项目仍须固定具体版本并独立形成客户事实。"
      : "全局模板新版本已发布；旧版本及使用它的项目事实保持不变。";
  } catch (failure) { if (mounted && run === generation) { error.value = failure instanceof Error ? failure.message : "暂时无法确认全局模板写入结果。";
    if (!(failure instanceof PrototypeWriteError) || !failure.uncertain) pending.value = null; } }
  finally { if (mounted && run === generation) busy.value = false; }
  if (completion && mounted && run === generation) { await load(); if (mounted && canAdmin.value) notice.value = completion; }
}
if (canAdmin.value) void load();
onUnmounted(() => { mounted = false; generation += 1; });
</script>

<template>
  <section class="global-template" aria-labelledby="global-template-title" :aria-busy="busy">
    <p class="section-kicker">部署管理</p><h1 id="global-template-title">全局原型模板</h1>
    <p class="warning"><strong>GLOBAL模板是跨项目可复用结构，不是任何客户的确认事实。</strong>修订只会发布新不可变版本，不会改写使用旧版本的项目。</p>
    <p><RouterLink :to="{ name: 'admin-users' }">返回部署管理区域</RouterLink></p>
    <p v-if="!identity" role="status">尚未读取当前身份，请先登录。</p>
    <p v-else-if="identity.password_change_required" role="status">当前账户须先修改密码。</p>
    <p v-else-if="!canAdmin" role="status">仅部署管理员可以管理全局原型模板。</p>
    <template v-else><button type="button" :disabled="busy" @click="load">{{ busy ? "正在读取…" : "刷新全局模板与文档候选" }}</button>
      <p v-if="error" role="alert">{{ error }}</p><p v-if="notice" role="status">{{ notice }}</p>
      <section><h2>已发布全局模板</h2><p v-if="loaded && !templates.length">尚无全局原型模板。</p>
        <ol><li v-for="item in templates" :key="item.prototype_template_id"><strong>{{ item.name }}</strong>
          <span>版本 {{ item.version_no }} · {{ item.etag }} · {{ item.applicable_terminals.join('、') }}</span>
          <span>固定文档 {{ item.artifact_refs.length }} 项 · 内容指纹 {{ item.content_fingerprint.slice(0, 12) }}…</span>
          <button v-if="item.state === 'ACTIVE'" type="button" :disabled="busy || !!pending" @click="beginRevise(item)">以当前固定版本修订</button>
          <ul><li v-for="ref in item.artifact_refs" :key="`${ref.artifact_kind}:${ref.target_id}`">
            <a v-if="ref.document_id" :href="fixedContentUrl(ref.document_id, ref.target_id)" target="_blank" rel="noopener">打开受权固定文档原文</a>
            <span v-else>服务端未提供受权文档根定位，当前只读。</span></li></ul></li></ol></section>
      <form @submit.prevent="submit()"><h2>{{ selected ? `修订全局模板：${selected.name}` : '创建全局模板' }}</h2>
        <label v-if="!selected">模板名称<input v-model="form.name" required maxlength="255"></label>
        <label>布局<select v-model="form.layout"><option v-for="item in layouts" :key="item.value" :value="item.value">{{ item.label }}</option></select></label>
        <fieldset><legend>组件</legend><label v-for="item in componentOptions" :key="item" class="choice"><input v-model="form.components" type="checkbox" :value="item">{{ item }}</label></fieldset>
        <fieldset><legend>适用终端</legend><label v-for="item in terminalOptions" :key="item" class="choice"><input v-model="form.terminals" type="checkbox" :value="item">{{ item }}</label></fieldset>
        <fieldset><legend>固定全局文档版本（可选）</legend><p>只显示受权元数据；选择后固定具体版本，不使用动态“最新版”。</p>
          <label v-for="item in availableDocuments" :key="item.document_id" class="choice"><input v-model="form.artifactVersions" type="checkbox" :value="versionOf(item)">{{ item.title }} · {{ item.display_name }}</label>
          <p v-for="versionId in form.artifactVersions.filter(id => !documentFor(id))" :key="versionId">已保留历史固定文档版本：{{ versionId }}</p></fieldset>
        <label class="confirm"><input v-model="form.confirmed" type="checkbox">我已人工核对结构和固定文档，确认不包含脚本，也不把模板当作客户事实。</label>
        <div><button :disabled="busy || !form.confirmed || !form.components.length || !form.terminals.length || !!pending">{{ selected ? '发布不可变修订版' : '发布首版' }}</button>
          <button v-if="selected" type="button" :disabled="busy || !!pending" @click="selected=null;reset()">取消修订</button></div></form>
      <aside v-if="pending" class="pending"><strong>上次全局模板{{ pending.kind === 'create' ? '创建' : '修订' }}结果未知。</strong>
        <p>请保持原结构、固定版本、ETag和操作号，不要新建重复版本。</p><button type="button" :disabled="busy" @click="submit(pending)">恢复原操作</button></aside>
    </template>
  </section>
</template>

<style scoped>
.global-template{max-width:72rem;margin:1rem auto;padding:1.5rem;background:#fff;border-radius:1rem}.global-template>section,.global-template form,.pending{display:grid;gap:.7rem;margin:1rem 0;padding:1rem;border:1px solid #d8dee7;border-radius:.8rem}.global-template ol{display:grid;gap:.8rem;padding:0;list-style:none}.global-template ol>li{display:grid;gap:.4rem;padding:.8rem;border:1px solid #d8dee7;border-radius:.7rem}.global-template form>label{display:grid;gap:.35rem}.choice,.confirm{display:flex!important;align-items:flex-start;gap:.4rem}.warning,.pending{padding:.8rem 1rem;border-left:.3rem solid #d29b42;background:#fff8e9}.global-template [role=alert]{color:#a21d25}
</style>
