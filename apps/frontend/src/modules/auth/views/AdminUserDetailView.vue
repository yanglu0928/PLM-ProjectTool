<script setup lang="ts">
import { inject, onUnmounted, ref, toRaw, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { sessionClientKey } from "@/modules/auth/api/sessionContext";
import { AdminUserDetailClient, AdminUserDetailError } from "@/modules/auth/api/adminUserDetailClient";
import { AdminUserStateClient, AdminUserStateError, type UserStateAction,
  type UserStateView } from "@/modules/auth/api/adminUserStateClient";

const props = defineProps<{ session?: SessionClient; details?: AdminUserDetailClient;
  states?: AdminUserStateClient }>();
const session = toRaw(props.session ?? inject(sessionClientKey, null) ?? new SessionClient());
const details = toRaw(props.details ?? new AdminUserDetailClient());
const states = toRaw(props.states ?? new AdminUserStateClient(session));
const route = useRoute();
const identity = session.view;
const allowedAtEntry = identity?.deployment_role === "DEPLOYMENT_ADMIN" && !identity.password_change_required;
const current = ref<UserStateView | null>(null);
const firstResult = ref<UserStateView | null>(null);
const pending = ref<{ readonly adminId: string; readonly userId: string; readonly username: string;
  readonly action: UserStateAction; readonly etag: string; readonly key: string } | null>(null);
const confirmAction = ref(false);
const confirmRecovery = ref(false);
const recoveryBlocked = ref(false);
const busy = ref(false);
const error = ref("");
let generation = 0;
let mounted = true;

function targetId(): string { return typeof route.params.userId === "string" ? route.params.userId : ""; }
function sameAdmin() {
  return mounted && allowedAtEntry && session.view?.user.user_id === identity?.user.user_id;
}
function canWrite() { return sameAdmin() && session.canSubmit; }
async function load() {
  if (!sameAdmin() || busy.value || pending.value) return;
  const request = ++generation;
  busy.value = true;
  current.value = null;
  confirmAction.value = false;
  error.value = "";
  try {
    const result = await details.get(targetId());
    if (request !== generation || !mounted) return;
    if (!sameAdmin()) throw new AdminUserDetailError("AUTH_SESSION_EXPIRED");
    current.value = result;
  } catch (failure) {
    if (request === generation && mounted) {
      current.value = null;
      error.value = failure instanceof AdminUserDetailError ? failure.message : "暂时无法读取用户详情，请稍后重试。";
    }
  } finally { if (request === generation && mounted) busy.value = false; }
}

watch(() => route.params.userId, () => {
  generation += 1;
  current.value = null;
  firstResult.value = null;
  pending.value = null;
  recoveryBlocked.value = false;
  busy.value = false;
  error.value = "";
  void load();
}, { immediate: true });
onUnmounted(() => { mounted = false; generation += 1; pending.value = null; });

async function submit(action: UserStateAction) {
  if (!canWrite() || busy.value || recoveryBlocked.value) return;
  const old = pending.value;
  if (old && (!confirmRecovery.value || old.userId !== targetId() || old.action !== action
    || old.adminId !== session.view?.user.user_id)) return;
  if (!old && (!current.value || !confirmAction.value
    || action !== (current.value.account_state === "ENABLED" ? "disable" : "enable"))) return;
  const attempt = old ?? Object.freeze({ adminId: identity!.user.user_id, userId: current.value!.user_id,
    username: current.value!.username_display, action, etag: current.value!.etag, key: crypto.randomUUID() });
  pending.value = attempt;
  firstResult.value = null;
  confirmAction.value = false;
  confirmRecovery.value = false;
  busy.value = true;
  error.value = "";
  try {
    const result = await states.change(attempt.userId, attempt.action, attempt.etag, attempt.key);
    if (!mounted || attempt.userId !== targetId()) return;
    firstResult.value = result;
    current.value = null;
    pending.value = null;
    if (!sameAdmin()) {
      error.value = "首次操作结果已返回，但当前会话变化；请重新登录核对当前状态。";
      return;
    }
  } catch (failure) {
    if (!mounted || attempt.userId !== targetId()) return;
    current.value = null;
    if (!(failure instanceof AdminUserStateError) || failure.uncertain) {
      error.value = "结果无法确认。仅可复用原操作记录与原版本恢复；不要换动作或新建操作。";
    } else if (failure instanceof AdminUserStateError && failure.code === "CONFLICT_IDEMPOTENCY") {
      recoveryBlocked.value = true;
      error.value = "原操作记录与请求不一致，已停止页面内重试；请核对审计记录。";
    } else {
      pending.value = null;
      error.value = failure.message;
    }
    return;
  } finally { if (mounted) busy.value = false; }
  // A state command returns its immutable first result, never a current-state proof.
  await load();
}
</script>

<template>
  <section class="user-detail" aria-labelledby="user-detail-title" :aria-busy="busy">
    <p class="section-kicker">部署管理</p>
    <h1 id="user-detail-title">用户账户详情</h1>
    <p><RouterLink to="/admin/users">返回用户列表</RouterLink></p>
    <p>账户状态以服务器当前详情为准；启停操作的首次回执可能是历史结果，不能代替当前状态。</p>
    <template v-if="!identity || !allowedAtEntry">
      <p role="status">需要已登录且不受改密限制的部署管理员会话。</p>
      <RouterLink to="/login">前往账户与登录</RouterLink>
    </template>
    <template v-else>
      <p>当前部署管理员：{{ identity.user.username_display }}</p>
      <p v-if="error" role="alert">{{ error }}</p>
      <RouterLink v-if="error" to="/login">如会话失效，请重新登录后核对</RouterLink>
      <p v-if="busy" role="status">正在处理账户信息…</p>
      <p v-if="!session.canSubmit" role="status">当前会话仅可读取；启停前需重新登录。</p>
      <RouterLink v-if="!session.canSubmit" to="/login">重新登录</RouterLink>
      <p v-if="firstResult" role="status">首次操作结果：{{ firstResult.username_display }}（{{ firstResult.account_state === 'ENABLED' ? '启用' : '停用' }}，版本 {{ firstResult.etag }}）。这不是当前状态证明。</p>
      <dl v-if="current" aria-label="服务器当前用户详情">
        <dt>用户名</dt><dd>{{ current.username_display }}</dd>
        <dt>用户 ID</dt><dd>{{ current.user_id }}</dd>
        <dt>当前状态</dt><dd>{{ current.account_state === 'ENABLED' ? '启用' : '停用' }}</dd>
        <dt>部署角色</dt><dd>{{ current.deployment_role === 'DEPLOYMENT_ADMIN' ? '部署管理员' : '普通用户' }}</dd>
        <dt>当前版本</dt><dd>{{ current.etag }}</dd>
      </dl>
      <p v-if="current && !pending"><RouterLink :to="`/admin/users/${current.user_id}/name`">修改用户名</RouterLink></p>
      <p v-if="pending" role="status">原操作：{{ pending.username }}，{{ pending.action === 'enable' ? '启用' : '停用' }}，原版本 {{ pending.etag }}。原操作标识只保存在本页内存；若刷新或离开，请先核对当前账户和审计，勿用新标识猜测重试。</p>
      <label v-if="pending && !recoveryBlocked">
        <input v-model="confirmRecovery" type="checkbox" name="confirm_original_user_state" :disabled="busy" />
        我确认复用原目标、原动作、原版本和原操作标识恢复。
      </label>
      <button v-if="pending && !recoveryBlocked" type="button"
        :disabled="busy || !canWrite() || !confirmRecovery" @click="submit(pending.action)">按原操作恢复</button>
      <template v-if="current && !pending">
        <p v-if="current.account_state === 'DISABLED' && current.credential_version === 0">此账户没有可用凭据；不能直接启用，请先核对管理员重置流程。</p>
        <p v-if="current.account_state === 'ENABLED' && current.user_id === identity.user.user_id">停用本人可能使当前会话立即失效；系统会保护最后一名启用的部署管理员。</p>
        <label>
          <input v-model="confirmAction" type="checkbox" name="confirm_user_state" :disabled="busy || !canWrite()" />
          我已核对目标账户、当前状态和版本，并确认{{ current.account_state === 'ENABLED' ? '停用' : '启用' }}。
        </label>
        <button type="button" :disabled="busy || !canWrite() || !confirmAction || (current.account_state === 'DISABLED' && current.credential_version === 0)"
          @click="submit(current.account_state === 'ENABLED' ? 'disable' : 'enable')">
          {{ current.account_state === 'ENABLED' ? '停用账户并撤销其会话' : '启用账户' }}
        </button>
      </template>
      <button v-if="!pending" type="button" :disabled="busy" @click="load">重新读取当前详情</button>
    </template>
  </section>
</template>

<style scoped>
.user-detail { max-width: 48rem; margin: 1rem auto; padding: 1.5rem; background: #fff; border-radius: 1rem; }
.user-detail p { line-height: 1.65; }
.user-detail dl { display: grid; grid-template-columns: minmax(5rem, auto) 1fr; gap: .65rem 1rem; }
.user-detail dt { font-weight: 700; }
.user-detail dd { margin: 0; overflow-wrap: anywhere; }
.user-detail label { display: block; margin: .8rem 0; }
.user-detail button { margin: .4rem .6rem .4rem 0; }
.user-detail button:disabled { opacity: .55; cursor: not-allowed; }
.user-detail [role="alert"] { color: #a21d25; }
</style>
