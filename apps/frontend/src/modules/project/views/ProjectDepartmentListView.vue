<script setup lang="ts">
import { inject, onUnmounted, ref, toRaw, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";

import { SessionClient } from "@/modules/auth/api/sessionClient";
import { sessionClientKey } from "@/modules/auth/api/sessionContext";
import { ProjectDepartmentReadClient, ProjectDepartmentReadError,
  type ProjectDepartmentView } from "@/modules/project/api/projectDepartmentReadClient";
import { ProjectDepartmentPatchClient, ProjectDepartmentPatchError } from
  "@/modules/project/api/projectDepartmentPatchClient";
import { ProjectDepartmentDeactivateClient, ProjectDepartmentDeactivateError,
  type ProjectDepartmentDeactivateFirstReceipt } from
  "@/modules/project/api/projectDepartmentDeactivateClient";

const props = defineProps<{ session?: SessionClient; departments?: ProjectDepartmentReadClient;
  patcher?: ProjectDepartmentPatchClient; deactivator?: ProjectDepartmentDeactivateClient }>();
const session = toRaw(props.session ?? inject(sessionClientKey, null) ?? new SessionClient());
const departments = toRaw(props.departments ?? new ProjectDepartmentReadClient());
const patcher = toRaw(props.patcher ?? new ProjectDepartmentPatchClient(session));
const deactivator = toRaw(props.deactivator ?? new ProjectDepartmentDeactivateClient(session));
const identity = session.view;
const route = useRoute();
const items = ref<readonly ProjectDepartmentView[]>([]);
const nextCursor = ref<string | null>(null);
const loaded = ref(false);
const busy = ref(false);
const writeBusy = ref(false);
const error = ref("");
const edit = ref<ProjectDepartmentView | null>(null);
const editCode = ref("");
const editName = ref("");
const editConfirmed = ref(false);
const writeReceipt = ref<ProjectDepartmentView | null>(null);
const deactivateEditor = ref<ProjectDepartmentView | null>(null);
const deactivateConfirmed = ref(false);
const confirmOriginal = ref(false);
const deactivatePending = ref<{ readonly project: string; readonly actor: string;
  readonly before: ProjectDepartmentView; readonly key: string } | null>(null);
const deactivateReceipt = ref<ProjectDepartmentDeactivateFirstReceipt | null>(null);
const deactivateBlocked = ref(false);
const requireFreshRead = ref(false);
let generation = 0;
let mounted = true;
function canCreate() {
  return mounted && !!identity && !identity.password_change_required && session.canSubmit
    && session.view?.user.user_id === identity.user.user_id
    && !!session.view?.authorized_projects.some((item) => item.project_id === route.params.projectId
      && item.role === "PROJECT_MANAGER");
}

async function load(cursor: string | null = null, replace = false) {
  if (!mounted || !identity || identity.password_change_required || busy.value || writeBusy.value) return;
  const current = ++generation;
  const projectId = typeof route.params.projectId === "string" ? route.params.projectId : "";
  busy.value = true;
  error.value = "";
  if (replace) {
    items.value = []; nextCursor.value = null; loaded.value = false;
    edit.value = null; editConfirmed.value = false;
    deactivateEditor.value = null; deactivateConfirmed.value = false;
  }
  try {
    const page = await departments.list(projectId, cursor);
    if (!mounted || current !== generation) return;
    const known = new Set(items.value.map((item) => item.department_id));
    if (page.items.some((item) => known.has(item.department_id))) {
      throw new ProjectDepartmentReadError("PROJECT_DEPARTMENT_CLIENT_UNAVAILABLE");
    }
    items.value = Object.freeze([...items.value, ...page.items]);
    nextCursor.value = page.next_cursor;
    loaded.value = true;
    if (replace) {
      requireFreshRead.value = false; writeReceipt.value = null; deactivateReceipt.value = null;
    }
  } catch (failure) {
    if (!mounted || current !== generation) return;
    items.value = []; nextCursor.value = null; loaded.value = false;
    error.value = failure instanceof ProjectDepartmentReadError
      ? failure.message : "暂时无法读取项目部门，请稍后重试。";
  } finally { if (mounted && current === generation) busy.value = false; }
}

watch([editCode, editName], () => { editConfirmed.value = false; });
function startEdit(item: ProjectDepartmentView) {
  if (!canCreate() || busy.value || writeBusy.value || requireFreshRead.value
    || writeReceipt.value || deactivateReceipt.value || deactivatePending.value
    || deactivateBlocked.value || item.state !== "ACTIVE"
    || !items.value.some((current) => current.department_id === item.department_id
      && current.etag === item.etag && current.code === item.code && current.name === item.name)) return;
  edit.value = Object.freeze({ ...item });
  editCode.value = item.code;
  editName.value = item.name;
  editConfirmed.value = false;
  deactivateEditor.value = null; deactivateConfirmed.value = false;
  error.value = "";
}

async function submitEdit() {
  const before = edit.value;
  if (!canCreate() || !before || !editConfirmed.value || busy.value || writeBusy.value
    || requireFreshRead.value || writeReceipt.value || deactivatePending.value || deactivateBlocked.value
    || !items.value.some((current) => current.department_id === before.department_id
      && current.etag === before.etag && current.code === before.code && current.name === before.name)) return;
  const current = ++generation;
  const projectId = route.params.projectId as string;
  const actorId = identity!.user.user_id;
  const input = Object.freeze({ code: editCode.value, name: editName.value });
  editConfirmed.value = false;
  writeBusy.value = true;
  error.value = "";
  try {
    const result = await patcher.patch(projectId, before, input);
    if (!mounted || current !== generation || route.params.projectId !== projectId
      || !canCreate() || session.view?.user.user_id !== actorId) return;
    writeReceipt.value = result;
    requireFreshRead.value = true;
  } catch (failure) {
    if (!mounted || current !== generation || route.params.projectId !== projectId) return;
    requireFreshRead.value = true;
    error.value = failure instanceof ProjectDepartmentPatchError && !failure.uncertain
      ? failure.message + " 请重新读取部门历史后再操作。"
      : "修改结果无法确认。请重新读取部门历史和审计，勿直接重试。";
  } finally {
    if (mounted && current === generation) {
      edit.value = null;
      items.value = []; nextCursor.value = null; loaded.value = false;
      writeBusy.value = false;
    }
  }
}

function sameCurrentDepartment(before: ProjectDepartmentView) {
  return items.value.some((item) => item.department_id === before.department_id
    && item.etag === before.etag && item.state === "ACTIVE"
    && item.code === before.code && item.name === before.name
    && item.created_at === before.created_at);
}
function startDeactivate(item: ProjectDepartmentView) {
  if (!canCreate() || busy.value || writeBusy.value || requireFreshRead.value
    || writeReceipt.value || deactivateReceipt.value || deactivatePending.value
    || deactivateBlocked.value || item.state !== "ACTIVE" || !sameCurrentDepartment(item)) return;
  edit.value = null; editConfirmed.value = false;
  deactivateEditor.value = Object.freeze({ ...item });
  deactivateConfirmed.value = false;
  error.value = "";
}
function canRecoverDeactivate() {
  const attempt = deactivatePending.value;
  return !!attempt && canCreate() && !busy.value && !writeBusy.value
    && !requireFreshRead.value && !deactivateBlocked.value
    && attempt.project === route.params.projectId
    && attempt.actor === session.view?.user.user_id && sameCurrentDepartment(attempt.before);
}
async function submitDeactivate() {
  if (busy.value || writeBusy.value || requireFreshRead.value || deactivateBlocked.value) return;
  const recovery = deactivatePending.value;
  if (recovery && (!canRecoverDeactivate() || !confirmOriginal.value)) return;
  if (!recovery && (!canCreate() || !deactivateEditor.value || !deactivateConfirmed.value
    || !sameCurrentDepartment(deactivateEditor.value))) return;
  const attempt = recovery ?? Object.freeze({ project: route.params.projectId as string,
    actor: identity!.user.user_id, before: deactivateEditor.value!, key: crypto.randomUUID() });
  const current = ++generation;
  deactivatePending.value = attempt;
  deactivateEditor.value = null; deactivateConfirmed.value = false; confirmOriginal.value = false;
  writeBusy.value = true; error.value = "";
  try {
    const receipt = await deactivator.deactivate(attempt.project, attempt.before, attempt.key);
    if (!mounted || current !== generation || route.params.projectId !== attempt.project
      || !canCreate() || session.view?.user.user_id !== attempt.actor) return;
    deactivateReceipt.value = receipt;
    deactivatePending.value = null;
    requireFreshRead.value = true;
  } catch (failure) {
    if (!mounted || current !== generation || route.params.projectId !== attempt.project) return;
    requireFreshRead.value = true;
    if (!(failure instanceof ProjectDepartmentDeactivateError) || failure.uncertain) {
      error.value = "停用结果无法确认。原目标、版本和操作记录保留在本页；先核对部门历史与审计，勿生成新操作记录。";
    } else if (failure.code === "CONFLICT_IDEMPOTENCY") {
      deactivatePending.value = null;
      deactivateBlocked.value = true;
      error.value = "原操作记录与请求冲突，已停止本页后续停用。请核对部门历史和审计。";
    } else {
      deactivatePending.value = null;
      error.value = failure.message + " 请重新读取部门历史后再决定。";
    }
  } finally {
    if (mounted && current === generation) {
      items.value = []; nextCursor.value = null; loaded.value = false;
      writeBusy.value = false;
    }
  }
}

watch(() => route.params.projectId, () => {
  generation += 1;
  items.value = []; nextCursor.value = null; loaded.value = false; error.value = ""; busy.value = false;
  writeBusy.value = false; edit.value = null; editConfirmed.value = false;
  writeReceipt.value = null; requireFreshRead.value = false;
  deactivateEditor.value = null; deactivateConfirmed.value = false; confirmOriginal.value = false;
  deactivatePending.value = null; deactivateReceipt.value = null; deactivateBlocked.value = false;
  void load(null, true);
}, { immediate: true });
onUnmounted(() => { mounted = false; generation += 1; deactivatePending.value = null; });
</script>

<template>
  <section class="department-panel" aria-labelledby="department-list-title" :aria-busy="busy">
    <p class="section-kicker">项目组织</p>
    <h1 id="department-list-title">项目部门历史</h1>
    <p>可见范围由服务器按当前项目实时确认；列表包含已停用部门，跨页内容不代表同一时刻的快照。</p>
    <p><RouterLink :to="{ name: 'project-detail', params: { projectId: route.params.projectId } }">返回项目详情</RouterLink></p>
    <p v-if="canCreate() && !deactivatePending && !deactivateBlocked"><RouterLink :to="{ name: 'project-department-create', params: { projectId: route.params.projectId } }">创建项目部门</RouterLink></p>
    <template v-if="!identity">
      <p role="status">尚未读取当前身份。请先登录，或在账户页读取当前身份。</p>
      <RouterLink to="/login">前往账户与登录</RouterLink>
    </template>
    <template v-else-if="identity.password_change_required">
      <p role="status">当前账户须先修改密码，暂不能读取项目部门。</p>
      <RouterLink to="/login">前往账户与登录</RouterLink>
    </template>
    <template v-else>
      <button type="button" :disabled="busy || writeBusy" @click="load(null, true)">{{ busy ? '正在读取…' : '刷新部门列表' }}</button>
      <p v-if="busy" role="status">正在确认项目部门访问权限…</p>
      <p v-if="error" role="alert">{{ error }}</p>
      <p v-if="deactivateBlocked" role="alert">原操作记录冲突，已停止本页后续停用；请核对部门历史和审计。</p>
      <p v-if="writeReceipt" role="status">本次修改回执：{{ writeReceipt.name }}（{{ writeReceipt.code }}）· {{ writeReceipt.etag }}。这不是当前状态证明，请刷新部门历史重新读取。</p>
      <p v-if="deactivateReceipt" role="status">本次停用首次回执：{{ deactivateReceipt.first_result.name }}（{{ deactivateReceipt.first_result.code }}）· {{ deactivateReceipt.first_result.etag }}。这不是当前状态证明，请刷新部门历史重新读取。</p>
      <p v-if="requireFreshRead && !writeReceipt && !deactivateReceipt" role="status">旧列表已清除。成功重新读取部门历史前，不能再次操作。</p>
      <p v-if="deactivatePending" role="status">原停用操作仅保留在本页内存。离页后若结果仍不确定，先核对历史和审计，勿生成新操作记录。</p>
      <p v-if="loaded && items.length === 0" role="status">当前项目没有部门记录。</p>
      <ul v-if="items.length" aria-label="项目部门历史">
        <li v-for="item in items" :key="item.department_id">
          <strong>{{ item.name }}</strong>
          <span>编号：{{ item.code }} · {{ item.state === 'ACTIVE' ? '有效' : '已停用' }}</span>
          <span>创建：<time :datetime="item.created_at">{{ new Date(item.created_at).toLocaleString('zh-CN') }}</time></span>
          <button v-if="canCreate() && item.state === 'ACTIVE' && !requireFreshRead && !writeReceipt && !deactivateReceipt && !deactivatePending && !deactivateBlocked"
            type="button" :disabled="busy || writeBusy" @click="startEdit(item)">修改此部门</button>
          <button v-if="canCreate() && item.state === 'ACTIVE' && !requireFreshRead && !writeReceipt && !deactivateReceipt && !deactivatePending && !deactivateBlocked"
            type="button" :disabled="busy || writeBusy" @click="startDeactivate(item)">停用此部门</button>
        </li>
      </ul>
      <form v-if="edit && canCreate() && !requireFreshRead && !writeReceipt" @submit.prevent="submitEdit">
        <h2>修改部门：{{ edit.name }}（{{ edit.code }}）</h2>
        <p>基于刚读取的 {{ edit.etag }} 版本；其他人修改后服务器将拒绝本次提交。</p>
        <label for="department-edit-code">部门编号</label>
        <input id="department-edit-code" v-model="editCode" required maxlength="64" autocomplete="off" :disabled="writeBusy" />
        <label for="department-edit-name">部门名称</label>
        <input id="department-edit-name" v-model="editName" required maxlength="255" autocomplete="off" :disabled="writeBusy" />
        <label><input v-model="editConfirmed" type="checkbox" :disabled="writeBusy" />我已核对当前项目、部门与修改内容</label>
        <button type="submit" :disabled="busy || writeBusy || !editConfirmed">{{ writeBusy ? '正在提交…' : '确认修改部门' }}</button>
      </form>
      <form v-if="deactivateEditor && canCreate() && !requireFreshRead && !deactivateBlocked"
        @submit.prevent="submitDeactivate">
        <h2>停用部门：{{ deactivateEditor.name }}（{{ deactivateEditor.code }}）</h2>
        <p>基于刚读取的 {{ deactivateEditor.etag }} 版本。停用后保留历史；若仍有成员使用此部门，服务器会拒绝。</p>
        <label><input v-model="deactivateConfirmed" type="checkbox" :disabled="writeBusy" />我已核对当前项目、部门及停用影响</label>
        <button type="submit" :disabled="busy || writeBusy || !deactivateConfirmed">{{ writeBusy ? '正在提交…' : '确认停用部门' }}</button>
      </form>
      <form v-if="deactivatePending && canCreate() && !deactivateBlocked" @submit.prevent="submitDeactivate">
        <h2>核对原停用操作</h2>
        <p>原部门：{{ deactivatePending.before.name }}（{{ deactivatePending.before.code }}）· {{ deactivatePending.before.etag }}。只有历史重读显示该部门仍有效且版本未变，才能按原操作记录恢复；否则请核对审计。</p>
        <label><input v-model="confirmOriginal" type="checkbox" name="confirm_original_deactivate"
          :disabled="busy || writeBusy || !canRecoverDeactivate()" />我确认只复用原目标、版本和操作记录</label>
        <button type="submit" :disabled="busy || writeBusy || !confirmOriginal || !canRecoverDeactivate()">按原操作记录恢复停用</button>
      </form>
      <button v-if="nextCursor" type="button" :disabled="busy || writeBusy" @click="load(nextCursor)">加载更多部门</button>
    </template>
  </section>
</template>

<style scoped>
.department-panel { max-width: 52rem; margin: 1rem auto; padding: 1.5rem; background: #fff; border-radius: 1rem; }
.department-panel p { line-height: 1.65; }
.department-panel ul { display: grid; gap: .7rem; padding-left: 1.4rem; }
.department-panel li { display: grid; gap: .3rem; overflow-wrap: anywhere; }
.department-panel form { display: grid; gap: .7rem; margin-top: 1rem; }
.department-panel form input:not([type="checkbox"]) { width: 100%; padding: .55rem; }
.department-panel [role="alert"] { color: #a21d25; }
</style>
