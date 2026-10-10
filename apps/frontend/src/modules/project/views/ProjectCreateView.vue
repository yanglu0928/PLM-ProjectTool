<script setup lang="ts">
import { inject, onMounted, onUnmounted, ref, toRaw } from "vue";
import { RouterLink } from "vue-router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { sessionClientKey } from "@/modules/auth/api/sessionContext";
import { AdminUserListClient, UserCandidateError, type UserCandidate } from "@/modules/auth/api/adminUserListClient";
import { ProjectCreateClient, ProjectCreateError, type ProjectCreateInput } from "@/modules/project/api/projectCreateClient";
import type { ProjectView } from "@/modules/project/api/projectReadClient";

const props = defineProps<{ session?: SessionClient; users?: AdminUserListClient; creator?: ProjectCreateClient }>();
const session = toRaw(props.session ?? inject(sessionClientKey, null) ?? new SessionClient());
const users = toRaw(props.users ?? new AdminUserListClient());
const creator = toRaw(props.creator ?? new ProjectCreateClient(session));
const identity = session.view;
const allowedAtEntry = identity?.deployment_role === "DEPLOYMENT_ADMIN"
  && !identity.password_change_required && session.canSubmit;
const candidates = ref<UserCandidate[]>([]);
const cursor = ref<string | null>(null);
const loaded = ref(false);
const busy = ref(false);
const error = ref("");
const code = ref("");
const name = ref("");
const selectedUserId = ref("");
const departmentCode = ref("");
const departmentName = ref("");
const useDepartment = ref(false);
const confirmRetry = ref(false);
const created = ref<ProjectView | null>(null);
const pending = ref<{ readonly input: ProjectCreateInput; readonly key: string; readonly adminId: string } | null>(null);
const recoveryBlocked = ref(false);
let mounted = true;

function stillAuthorized() { return mounted && allowedAtEntry && session.canSubmit
  && session.view?.user.user_id === identity?.user.user_id; }
async function loadUsers(next = false) {
  if (!stillAuthorized() || busy.value || (next && !cursor.value) || pending.value) return;
  busy.value = true;
  error.value = "";
  const prior = next ? cursor.value : null;
  if (!next) { candidates.value = []; cursor.value = null; loaded.value = false; selectedUserId.value = ""; }
  try {
    const page = await users.page(prior);
    if (!stillAuthorized()) { if (mounted) error.value = "当前会话已变化，请核对创建结果后重新登录。"; return; }
    const combined = next ? [...candidates.value, ...page.items] : [...page.items];
    if (new Set(combined.map((item) => item.user_id)).size !== combined.length) throw new UserCandidateError("USER_LIST_UNAVAILABLE");
    candidates.value = combined;
    cursor.value = page.next_cursor;
    loaded.value = true;
  } catch (failure) {
    if (mounted) {
      candidates.value = []; cursor.value = null; loaded.value = false; selectedUserId.value = "";
      error.value = failure instanceof UserCandidateError ? failure.message : "暂时无法读取用户列表，请稍后重试。";
    }
  } finally { if (mounted) busy.value = false; }
}
onMounted(() => { void loadUsers(); });
onUnmounted(() => { mounted = false; pending.value = null; });

function inputSnapshot(): ProjectCreateInput | null {
  const candidate = candidates.value.find((item) => item.user_id === selectedUserId.value);
  if (!candidate || candidate.account_state !== "ENABLED") return null;
  if (useDepartment.value && (!departmentCode.value.trim() || !departmentName.value.trim())) return null;
  return Object.freeze({ code: code.value, name: name.value, initial_manager_user_id: candidate.user_id,
    ...(useDepartment.value ? { department: Object.freeze({ code: departmentCode.value, name: departmentName.value }) } : {}) });
}
async function submit() {
  if (!stillAuthorized() || busy.value || recoveryBlocked.value || created.value) return;
  if (pending.value && (!confirmRetry.value || pending.value.adminId !== session.view?.user.user_id)) return;
  const attempt = pending.value ?? (() => {
    const input = inputSnapshot();
    return input && identity ? Object.freeze({ input, key: crypto.randomUUID(), adminId: identity.user.user_id }) : null;
  })();
  if (!attempt) { error.value = "请先填写项目信息并选择启用的负责人候选。"; return; }
  pending.value = attempt;
  confirmRetry.value = false;
  busy.value = true;
  error.value = "";
  try {
    const result = await creator.create(attempt.input, attempt.key);
    if (!stillAuthorized()) return;
    created.value = result;
    pending.value = null;
  } catch (failure) {
    if (!mounted) return;
    if (failure instanceof ProjectCreateError && failure.uncertain) {
      error.value = "创建结果无法确认。请勿新建操作；核对原项目信息后，明确确认并复用原操作记录重试。";
    } else if (failure instanceof ProjectCreateError && failure.code === "CONFLICT_IDEMPOTENCY") {
      recoveryBlocked.value = true;
      error.value = "原操作记录与输入不一致，已停止页面内重试，请核对结果。";
    } else if (failure instanceof ProjectCreateError) {
      pending.value = null;
      error.value = failure.message;
    } else {
      error.value = "创建结果无法确认，请勿以新操作记录重复创建。";
    }
  } finally { if (mounted) busy.value = false; }
}
</script>

<template>
  <section class="project-create" aria-labelledby="create-title" :aria-busy="busy">
    <p class="section-kicker">部署管理</p>
    <h1 id="create-title">创建项目</h1>
    <p>首位负责人须为启用账户。候选列表不显示其是否已属于其他项目；服务器会在提交时最终核验。</p>
    <template v-if="!identity || !allowedAtEntry">
      <p role="status">需要已登录且可提交的部署管理员会话；刷新后请重新登录。</p>
      <RouterLink to="/login">前往账户与登录</RouterLink>
    </template>
    <template v-else>
      <p>当前部署管理员：{{ identity.user.username_display }}</p>
      <p v-if="error" role="alert">{{ error }}</p>
      <template v-if="created">
        <p role="status">项目创建已确认：{{ created.name }}（{{ created.code }}）。项目 ID：{{ created.project_id }}。</p>
        <p>部署管理员不会自动成为项目成员；请由首位负责人登录查看该项目。</p>
      </template>
      <template v-else>
        <button v-if="!pending" type="button" :disabled="busy" @click="loadUsers(false)">重新读取候选用户</button>
        <p v-if="loaded && candidates.length === 0" role="status">当前没有可选的用户；请先由部署管理员创建并启用账户。</p>
        <form @submit.prevent="submit">
          <label for="new-project-code">项目编号</label>
          <input id="new-project-code" v-model="code" required maxlength="64" :disabled="busy || !!pending" />
          <label for="new-project-name">项目名称</label>
          <input id="new-project-name" v-model="name" required maxlength="255" :disabled="busy || !!pending" />
          <label for="new-project-manager">首位项目负责人</label>
          <select id="new-project-manager" v-model="selectedUserId" required :disabled="busy || !!pending || !loaded">
            <option value="">请选择启用账户</option>
            <option v-for="user in candidates" :key="user.user_id" :value="user.user_id" :disabled="user.account_state !== 'ENABLED'">
              {{ user.username_display }}（{{ user.account_state === 'ENABLED' ? '启用' : '停用' }} · {{ user.user_id }}）
            </option>
          </select>
          <button v-if="cursor && !pending" type="button" :disabled="busy" @click="loadUsers(true)">加载更多候选</button>
          <label><input v-model="useDepartment" type="checkbox" :disabled="busy || !!pending" /> 指定初始部门（不勾选则由系统创建默认部门）</label>
          <template v-if="useDepartment">
            <label for="new-department-code">部门编号</label>
            <input id="new-department-code" v-model="departmentCode" required maxlength="64" :disabled="busy || !!pending" />
            <label for="new-department-name">部门名称</label>
            <input id="new-department-name" v-model="departmentName" required maxlength="255" :disabled="busy || !!pending" />
          </template>
          <p v-if="pending" role="status">原操作仅保留在本页内存。离开或刷新后如结果未确认，请核对项目与审计记录，勿直接使用新操作重建。</p>
          <label v-if="pending && !recoveryBlocked">
            <input v-model="confirmRetry" name="confirm_original_create" type="checkbox" :disabled="busy" /> 我确认继续使用原项目、原负责人和原操作记录恢复
          </label>
          <button type="submit" :disabled="busy || !session.canSubmit || !loaded || recoveryBlocked || !!(pending && !confirmRetry)">
            {{ busy ? '正在提交…' : pending ? '按原操作记录重试' : '创建项目' }}
          </button>
        </form>
      </template>
    </template>
  </section>
</template>

<style scoped>
.project-create { max-width: 44rem; margin: 1rem auto; padding: 1.5rem; background: #fff; border-radius: 1rem; }
.project-create form { display: grid; gap: .7rem; margin-top: 1rem; }
.project-create input:not([type="checkbox"]), .project-create select { width: 100%; padding: .55rem; }
.project-create p { line-height: 1.65; }
.project-create [role="alert"] { color: #a21d25; }
.project-create button:disabled { opacity: .55; cursor: not-allowed; }
</style>
