<script setup lang="ts">
import { computed, inject, onUnmounted, reactive, ref, toRaw, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";

import { SessionClient } from "@/modules/auth/api/sessionClient";
import { sessionClientKey } from "@/modules/auth/api/sessionContext";
import { DocumentReadClient, DocumentReadError, type DocumentView } from "@/modules/document/api/documentReadClient";
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
const identity = session.view; const route = useRoute();
const templates = ref<readonly PrototypeTemplateView[]>([]); const documents = ref<readonly DocumentView[]>([]);
const selected = ref<PrototypeTemplateView | null>(null); const pending = ref<Pending | null>(null);
const busy = ref(false); const loaded = ref(false); const error = ref(""); const notice = ref("");
const form = reactive({ name: "", layout: "SINGLE_COLUMN", components: ["FORM"] as string[],
  terminals: ["DESKTOP"] as string[], artifactVersions: [] as string[], confirmed: false });
let generation = 0; let mounted = true;
const layouts = prototypeTemplateLayouts; const componentOptions = prototypeTemplateComponents;
const terminalOptions = prototypeTemplateTerminals;
const projectId = () => typeof route.params.projectId === "string" ? route.params.projectId : "";
const role = computed(() => identity?.authorized_projects.find(item => item.project_id === projectId())?.role ?? null);
const canWrite = computed(() => !!identity && !identity.password_change_required && session.canSubmit
  && session.view?.user.user_id === identity.user.user_id
  && ["PROJECT_MANAGER", "IMPLEMENTATION_MEMBER"].includes(role.value ?? ""));
const projectTemplates = computed(() => templates.value.filter(item => item.scope === "PROJECT"));
const globalTemplates = computed(() => templates.value.filter(item => item.scope === "GLOBAL"));
const availableDocuments = computed(() => documents.value.filter(item => item.state === "ACTIVE"
  && (item.effective_version_ref ?? item.latest_version_ref)));
function versionOf(item: DocumentView) { return item.effective_version_ref ?? item.latest_version_ref!; }
function documentFor(versionId: string) { return documents.value.find(item => versionOf(item) === versionId) ?? null; }

async function load() {
  if (!identity || identity.password_change_required || busy.value) return;
  const project = projectId(), run = ++generation; busy.value = true; loaded.value = false; error.value = ""; notice.value = "";
  try {
    const firstTemplates = await templatesApi.listProject(project); const allTemplates = [...firstTemplates.items];
    let templateCursor = firstTemplates.next_cursor; let templatePages = 1;
    while (templateCursor && templatePages < 20) { const page = await templatesApi.listProject(project, 50, templateCursor as PrototypeTemplateCursor);
      allTemplates.push(...page.items); templateCursor = page.next_cursor; templatePages += 1; }
    const firstDocuments = await documentsApi.list({ kind: "PROJECT", projectId: project }); const allDocuments = [...firstDocuments.items];
    let documentCursor = firstDocuments.next_cursor; let documentPages = 1;
    while (documentCursor && documentPages < 20) { const page = await documentsApi.list({ kind: "PROJECT", projectId: project }, documentCursor);
      allDocuments.push(...page.items); documentCursor = page.next_cursor; documentPages += 1; }
    if (templateCursor || documentCursor || new Set(allTemplates.map(item => item.prototype_template_id)).size !== allTemplates.length
      || new Set(allDocuments.map(item => item.document_id)).size !== allDocuments.length) throw new PrototypeReadError("PROTOTYPE_READ_UNAVAILABLE");
    if (!mounted || run !== generation || project !== projectId()) return;
    templates.value = Object.freeze(allTemplates); documents.value = Object.freeze(allDocuments); selected.value = null; reset(); loaded.value = true;
  } catch (failure) { if (mounted && run === generation) { templates.value = []; documents.value = []; selected.value = null;
    error.value = failure instanceof Error ? failure.message : "暂时无法读取原型模板。"; } }
  finally { if (mounted && run === generation) busy.value = false; }
}
function reset() { form.name = ""; form.layout = "SINGLE_COLUMN"; form.components = ["FORM"]; form.terminals = ["DESKTOP"];
  form.artifactVersions = []; form.confirmed = false; }
function beginRevise(item: PrototypeTemplateView) {
  if (!canWrite.value || item.scope !== "PROJECT") return; const parsed = canonicalPrototypeTemplate(item);
  if (!parsed) { error.value = "该历史模板不符合当前结构化表单合同，只能查看；不会降级为任意JSON编辑。"; return; }
  if (item.artifact_refs.some(ref => ref.artifact_kind !== "DOCUMENT_VERSION" || ref.document_id === null)) {
    error.value = "该模板包含当前页面无法安全定位的制品，只能查看；请先完成服务端受权定位。"; return;
  }
  selected.value = item; form.name = item.name; form.layout = parsed.layout; form.components = [...parsed.components];
  form.terminals = [...item.applicable_terminals]; form.artifactVersions = item.artifact_refs.map(ref => ref.target_id);
  form.confirmed = false; error.value = ""; notice.value = "";
}
async function submit(attempt: Pending | null = null) {
  if (!canWrite.value || busy.value || (!form.confirmed && attempt === null)) return;
  if (attempt === null && (!form.components.length || !form.terminals.length)) { error.value = "至少选择一个组件和一个适用终端。"; return; }
  const value = attempt ?? (selected.value ? Object.freeze({ kind: "revise" as const,
    templateId: selected.value.prototype_template_id, etag: selected.value.etag, content: prototypeTemplateContent(form),
    key: `prototype-template-revise-${crypto.randomUUID()}` }) : Object.freeze({ kind: "create" as const,
    name: form.name.trim(), content: prototypeTemplateContent(form), key: `prototype-template-create-${crypto.randomUUID()}` }));
  const project = projectId(), run = ++generation; let completion = ""; busy.value = true; error.value = ""; notice.value = ""; pending.value = value;
  try { if (value.kind === "create") await writer.createProjectTemplate(project, value.name, value.content, value.key);
    else await writer.reviseProjectTemplate(project, value.templateId, value.etag, value.content, value.key);
    if (!mounted || run !== generation || project !== projectId()) return; pending.value = null; selected.value = null; reset();
    completion = value.kind === "create" ? "项目模板首版已发布；它仍不是客户确认事实。" : "模板新版本已发布；旧版本保持不可变。";
  } catch (failure) { if (mounted && run === generation) { error.value = failure instanceof Error ? failure.message : "暂时无法确认模板写入结果。";
    if (!(failure instanceof PrototypeWriteError) || !failure.uncertain) pending.value = null; } }
  finally { if (mounted && run === generation) busy.value = false; }
  if (completion && mounted && run === generation) { await load(); if (mounted && project === projectId()) notice.value = completion; }
}
watch(() => route.params.projectId, () => { generation += 1; templates.value = []; documents.value = []; selected.value = null;
  pending.value = null; busy.value = false; error.value = ""; notice.value = ""; reset(); void load(); }, { immediate: true });
onUnmounted(() => { mounted = false; generation += 1; });
</script>

<template>
  <section class="template-page" aria-labelledby="template-title" :aria-busy="busy">
    <p class="section-kicker">项目原型</p><h1 id="template-title">原型模板</h1>
    <p class="warning"><strong>模板只定义可复用结构，不是客户事实，也不会执行脚本。</strong>项目使用时固定具体模板版本；GLOBAL模板只读显示，管理入口仅向部署管理员开放。</p>
    <p><RouterLink :to="{ name: 'project-prototypes', params: { projectId: route.params.projectId } }">返回原型列表</RouterLink></p>
    <p v-if="!identity" role="status">尚未读取当前身份，请先登录。</p><p v-else-if="identity.password_change_required" role="status">当前账户须先修改密码。</p>
    <template v-else><button type="button" :disabled="busy" @click="load">{{ busy ? "正在读取…" : "刷新模板与文档候选" }}</button>
      <p v-if="error" role="alert">{{ error }}</p><p v-if="notice" role="status">{{ notice }}</p>
      <section><h2>项目模板</h2><p v-if="loaded && !projectTemplates.length">当前项目没有模板。</p>
        <ol><li v-for="item in projectTemplates" :key="item.prototype_template_id"><strong>{{ item.name }}</strong>
          <span>版本 {{ item.version_no }} · {{ item.etag }} · {{ item.applicable_terminals.join('、') }}</span>
          <span>固定文档 {{ item.artifact_refs.length }} 项 · 内容指纹 {{ item.content_fingerprint.slice(0, 12) }}…</span>
          <button v-if="canWrite && item.state === 'ACTIVE'" type="button" :disabled="busy || !!pending" @click="beginRevise(item)">以当前固定版本修订</button>
          <ul><li v-for="ref in item.artifact_refs" :key="`${ref.artifact_kind}:${ref.target_id}`"><template v-if="ref.document_id">
            <RouterLink :to="{ name: 'project-document-detail', params: { projectId: route.params.projectId, documentId: ref.document_id }, query: { version: ref.target_id } }">定位固定文档版本</RouterLink>
          </template><span v-else>服务端未提供受权文档根定位，当前只读。</span></li></ul></li></ol></section>
      <section><h2>获准的全局模板（只读）</h2><p>这些模板可作为项目固定输入，但不能在项目页面修改，也不代表本项目客户确认。</p>
        <ol><li v-for="item in globalTemplates" :key="item.prototype_template_id"><strong>{{ item.name }}</strong>
          <span>固定版本 {{ item.version_no }} · {{ item.applicable_terminals.join('、') }}</span></li></ol></section>
      <form v-if="canWrite" @submit.prevent="submit()"><h2>{{ selected ? `修订项目模板：${selected.name}` : '创建项目模板' }}</h2>
        <label v-if="!selected">模板名称<input v-model="form.name" required maxlength="255"></label>
        <label>布局<select v-model="form.layout"><option v-for="item in layouts" :key="item.value" :value="item.value">{{ item.label }}</option></select></label>
        <fieldset><legend>组件</legend><label v-for="item in componentOptions" :key="item" class="choice"><input v-model="form.components" type="checkbox" :value="item">{{ item }}</label></fieldset>
        <fieldset><legend>适用终端</legend><label v-for="item in terminalOptions" :key="item" class="choice"><input v-model="form.terminals" type="checkbox" :value="item">{{ item }}</label></fieldset>
        <fieldset><legend>固定项目文档版本（可选）</legend><p>只选择当前受权元数据；提交的是固定版本，不是动态“最新版”。</p>
          <label v-for="item in availableDocuments" :key="item.document_id" class="choice"><input v-model="form.artifactVersions" type="checkbox" :value="versionOf(item)">{{ item.title }} · {{ item.display_name }}</label>
          <p v-for="versionId in form.artifactVersions.filter(id => !documentFor(id))" :key="versionId">已保留历史固定文档版本：{{ versionId }}</p></fieldset>
        <label class="confirm"><input v-model="form.confirmed" type="checkbox">我已人工核对布局、组件、终端和固定文档；没有把AI建议当作客户事实。</label>
        <div><button :disabled="busy || !form.confirmed || !form.components.length || !form.terminals.length || !!pending">{{ selected ? '发布不可变修订版' : '发布首版' }}</button>
          <button v-if="selected" type="button" :disabled="busy || !!pending" @click="selected=null;reset()">取消修订</button></div></form>
      <aside v-if="pending" class="pending"><strong>上次模板{{ pending.kind === 'create' ? '创建' : '修订' }}结果未知。</strong>
        <p>请保持原结构、固定版本、ETag和操作号，不要新建重复版本。</p><button type="button" :disabled="busy" @click="submit(pending)">恢复原操作</button></aside>
    </template>
  </section>
</template>

<style scoped>
.template-page{max-width:72rem;margin:1rem auto;padding:1.5rem;background:#fff;border-radius:1rem}.template-page>section,.template-page form,.pending{display:grid;gap:.7rem;margin:1rem 0;padding:1rem;border:1px solid #d8dee7;border-radius:.8rem}.template-page ol{display:grid;gap:.8rem;padding:0;list-style:none}.template-page ol>li{display:grid;gap:.4rem;padding:.8rem;border:1px solid #d8dee7;border-radius:.7rem}.template-page form>label{display:grid;gap:.35rem}.choice,.confirm{display:flex!important;align-items:flex-start;gap:.4rem}.warning,.pending{padding:.8rem 1rem;border-left:.3rem solid #d29b42;background:#fff8e9}.template-page [role=alert]{color:#a21d25}
</style>
