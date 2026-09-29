<script setup lang="ts">
import { inject, onUnmounted, ref, toRaw, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";

import { SessionClient } from "@/modules/auth/api/sessionClient";
import { sessionClientKey } from "@/modules/auth/api/sessionContext";
import { ProjectDepartmentReadClient, ProjectDepartmentReadError,
  type ProjectDepartmentView } from "@/modules/project/api/projectDepartmentReadClient";
import { ProjectDepartmentPatchClient, ProjectDepartmentPatchError } from
  "@/modules/project/api/projectDepartmentPatchClient";

const props = defineProps<{ session?: SessionClient; departments?: ProjectDepartmentReadClient;
  patcher?: ProjectDepartmentPatchClient }>();
const session = toRaw(props.session ?? inject(sessionClientKey, null) ?? new SessionClient());
const departments = toRaw(props.departments ?? new ProjectDepartmentReadClient());
const patcher = toRaw(props.patcher ?? new ProjectDepartmentPatchClient(session));
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
    if (replace) { requireFreshRead.value = false; writeReceipt.value = null; }
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
    || writeReceipt.value || item.state !== "ACTIVE"
    || !items.value.some((current) => current.department_id === item.department_id
      && current.etag === item.etag && current.code === item.code && current.name === item.name)) return;
  edit.value = Object.freeze({ ...item });
  editCode.value = item.code;
  editName.value = item.name;
  editConfirmed.value = false;
  error.value = "";
}

async function submitEdit() {
  const before = edit.value;
  if (!canCreate() || !before || !editConfirmed.value || busy.value || writeBusy.value
    || requireFreshRead.value || writeReceipt.value
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

watch(() => route.params.projectId, () => {
  generation += 1;
  items.value = []; nextCursor.value = null; loaded.value = false; error.value = ""; busy.value = false;
  writeBusy.value = false; edit.value = null; editConfirmed.value = false;
  writeReceipt.value = null; requireFreshRead.value = false;
  void load(null, true);
}, { immediate: true });
onUnmounted(() => { mounted = false; generation += 1; });
</script>

<template>
  <section class="department-panel" aria-labelledby="department-list-title" :aria-busy="busy">
    <p class="section-kicker">项目组织</p>
    <h1 id="department-list-title">项目部门历史</h1>
    <p>可见范围由服务器按当前项目实时确认；列表包含已停用部门，跨页内容不代表同一时刻的快照。</p>
    <p><RouterLink :to="{ name: 'project-detail', params: { projectId: route.params.projectId } }">返回项目详情</RouterLink></p>
    <p v-if="canCreate()"><RouterLink :to="{ name: 'project-department-create', params: { projectId: route.params.projectId } }">创建项目部门</RouterLink></p>
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
      <p v-if="writeReceipt" role="status">本次修改回执：{{ writeReceipt.name }}（{{ writeReceipt.code }}）· {{ writeReceipt.etag }}。这不是当前状态证明，请刷新部门历史重新读取。</p>
      <p v-if="requireFreshRead && !writeReceipt" role="status">旧列表已清除。成功重新读取部门历史前，不能再次修改。</p>
      <p v-if="loaded && items.length === 0" role="status">当前项目没有部门记录。</p>
      <ul v-if="items.length" aria-label="项目部门历史">
        <li v-for="item in items" :key="item.department_id">
          <strong>{{ item.name }}</strong>
          <span>编号：{{ item.code }} · {{ item.state === 'ACTIVE' ? '有效' : '已停用' }}</span>
          <span>创建：<time :datetime="item.created_at">{{ new Date(item.created_at).toLocaleString('zh-CN') }}</time></span>
          <button v-if="canCreate() && item.state === 'ACTIVE' && !requireFreshRead && !writeReceipt"
            type="button" :disabled="busy || writeBusy" @click="startEdit(item)">修改此部门</button>
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
