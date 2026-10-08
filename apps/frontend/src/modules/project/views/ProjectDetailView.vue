<script setup lang="ts">
import { inject, onUnmounted, ref, toRaw, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";

import { SessionClient } from "@/modules/auth/api/sessionClient";
import { sessionClientKey } from "@/modules/auth/api/sessionContext";
import { ProjectReadClient, ProjectReadError, type ProjectView } from "@/modules/project/api/projectReadClient";
import { ProjectArchiveClient, ProjectArchiveError,
  type ProjectArchiveFirstReceipt } from "@/modules/project/api/projectArchiveClient";
import { ProjectPatchClient, ProjectPatchError } from "@/modules/project/api/projectPatchClient";

const props = defineProps<{ session?: SessionClient; projects?: ProjectReadClient;
  archiver?: ProjectArchiveClient; patcher?: ProjectPatchClient }>();
const session = toRaw(props.session ?? inject(sessionClientKey, null) ?? new SessionClient());
const projects = toRaw(props.projects ?? new ProjectReadClient());
const archiver = toRaw(props.archiver ?? new ProjectArchiveClient(session));
const patcher = toRaw(props.patcher ?? new ProjectPatchClient(session));
const identity = session.view;
const route = useRoute();
const project = ref<ProjectView | null>(null);
const busy = ref(false);
const writeBusy = ref(false);
const error = ref("");
const archiveEditor = ref<ProjectView | null>(null);
const nameEditor = ref<ProjectView | null>(null);
const draftName = ref("");
const nameConfirmed = ref(false);
const nameReceipt = ref<ProjectView | null>(null);
const archiveConfirmed = ref(false);
const confirmOriginal = ref(false);
const pending = ref<{ readonly project: string; readonly actor: string;
  readonly before: ProjectView; readonly key: string } | null>(null);
const receipt = ref<ProjectArchiveFirstReceipt | null>(null);
const blocked = ref(false);
const requireFreshRead = ref(false);
let generation = 0;
let mounted = true;

function canArchive() {
  return mounted && !!identity && !identity.password_change_required && session.canSubmit
    && session.view?.user.user_id === identity.user.user_id
    && !!session.view?.authorized_projects.some((item) => item.project_id === route.params.projectId
      && item.role === "PROJECT_MANAGER");
}
function sameCurrentProject(before: ProjectView) {
  const current = project.value;
  return !!current && current.project_id === before.project_id && current.state === "ACTIVE"
    && current.code === before.code && current.name === before.name
    && current.created_at === before.created_at && current.etag === before.etag;
}
async function load() {
  if (!mounted || !identity || identity.password_change_required || busy.value || writeBusy.value) return;
  const current = ++generation;
  const projectId = typeof route.params.projectId === "string" ? route.params.projectId : "";
  project.value = null;
  archiveEditor.value = null; archiveConfirmed.value = false; confirmOriginal.value = false;
  nameEditor.value = null; draftName.value = ""; nameConfirmed.value = false;
  error.value = "";
  busy.value = true;
  try {
    const result = await projects.get(projectId);
    if (!mounted || current !== generation) return;
    project.value = result;
    requireFreshRead.value = false;
    receipt.value = null;
    nameReceipt.value = null;
  } catch (failure) {
    if (!mounted || current !== generation) return;
    error.value = failure instanceof ProjectReadError
      ? failure.message : "暂时无法读取项目，请稍后重试。";
  } finally {
    if (mounted && current === generation) busy.value = false;
  }
}
function startArchive() {
  if (!canArchive() || busy.value || writeBusy.value || requireFreshRead.value
    || receipt.value || pending.value || blocked.value || nameEditor.value || nameReceipt.value || !project.value
    || project.value.state !== "ACTIVE") return;
  archiveEditor.value = Object.freeze({ ...project.value });
  archiveConfirmed.value = false;
  error.value = "";
}
function startNameEdit() {
  if (!canArchive() || busy.value || writeBusy.value || requireFreshRead.value
    || receipt.value || pending.value || blocked.value || archiveEditor.value || nameReceipt.value
    || !project.value || project.value.state !== "ACTIVE") return;
  nameEditor.value = Object.freeze({ ...project.value });
  draftName.value = project.value.name;
  nameConfirmed.value = false;
  error.value = "";
}
async function submitName() {
  if (!canArchive() || busy.value || writeBusy.value || requireFreshRead.value
    || receipt.value || pending.value || blocked.value || archiveEditor.value
    || !nameEditor.value || !nameConfirmed.value || !sameCurrentProject(nameEditor.value)) return;
  const attempt = Object.freeze({ project: nameEditor.value.project_id,
    actor: identity!.user.user_id, before: nameEditor.value, name: draftName.value });
  const current = ++generation;
  nameEditor.value = null; nameConfirmed.value = false;
  writeBusy.value = true; requireFreshRead.value = true; error.value = "";
  try {
    const result = await patcher.patch(attempt.project, attempt.before, attempt.name);
    if (!mounted || current !== generation || route.params.projectId !== attempt.project
      || !canArchive() || session.view?.user.user_id !== attempt.actor) return;
    nameReceipt.value = result;
  } catch (failure) {
    if (!mounted || current !== generation || route.params.projectId !== attempt.project) return;
    error.value = failure instanceof ProjectPatchError && !failure.uncertain
      ? failure.message + " 请重新读取项目详情后再决定。"
      : "名称修改结果无法确认。旧项目详情已清除；先重新读取项目并核对审计，勿直接重试。";
  } finally {
    if (mounted && current === generation) {
      project.value = null;
      writeBusy.value = false;
    }
  }
}
function canRecover() {
  const attempt = pending.value;
  return !!attempt && canArchive() && !busy.value && !writeBusy.value
    && !requireFreshRead.value && !blocked.value
    && attempt.project === route.params.projectId
    && attempt.actor === session.view?.user.user_id && sameCurrentProject(attempt.before);
}
async function submitArchive() {
  if (busy.value || writeBusy.value || requireFreshRead.value || blocked.value
    || nameEditor.value || nameReceipt.value) return;
  const recovery = pending.value;
  if (recovery && (!canRecover() || !confirmOriginal.value)) return;
  if (!recovery && (!canArchive() || !archiveEditor.value || !archiveConfirmed.value
    || !sameCurrentProject(archiveEditor.value))) return;
  const attempt = recovery ?? Object.freeze({ project: route.params.projectId as string,
    actor: identity!.user.user_id, before: archiveEditor.value!, key: crypto.randomUUID() });
  const current = ++generation;
  pending.value = attempt;
  archiveEditor.value = null; archiveConfirmed.value = false; confirmOriginal.value = false;
  writeBusy.value = true; error.value = "";
  try {
    const first = await archiver.archive(attempt.project, attempt.before, attempt.key);
    if (!mounted || current !== generation || route.params.projectId !== attempt.project
      || !canArchive() || session.view?.user.user_id !== attempt.actor) return;
    receipt.value = first;
    pending.value = null;
    requireFreshRead.value = true;
  } catch (failure) {
    if (!mounted || current !== generation || route.params.projectId !== attempt.project) return;
    requireFreshRead.value = true;
    if (!(failure instanceof ProjectArchiveError) || failure.uncertain) {
      error.value = "归档结果无法确认。原项目、版本和操作记录保留在本页；先核对项目详情与审计，勿生成新操作记录。";
    } else if (failure.code === "CONFLICT_IDEMPOTENCY") {
      pending.value = null; blocked.value = true;
      error.value = "原操作记录与请求冲突，已停止本页后续归档。请核对项目详情和审计。";
    } else {
      pending.value = null;
      error.value = failure.message + " 请重新读取项目详情后再决定。";
    }
  } finally {
    if (mounted && current === generation) {
      project.value = null;
      writeBusy.value = false;
    }
  }
}

watch(draftName, () => { nameConfirmed.value = false; });

watch(() => route.params.projectId, () => {
  generation += 1;
  project.value = null; error.value = ""; busy.value = false; writeBusy.value = false;
  archiveEditor.value = null; archiveConfirmed.value = false; confirmOriginal.value = false;
  nameEditor.value = null; draftName.value = ""; nameConfirmed.value = false; nameReceipt.value = null;
  pending.value = null; receipt.value = null; blocked.value = false; requireFreshRead.value = false;
  void load();
}, { immediate: true });
onUnmounted(() => { mounted = false; generation += 1; pending.value = null; });
</script>

<template>
  <section class="project-detail" aria-labelledby="project-title" :aria-busy="busy">
    <p class="section-kicker">当前项目</p>
    <h1 id="project-title">项目详情</h1>
    <p><RouterLink to="/projects">返回我的项目</RouterLink></p>
    <template v-if="!identity">
      <p role="status">尚未读取当前身份。请先登录，或在账户页读取当前身份。</p>
      <RouterLink to="/login">前往账户与登录</RouterLink>
    </template>
    <template v-else-if="identity.password_change_required">
      <p role="status">当前账户须先修改密码，暂不能读取项目。</p>
      <RouterLink to="/login">前往账户与登录</RouterLink>
    </template>
    <template v-else>
      <button type="button" :disabled="busy || writeBusy" @click="load()">{{ busy ? '正在读取…' : '刷新项目详情' }}</button>
      <p v-if="busy" role="status">正在确认当前项目访问权限…</p>
      <p v-if="error" role="alert">{{ error }}</p>
      <p v-if="blocked" role="alert">原操作记录冲突，已停止本页后续归档；请核对项目详情和审计。</p>
      <p v-if="receipt" role="status">本次归档首次回执：{{ receipt.first_result.name }}（{{ receipt.first_result.code }}）· {{ receipt.first_result.etag }}。这不是当前状态证明，请刷新项目详情重新读取。</p>
      <p v-if="nameReceipt" role="status">本次名称修改回执：{{ nameReceipt.name }}（{{ nameReceipt.code }}）· {{ nameReceipt.etag }}。这不是独立的当前状态证明，请刷新项目详情重新读取。</p>
      <p v-if="requireFreshRead && !receipt && !nameReceipt" role="status">旧项目详情已清除。成功重新读取项目详情前，不能再次操作。</p>
      <p v-if="pending" role="status">原归档操作仅保留在本页内存。离页后若结果仍不确定，先核对项目详情和审计，勿生成新操作记录。</p>
      <dl v-if="project" aria-label="当前授权项目详情">
        <dt>名称</dt><dd>{{ project.name }}</dd>
        <dt>编号</dt><dd>{{ project.code }}</dd>
        <dt>状态</dt><dd>{{ project.state === 'ACTIVE' ? '进行中' : '已归档' }}</dd>
        <dt>创建时间</dt><dd><time :datetime="project.created_at">{{ new Date(project.created_at).toLocaleString('zh-CN') }}</time></dd>
      </dl>
      <p v-if="project"><RouterLink :to="{ name: 'project-members', params: { projectId: project.project_id } }">查看项目成员历史</RouterLink></p>
      <p v-if="project"><RouterLink :to="{ name: 'project-departments', params: { projectId: project.project_id } }">查看项目部门历史</RouterLink></p>
      <p v-if="project"><RouterLink :to="{ name: 'project-documents', params: { projectId: project.project_id } }">查看项目文档历史</RouterLink></p>
      <p v-if="project"><RouterLink :to="{ name: 'project-evidence', params: { projectId: project.project_id } }">查看项目证据并定位原文</RouterLink></p>
      <p v-if="project"><RouterLink :to="{ name: 'project-jobs', params: { projectId: project.project_id } }">查看项目运行任务</RouterLink></p>
      <p v-if="project"><RouterLink :to="{ name: 'project-ai-workbench', params: { projectId: project.project_id } }">查看AI任务与建议状态</RouterLink></p>
      <p v-if="project"><RouterLink :to="{ name: 'project-handover', params: { projectId: project.project_id } }">查看项目交接分析与待确认事项</RouterLink></p>
      <p v-if="project"><RouterLink :to="{ name: 'project-handover-actions', params: { projectId: project.project_id } }">查看项目交接待办与验证状态</RouterLink></p>
      <p v-if="project"><RouterLink :to="{ name: 'project-surveys', params: { projectId: project.project_id } }">查看项目调研定义与问题卡片</RouterLink></p>
      <p v-if="project"><RouterLink :to="{ name: 'project-survey-rounds', params: { projectId: project.project_id } }">管理项目调研轮次</RouterLink></p>
      <p v-if="project"><RouterLink :to="{ name: 'project-survey-conclusions', params: { projectId: project.project_id } }">生成与评审调研结论</RouterLink></p>
      <p v-if="project"><RouterLink :to="{ name: 'project-requirements', params: { projectId: project.project_id } }">查看项目需求、待维护内容与原文入口</RouterLink></p>
      <p v-if="project"><RouterLink :to="{ name: 'project-prototypes', params: { projectId: project.project_id } }">维护项目原型、固定版本与需求覆盖</RouterLink></p>
      <p v-if="project"><RouterLink :to="{ name: 'project-retrieval-new', params: { projectId: project.project_id } }">新建项目知识检索</RouterLink></p>
      <p v-if="project"><RouterLink :to="{ name: 'project-workflow', params: { projectId: project.project_id } }">查看项目六阶段流程</RouterLink></p>
      <button v-if="project?.state === 'ACTIVE' && canArchive() && !requireFreshRead && !receipt && !pending && !blocked && !nameEditor && !nameReceipt"
        type="button" :disabled="busy || writeBusy" @click="startArchive">归档此项目</button>
      <button v-if="project?.state === 'ACTIVE' && canArchive() && !requireFreshRead && !receipt && !pending && !blocked && !archiveEditor && !nameReceipt"
        type="button" :disabled="busy || writeBusy" @click="startNameEdit">修改项目名称</button>
      <form v-if="nameEditor && canArchive() && !requireFreshRead && !blocked" @submit.prevent="submitName">
        <h2>修改项目名称：{{ nameEditor.name }}（{{ nameEditor.code }}）</h2>
        <p>基于刚读取的 {{ nameEditor.etag }} 版本。仅修改显示名称，不修改项目编号；提交结果不明确时，请先重新读取并核对审计，勿直接重试。</p>
        <label>新名称 <input v-model="draftName" type="text" required maxlength="255" :disabled="writeBusy" /></label>
        <label><input v-model="nameConfirmed" type="checkbox" :disabled="writeBusy" />我已核对项目编号、原版本和新名称</label>
        <button type="submit" :disabled="busy || writeBusy || !nameConfirmed">{{ writeBusy ? '正在提交…' : '确认修改名称' }}</button>
      </form>
      <form v-if="archiveEditor && canArchive() && !requireFreshRead && !blocked" @submit.prevent="submitArchive">
        <h2>归档项目：{{ archiveEditor.name }}（{{ archiveEditor.code }}）</h2>
        <p>基于刚读取的 {{ archiveEditor.etag }} 版本。归档后项目保留只读历史，但禁止新写入与任务；首版没有普通反归档入口。</p>
        <label><input v-model="archiveConfirmed" type="checkbox" :disabled="writeBusy" />我已核对当前项目，并确认理解归档后的单向影响</label>
        <button type="submit" :disabled="busy || writeBusy || !archiveConfirmed">{{ writeBusy ? '正在提交…' : '确认归档项目' }}</button>
      </form>
      <form v-if="pending && canArchive() && !blocked" @submit.prevent="submitArchive">
        <h2>核对原归档操作</h2>
        <p>原项目：{{ pending.before.name }}（{{ pending.before.code }}）· {{ pending.before.etag }}。仅当详情重读仍为原 ACTIVE 版本时，才可按原操作记录恢复；否则请核对审计。</p>
        <label><input v-model="confirmOriginal" type="checkbox" :disabled="busy || writeBusy || !canRecover()" />我确认只复用原项目、版本和操作记录</label>
        <button type="submit" :disabled="busy || writeBusy || !confirmOriginal || !canRecover()">按原操作记录恢复归档</button>
      </form>
    </template>
  </section>
</template>

<style scoped>
.project-detail { max-width: 48rem; margin: 1rem auto; padding: 1.5rem; background: #fff; border-radius: 1rem; }
.project-detail p { line-height: 1.65; }
.project-detail dl { display: grid; grid-template-columns: minmax(5rem, auto) 1fr; gap: .65rem 1rem; }
.project-detail dt { font-weight: 700; }
.project-detail dd { margin: 0; overflow-wrap: anywhere; }
.project-detail form { display: grid; gap: .7rem; margin-top: 1rem; }
.project-detail [role="alert"] { color: #a21d25; }
</style>
