<script setup lang="ts">
import { inject, onMounted, onUnmounted, ref, toRaw, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { sessionClientKey } from "@/modules/auth/api/sessionContext";
import { ProjectMemberChoicesClient, MemberChoicesError,
  type ActiveDepartment, type MemberCandidate } from "@/modules/project/api/projectMemberChoicesClient";
import { ProjectMemberCreateClient, ProjectMemberCreateError,
  type ProjectMemberCreateInput } from "@/modules/project/api/projectMemberCreateClient";
import type { ProjectMemberView } from "@/modules/project/api/projectMemberReadClient";

const props = defineProps<{ session?: SessionClient; choices?: ProjectMemberChoicesClient;
  creator?: ProjectMemberCreateClient }>();
const session = toRaw(props.session ?? inject(sessionClientKey, null) ?? new SessionClient());
const choices = toRaw(props.choices ?? new ProjectMemberChoicesClient(session));
const creator = toRaw(props.creator ?? new ProjectMemberCreateClient(session));
const route = useRoute();
const identity = session.view;
const initialProjectId = typeof route.params.projectId === "string" ? route.params.projectId : "";
const allowedAtEntry = !!identity && !identity.password_change_required && session.canSubmit
  && identity.authorized_projects.some((item) => item.project_id === initialProjectId && item.role === "PROJECT_MANAGER");
const departments = ref<readonly ActiveDepartment[]>([]);
const loaded = ref(false);
const busy = ref(false);
const error = ref("");
const username = ref("");
const candidate = ref<MemberCandidate | null>(null);
const role = ref<ProjectMemberView["role"] | "">("");
const departmentId = ref("");
const confirmChoice = ref(false);
const confirmRetry = ref(false);
const created = ref<ProjectMemberView | null>(null);
const pending = ref<{ readonly projectId: string; readonly userId: string;
  readonly input: ProjectMemberCreateInput; readonly key: string; readonly actorId: string } | null>(null);
const recoveryBlocked = ref(false);
let mounted = true;
let generation = 0;

function stillAuthorized() {
  return mounted && allowedAtEntry && route.params.projectId === initialProjectId
    && session.canSubmit && session.view?.user.user_id === identity?.user.user_id;
}
watch(username, () => { if (!pending.value) { candidate.value = null; confirmChoice.value = false; } });
watch([role, departmentId], () => { if (!pending.value) confirmChoice.value = false; });
watch(() => route.params.projectId, () => {
  generation += 1; candidate.value = null; departments.value = []; loaded.value = false;
  if (pending.value) recoveryBlocked.value = true;
});
onUnmounted(() => { mounted = false; generation += 1; pending.value = null; });

async function loadDepartments() {
  if (!stillAuthorized() || busy.value || pending.value || created.value) return;
  const current = generation;
  busy.value = true; error.value = ""; loaded.value = false; departments.value = []; departmentId.value = "";
  try {
    const items = await choices.activeDepartments(initialProjectId);
    if (!stillAuthorized() || current !== generation) return;
    departments.value = items; loaded.value = true;
  } catch (failure) {
    if (mounted && current === generation) error.value = failure instanceof MemberChoicesError
      ? failure.message : "暂时无法读取有效部门，请稍后重试。";
  } finally { if (mounted && current === generation) busy.value = false; }
}
onMounted(() => { void loadDepartments(); });

async function resolveCandidate() {
  if (!stillAuthorized() || busy.value || pending.value || created.value || !loaded.value) return;
  const current = generation;
  const searched = username.value;
  candidate.value = null; confirmChoice.value = false;
  busy.value = true; error.value = "";
  try {
    const result = await choices.candidate(initialProjectId, searched);
    if (!stillAuthorized() || current !== generation || searched !== username.value) return;
    candidate.value = result;
    if (!result) error.value = "未找到可加入的启用用户。请核对准确用户名；不显示其他项目归属。";
  } catch (failure) {
    if (mounted && current === generation) error.value = failure instanceof MemberChoicesError
      ? failure.message : "暂时无法确认该用户，请稍后重试。";
  } finally { if (mounted && current === generation) busy.value = false; }
}

function snapshot(): ProjectMemberCreateInput | null {
  if (!candidate.value || !departments.value.some((item) => item.department_id === departmentId.value)
    || !["PROJECT_MANAGER", "IMPLEMENTATION_MEMBER", "CUSTOMER_MANAGER", "CUSTOMER_MEMBER"].includes(role.value)
    || !confirmChoice.value) return null;
  return Object.freeze({ user_id: candidate.value.user_id,
    role: role.value as ProjectMemberView["role"], department_id: departmentId.value });
}
async function submit() {
  if (!stillAuthorized() || busy.value || recoveryBlocked.value || created.value) return;
  if (pending.value && (!confirmRetry.value || pending.value.actorId !== session.view?.user.user_id)) return;
  const attempt = pending.value ?? (() => {
    const input = snapshot();
    return input && identity ? Object.freeze({ projectId: initialProjectId, userId: input.user_id,
      input, key: crypto.randomUUID(), actorId: identity.user.user_id }) : null;
  })();
  if (!attempt) { error.value = "请先确认准确用户名、成员角色、有效部门，并勾选确认。"; return; }
  pending.value = attempt; confirmRetry.value = false; busy.value = true; error.value = "";
  try {
    const result = await creator.create(attempt.projectId, attempt.input, attempt.key);
    if (!stillAuthorized()) return;
    created.value = result; pending.value = null;
  } catch (failure) {
    if (!mounted) return;
    if (failure instanceof ProjectMemberCreateError && failure.uncertain) {
      error.value = "创建结果无法确认。请勿新建操作；核对成员记录后，明确确认并复用原操作记录重试。";
    } else if (failure instanceof ProjectMemberCreateError && failure.code === "CONFLICT_IDEMPOTENCY") {
      recoveryBlocked.value = true;
      error.value = "原操作记录与输入不一致，已停止页面内重试，请核对成员记录。";
    } else if (failure instanceof ProjectMemberCreateError) {
      pending.value = null; candidate.value = null; confirmChoice.value = false;
      error.value = failure.message;
    } else {
      error.value = "创建结果无法确认，请勿以新操作记录重复创建。";
    }
  } finally { if (mounted) busy.value = false; }
}
</script>

<template>
  <section class="member-create" aria-labelledby="member-create-title" :aria-busy="busy">
    <p class="section-kicker">项目权限</p>
    <h1 id="member-create-title">添加项目成员</h1>
    <p>请先核对准确用户名，再选择角色和当前有效部门。候选并不代表已加入；服务器会在提交时重新核验。</p>
    <p><RouterLink :to="{ name: 'project-members', params: { projectId: initialProjectId } }">返回成员历史</RouterLink></p>
    <template v-if="!allowedAtEntry || !stillAuthorized() && !busy">
      <p role="status">需要当前项目负责人可提交的登录会话；会话或项目变化后请重新登录。</p>
      <RouterLink to="/login">前往账户与登录</RouterLink>
    </template>
    <template v-else>
      <p v-if="error" role="alert">{{ error }}</p>
      <template v-if="created">
        <p role="status">成员创建已确认：{{ created.user.display_name }} · {{ created.department.name }}。</p>
        <p>成员状态：有效。可返回成员历史核对。</p>
      </template>
      <template v-else>
        <button v-if="!pending" type="button" :disabled="busy" @click="loadDepartments">重新读取有效部门</button>
        <p v-if="loaded && departments.length === 0" role="status">当前项目没有可选的有效部门，请先由负责人维护部门。</p>
        <form @submit.prevent="submit">
          <label for="member-username">准确用户名</label>
          <input id="member-username" v-model="username" required maxlength="255" autocomplete="off" :disabled="busy || !!pending" />
          <button v-if="!pending" type="button" :disabled="busy || !loaded || !username.trim()" @click="resolveCandidate">查找可加入用户</button>
          <p v-if="candidate" role="status">已找到候选：{{ candidate.display_name }}。请确认这是目标用户。</p>
          <label for="member-role">项目角色</label>
          <select id="member-role" v-model="role" required :disabled="busy || !!pending">
            <option value="">请选择角色</option>
            <option value="PROJECT_MANAGER">项目负责人</option>
            <option value="IMPLEMENTATION_MEMBER">实施成员</option>
            <option value="CUSTOMER_MANAGER">客户负责人</option>
            <option value="CUSTOMER_MEMBER">客户成员</option>
          </select>
          <label for="member-department">所属部门</label>
          <select id="member-department" v-model="departmentId" required :disabled="busy || !!pending || !loaded">
            <option value="">请选择有效部门</option>
            <option v-for="item in departments" :key="item.department_id" :value="item.department_id">{{ item.name }}（{{ item.code }}）</option>
          </select>
          <label v-if="!pending"><input v-model="confirmChoice" type="checkbox" :disabled="busy || !candidate" /> 我已核对候选用户、角色和部门</label>
          <p v-if="pending" role="status">原操作仅保留在本页内存。离开或刷新后若结果未确认，请先核对成员与审计记录，勿直接使用新操作重建。</p>
          <label v-if="pending && !recoveryBlocked"><input v-model="confirmRetry" name="confirm_original_member" type="checkbox" :disabled="busy" /> 我确认复用原用户、角色、部门和原操作记录恢复</label>
          <button type="submit" :disabled="busy || !session.canSubmit || !loaded || recoveryBlocked || !!(pending && !confirmRetry)">
            {{ busy ? '正在提交…' : pending ? '按原操作记录重试' : '添加成员' }}
          </button>
        </form>
      </template>
    </template>
  </section>
</template>

<style scoped>
.member-create { max-width: 44rem; margin: 1rem auto; padding: 1.5rem; background: #fff; border-radius: 1rem; }
.member-create form { display: grid; gap: .7rem; margin-top: 1rem; }
.member-create input:not([type="checkbox"]), .member-create select { width: 100%; padding: .55rem; }
.member-create p { line-height: 1.65; }
.member-create [role="alert"] { color: #a21d25; }
.member-create button:disabled { opacity: .55; cursor: not-allowed; }
</style>
