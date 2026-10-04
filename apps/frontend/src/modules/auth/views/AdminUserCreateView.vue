<script setup lang="ts">
import { inject, onUnmounted, ref, toRaw } from "vue";
import { RouterLink } from "vue-router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { sessionClientKey } from "@/modules/auth/api/sessionContext";
import { AdminUserCreateClient, AdminUserCreateError, type CreatedUserView } from "@/modules/auth/api/adminUserCreateClient";

const props = defineProps<{ session?: SessionClient; creator?: AdminUserCreateClient }>();
const session = toRaw(props.session ?? inject(sessionClientKey, null) ?? new SessionClient());
const creator = toRaw(props.creator ?? new AdminUserCreateClient(session));
const identity = session.view;
const allowedAtEntry = identity?.deployment_role === "DEPLOYMENT_ADMIN"
  && !identity.password_change_required && session.canSubmit;
const username = ref("");
const password = ref("");
const confirmPassword = ref("");
const confirmOriginalAttempt = ref(false);
const pending = ref<{ readonly adminId: string; readonly username: string; readonly key: string } | null>(null);
const recoveryBlocked = ref(false);
const busy = ref(false);
const error = ref("");
const created = ref<CreatedUserView | null>(null);
let mounted = true;

function stillAuthorized() {
  return mounted && allowedAtEntry && session.canSubmit
    && session.view?.user.user_id === identity?.user.user_id;
}
onUnmounted(() => {
  mounted = false;
  password.value = "";
  confirmPassword.value = "";
  pending.value = null;
});

async function submit() {
  if (!stillAuthorized() || busy.value || recoveryBlocked.value || created.value) return;
  if (pending.value && (!confirmOriginalAttempt.value
    || pending.value.adminId !== session.view?.user.user_id)) return;
  if (password.value !== confirmPassword.value) {
    error.value = "两次输入的初始密码不一致。";
    return;
  }
  const attempt = pending.value ?? (identity ? Object.freeze({
    adminId: identity.user.user_id, username: username.value.trim().normalize("NFC"),
    key: crypto.randomUUID(),
  }) : null);
  if (!attempt) return;
  pending.value = attempt;
  confirmOriginalAttempt.value = false;
  busy.value = true;
  error.value = "";
  try {
    // The client captures the write-only password synchronously. Never retain it for recovery.
    const request = creator.create({ username: attempt.username, password: password.value }, attempt.key);
    password.value = "";
    confirmPassword.value = "";
    const result = await request;
    if (!stillAuthorized()) {
      if (mounted) error.value = "当前会话已变化，请核对账户创建结果后重新登录。";
      return;
    }
    created.value = result;
    pending.value = null;
  } catch (failure) {
    if (!mounted) return;
    if (failure instanceof AdminUserCreateError && failure.uncertain) {
      error.value = "账户创建结果无法确认。请留在本页，用原密码、原操作记录恢复；不要以新操作重复创建。";
    } else if (failure instanceof AdminUserCreateError && failure.code === "CONFLICT_IDEMPOTENCY") {
      recoveryBlocked.value = true;
      error.value = "原操作记录与密码或用户名不一致，已停止页面内重试。请核对账户及审计记录。";
    } else if (failure instanceof AdminUserCreateError) {
      pending.value = null;
      error.value = failure.message;
    } else {
      error.value = "账户创建结果无法确认。请勿以新操作重复创建。";
    }
  } finally {
    password.value = "";
    confirmPassword.value = "";
    if (mounted) busy.value = false;
  }
}
</script>

<template>
  <section class="user-create" aria-labelledby="user-create-title" :aria-busy="busy">
    <p class="section-kicker">部署管理</p>
    <h1 id="user-create-title">创建用户账户</h1>
    <p>新账户默认为普通用户，不会自动成为部署管理员。创建后可作为项目负责人候选；是否可任命由服务器在创建项目时核验。</p>
    <template v-if="!identity || !allowedAtEntry">
      <p role="status">需要已登录且可提交的部署管理员会话；刷新后请重新登录。</p>
      <RouterLink to="/login">前往账户与登录</RouterLink>
    </template>
    <template v-else>
      <p>当前部署管理员：{{ identity.user.username_display }}</p>
      <p v-if="error" role="alert">{{ error }}</p>
      <RouterLink v-if="!session.canSubmit" to="/login">会话已失效，请重新登录并先核对创建结果</RouterLink>
      <template v-if="created">
        <p role="status">账户创建已确认：{{ created.username_display }}（{{ created.user_id }}）。状态：启用，角色：普通用户。</p>
        <p>初始密码不会在此回显；请按组织批准的安全方式交付给账户本人。</p>
        <RouterLink to="/projects/new">前往创建项目</RouterLink>
      </template>
      <form v-else @submit.prevent="submit">
        <label for="admin-new-username">用户名</label>
        <input id="admin-new-username" v-model="username" autocomplete="off" required maxlength="255" :disabled="busy || !!pending" />
        <label for="admin-new-password">初始密码</label>
        <input id="admin-new-password" v-model="password" type="password" autocomplete="new-password" required :disabled="busy || recoveryBlocked" />
        <label for="admin-confirm-password">确认初始密码</label>
        <input id="admin-confirm-password" v-model="confirmPassword" type="password" autocomplete="new-password" required :disabled="busy || recoveryBlocked" />
        <p v-if="pending" role="status">原操作标识仅保留在本页内存，不保留密码。请勿刷新或离开；若已离开，先核对用户与审计记录，不要猜测结果。</p>
        <label v-if="pending && !recoveryBlocked">
          <input v-model="confirmOriginalAttempt" name="confirm_original_user_create" type="checkbox" :disabled="busy" />
          我确认重新输入的是上次完全相同的初始密码，并复用原操作记录。
        </label>
        <button type="submit" :disabled="busy || !session.canSubmit || recoveryBlocked || !!(pending && !confirmOriginalAttempt) || !username || !password || !confirmPassword">
          {{ busy ? '正在提交…' : pending ? '按原操作记录恢复' : '创建用户账户' }}
        </button>
      </form>
    </template>
  </section>
</template>

<style scoped>
.user-create { max-width: 44rem; margin: 1rem auto; padding: 1.5rem; background: #fff; border-radius: 1rem; }
.user-create form { display: grid; gap: .7rem; margin-top: 1rem; }
.user-create input:not([type="checkbox"]) { width: 100%; padding: .55rem; }
.user-create p { line-height: 1.65; }
.user-create [role="alert"] { color: #a21d25; }
.user-create button:disabled { opacity: .55; cursor: not-allowed; }
</style>
