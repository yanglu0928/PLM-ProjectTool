<script setup lang="ts">
import { inject, onUnmounted, ref, toRaw, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";

import { SessionClient } from "@/modules/auth/api/sessionClient";
import { sessionClientKey } from "@/modules/auth/api/sessionContext";
import { ProjectMemberReadClient, ProjectMemberReadError, type ProjectMemberView } from "@/modules/project/api/projectMemberReadClient";
import { ProjectMemberChoicesClient, MemberChoicesError, type ActiveDepartment } from "@/modules/project/api/projectMemberChoicesClient";
import { ProjectMemberPatchClient, ProjectMemberPatchError } from "@/modules/project/api/projectMemberPatchClient";

const props = defineProps<{ session?: SessionClient; members?: ProjectMemberReadClient;
  choices?: ProjectMemberChoicesClient; patcher?: ProjectMemberPatchClient }>();
const session = toRaw(props.session ?? inject(sessionClientKey, null) ?? new SessionClient());
const members = toRaw(props.members ?? new ProjectMemberReadClient());
const choices = toRaw(props.choices ?? new ProjectMemberChoicesClient(session));
const patcher = toRaw(props.patcher ?? new ProjectMemberPatchClient(session));
const identity = session.view;
const route = useRoute();
function projectId() { return typeof route.params.projectId === "string" ? route.params.projectId : ""; }
const items = ref<readonly ProjectMemberView[]>([]);
const nextCursor = ref<string | null>(null);
const loaded = ref(false);
const busy = ref(false);
const error = ref("");
const editor = ref<ProjectMemberView | null>(null);
const departments = ref<readonly ActiveDepartment[]>([]);
const role = ref<ProjectMemberView["role"]>("IMPLEMENTATION_MEMBER");
const departmentId = ref("");
const confirm = ref(false);
const reviewRequired = ref(false);
const firstResult = ref<ProjectMemberView | null>(null);
const notice = ref("");
let generation = 0;
let mounted = true;

function canEdit() {
  return mounted && !reviewRequired.value && session.canSubmit
    && identity?.user.user_id === session.view?.user.user_id
    && !identity?.password_change_required
    && !!session.view?.authorized_projects.some((item) => item.project_id === projectId() && item.role === "PROJECT_MANAGER");
}
watch([role, departmentId], () => { confirm.value = false; });

async function openEditor(item: ProjectMemberView) {
  if (!canEdit() || busy.value || item.state === "REMOVED"
    || !items.value.some((entry) => entry.member_id === item.member_id && entry.etag === item.etag)) return;
  const request = ++generation;
  busy.value = true; error.value = ""; notice.value = "";
  editor.value = null; departments.value = []; confirm.value = false;
  try {
    const active = await choices.activeDepartments(projectId());
    if (!mounted || request !== generation || !canEdit()) return;
    departments.value = active;
    editor.value = item;
    role.value = item.role;
    departmentId.value = active.some((entry) => entry.department_id === item.department.department_id)
      ? item.department.department_id : "";
  } catch (failure) {
    if (mounted && request === generation) error.value = failure instanceof MemberChoicesError
      ? failure.message : "暂时无法读取有效部门，请重新读取成员历史后再试。";
  } finally { if (mounted && request === generation) busy.value = false; }
}

async function submitPatch() {
  const before = editor.value;
  if (!before || !canEdit() || busy.value || !confirm.value
    || !departments.value.some((item) => item.department_id === departmentId.value)
    || (role.value === before.role && departmentId.value === before.department.department_id)) return;
  const request = ++generation;
  const proposedRole = role.value;
  const proposedDepartment = departmentId.value;
  busy.value = true; error.value = ""; notice.value = ""; confirm.value = false;
  let reconcile = false;
  try {
    const result = await patcher.patch(projectId(), before,
      { role: proposedRole, department_id: proposedDepartment });
    if (!mounted || request !== generation || !canEdit()) return;
    firstResult.value = result;
    notice.value = "本次修改有成功回执；下方刷新列表用于核对当前状态。";
    editor.value = null; reconcile = true;
  } catch (failure) {
    if (!mounted || request !== generation) return;
    editor.value = null;
    if (!(failure instanceof ProjectMemberPatchError) || failure.uncertain) {
      reviewRequired.value = true;
      notice.value = "修改结果无法确认。已停止本页后续提交；重新读取成员历史仅供对账，请核对审计后重新进入页面决定，勿直接重试。";
    } else {
      notice.value = `服务器拒绝本次修改：${failure.message} 当前历史将重新读取。`;
    }
    reconcile = true;
  } finally { if (mounted && request === generation) busy.value = false; }
  if (reconcile) await load(null, true);
}

async function load(cursor: string | null, replace: boolean) {
  if (busy.value || !identity || identity.password_change_required) return;
  const current = generation;
  const projectId = route.params.projectId;
  busy.value = true;
  error.value = "";
  if (replace) {
    editor.value = null; departments.value = []; confirm.value = false;
    items.value = []; nextCursor.value = null; loaded.value = false;
  }
  try {
    const page = await members.list(typeof projectId === "string" ? projectId : "", cursor);
    if (current !== generation) return;
    const known = new Set(items.value.map((item) => item.member_id));
    if (page.items.some((item) => known.has(item.member_id))) {
      throw new ProjectMemberReadError("PROJECT_MEMBER_CLIENT_UNAVAILABLE");
    }
    items.value = Object.freeze([...items.value, ...page.items]);
    nextCursor.value = page.next_cursor;
    loaded.value = true;
  } catch (failure) {
    if (current !== generation) return;
    items.value = [];
    nextCursor.value = null;
    loaded.value = false;
    error.value = failure instanceof ProjectMemberReadError
      ? failure.message : "暂时无法读取项目成员，请稍后重试。";
  } finally {
    if (current === generation) busy.value = false;
  }
}

watch(() => route.params.projectId, () => {
  generation += 1;
  editor.value = null;
  departments.value = [];
  confirm.value = false;
  reviewRequired.value = false;
  firstResult.value = null;
  notice.value = "";
  items.value = [];
  nextCursor.value = null;
  loaded.value = false;
  error.value = "";
  busy.value = false;
  void load(null, true);
}, { immediate: true });
onUnmounted(() => { mounted = false; generation += 1; });

const roleNames: Record<ProjectMemberView["role"], string> = {
  PROJECT_MANAGER: "项目负责人", IMPLEMENTATION_MEMBER: "实施成员",
  CUSTOMER_MANAGER: "客户负责人", CUSTOMER_MEMBER: "客户成员",
};
const stateNames: Record<ProjectMemberView["state"], string> = {
  ACTIVE: "有效", SUSPENDED: "暂停", REMOVED: "已移除",
};
</script>

<template>
  <section class="member-panel" aria-labelledby="member-list-title" :aria-busy="busy">
    <p class="section-kicker">项目权限</p>
    <h1 id="member-list-title">项目成员历史</h1>
    <p>可见范围由服务器按当前项目和角色实时确认；列表包含已移除的历史成员。</p>
    <p><RouterLink :to="{ name: 'project-detail', params: { projectId: route.params.projectId } }">返回项目详情</RouterLink></p>
    <p><RouterLink :to="{ name: 'project-member-create', params: { projectId: route.params.projectId } }">添加项目成员</RouterLink></p>
    <template v-if="!identity">
      <p role="status">尚未读取当前身份。请先登录，或在账户页读取当前身份。</p>
      <RouterLink to="/login">前往账户与登录</RouterLink>
    </template>
    <template v-else-if="identity.password_change_required">
      <p role="status">当前账户须先修改密码，暂不能读取项目成员。</p>
      <RouterLink to="/login">前往账户与登录</RouterLink>
    </template>
    <template v-else>
      <button type="button" :disabled="busy" @click="load(null, true)">{{ busy ? '正在读取…' : '刷新成员列表' }}</button>
      <p v-if="busy" role="status">正在确认项目成员访问权限…</p>
      <p v-if="error" role="alert">{{ error }}</p>
      <p v-if="notice" role="alert">{{ notice }}</p>
      <p v-if="firstResult" role="status">本次写入回执：{{ firstResult.user.display_name }} · {{ roleNames[firstResult.role] }} · {{ firstResult.department.name }} · {{ firstResult.etag }}。这不是当前状态证明。</p>
      <p v-if="reviewRequired" role="status">本页已停止后续成员修改。核对审计与当前历史后，重新进入页面作新决定。</p>
      <p v-if="loaded && items.length === 0" role="status">当前项目没有成员记录。</p>
      <ul v-if="items.length" aria-label="项目成员历史">
        <li v-for="item in items" :key="item.member_id">
          <strong>{{ item.user.display_name }}</strong>
          <span>{{ roleNames[item.role] }} · {{ stateNames[item.state] }} · {{ item.department.name }}</span>
          <span>生效：<time :datetime="item.effective_at">{{ new Date(item.effective_at).toLocaleString('zh-CN') }}</time></span>
          <span v-if="item.ended_at">结束：<time :datetime="item.ended_at">{{ new Date(item.ended_at).toLocaleString('zh-CN') }}</time></span>
          <button v-if="canEdit() && item.state !== 'REMOVED'" type="button" :disabled="busy" @click="openEditor(item)">修改角色或部门</button>
        </li>
      </ul>
      <form v-if="editor && canEdit()" aria-label="修改项目成员" @submit.prevent="submitPatch">
        <h2>修改项目成员</h2>
        <p>目标：{{ editor.user.display_name }}（{{ editor.user.user_id }}）</p>
        <p>当前：{{ roleNames[editor.role] }} · {{ editor.department.name }} · {{ stateNames[editor.state] }}，版本 {{ editor.etag }}</p>
        <label for="member-edit-role">新角色</label>
        <select id="member-edit-role" v-model="role" :disabled="busy">
          <option value="PROJECT_MANAGER">项目负责人</option>
          <option value="IMPLEMENTATION_MEMBER">实施成员</option>
          <option value="CUSTOMER_MANAGER">客户负责人</option>
          <option value="CUSTOMER_MEMBER">客户成员</option>
        </select>
        <label for="member-edit-department">新部门（当前有效）</label>
        <select id="member-edit-department" v-model="departmentId" :disabled="busy">
          <option value="">请选择有效部门</option>
          <option v-for="item in departments" :key="item.department_id" :value="item.department_id">{{ item.name }}（{{ item.code }}）</option>
        </select>
        <label><input v-model="confirm" type="checkbox" name="confirm_member_patch" :disabled="busy" />我已核对目标成员、当前版本、目标角色和有效部门</label>
        <button type="submit" :disabled="busy || !confirm || !departmentId || (role === editor.role && departmentId === editor.department.department_id)">提交修改</button>
        <button type="button" :disabled="busy" @click="editor = null">取消</button>
      </form>
      <button v-if="nextCursor" type="button" :disabled="busy" @click="load(nextCursor, false)">读取下一页</button>
    </template>
  </section>
</template>

<style scoped>
.member-panel { max-width: 48rem; margin: 1rem auto; padding: 1.5rem; background: #fff; border-radius: 1rem; }
.member-panel p { line-height: 1.65; }
.member-panel ul { list-style: none; padding: 0; display: grid; gap: .8rem; }
.member-panel li { display: grid; gap: .25rem; border: 1px solid #d6ded7; border-radius: .5rem; padding: .9rem; overflow-wrap: anywhere; }
.member-panel form { display: grid; gap: .7rem; margin-top: 1rem; padding: 1rem; border: 1px solid #d6ded7; border-radius: .5rem; }
.member-panel select { width: 100%; padding: .55rem; }
.member-panel button:disabled { cursor: not-allowed; opacity: .55; }
.member-panel [role="alert"] { color: #a21d25; }
</style>
