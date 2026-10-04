<script setup lang="ts">
import { inject, onUnmounted, ref, toRaw, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { sessionClientKey } from "@/modules/auth/api/sessionContext";
import { AdminUserDetailClient, AdminUserDetailError } from "@/modules/auth/api/adminUserDetailClient";
import { AdminUserNameClient, AdminUserNameError } from "@/modules/auth/api/adminUserNameClient";
import type { UserStateView } from "@/modules/auth/api/adminUserStateClient";

const props = defineProps<{ session?: SessionClient; details?: AdminUserDetailClient;
  names?: AdminUserNameClient }>();
const session = toRaw(props.session ?? inject(sessionClientKey, null) ?? new SessionClient());
const details = toRaw(props.details ?? new AdminUserDetailClient());
const names = toRaw(props.names ?? new AdminUserNameClient(session));
const route = useRoute();
const identity = session.view;
const allowedAtEntry = identity?.deployment_role === "DEPLOYMENT_ADMIN" && !identity.password_change_required;
const current = ref<UserStateView | null>(null);
const firstResult = ref<UserStateView | null>(null);
const candidate = ref("");
const confirm = ref(false);
const reviewRequired = ref(false);
const busy = ref(false);
const error = ref("");
const notice = ref("");
let generation = 0;
let mounted = true;

function targetId(): string { return typeof route.params.userId === "string" ? route.params.userId : ""; }
function sameAdmin() {
  return mounted && allowedAtEntry && session.view?.user.user_id === identity?.user.user_id;
}
function canWrite() { return sameAdmin() && session.canSubmit && !reviewRequired.value; }
async function load() {
  if (!sameAdmin() || busy.value) return;
  const request = ++generation;
  busy.value = true;
  current.value = null;
  confirm.value = false;
  error.value = "";
  try {
    const result = await details.get(targetId());
    if (!mounted || request !== generation) return;
    if (!sameAdmin()) throw new AdminUserDetailError("AUTH_SESSION_EXPIRED");
    current.value = result;
    if (!reviewRequired.value) candidate.value = result.username_display;
  } catch (failure) {
    if (mounted && request === generation) {
      current.value = null;
      error.value = failure instanceof AdminUserDetailError ? failure.message : "暂时无法读取当前账户，请稍后重试。";
    }
  } finally { if (mounted && request === generation) busy.value = false; }
}

watch(() => route.params.userId, () => {
  generation += 1;
  current.value = null;
  firstResult.value = null;
  candidate.value = "";
  confirm.value = false;
  reviewRequired.value = false;
  busy.value = false;
  error.value = "";
  notice.value = "";
  void load();
}, { immediate: true });
onUnmounted(() => { mounted = false; generation += 1; });

async function submit() {
  if (!canWrite() || busy.value || !current.value || !confirm.value) return;
  const before = current.value;
  const proposed = candidate.value;
  if (before.user_id !== targetId() || proposed.normalize("NFC").trim() === before.username_display) return;
  const request = ++generation;
  busy.value = true;
  error.value = "";
  notice.value = "";
  confirm.value = false;
  let reconcile = false;
  try {
    const result = await names.change(before, proposed);
    if (!mounted || request !== generation || before.user_id !== targetId()) return;
    firstResult.value = result;
    current.value = null;
    if (!sameAdmin()) {
      error.value = "会话已变化；请重新登录后核对改名结果。";
      return;
    }
    reconcile = true;
  } catch (failure) {
    if (!mounted || request !== generation || before.user_id !== targetId()) return;
    current.value = null;
    if (!(failure instanceof AdminUserNameError) || failure.uncertain) {
      reviewRequired.value = true;
      notice.value = "改名结果无法确认。下方当前详情仅供对账，不能证明本次请求是否执行；请核对审计，不要在本页重试。";
      reconcile = sameAdmin();
    } else {
      error.value = failure.message;
    }
  } finally { if (mounted && request === generation) busy.value = false; }
  if (reconcile) await load();
}
</script>

<template>
  <section class="user-name" aria-labelledby="user-name-title" :aria-busy="busy">
    <p class="section-kicker">部署管理</p>
    <h1 id="user-name-title">修改用户名</h1>
    <p><RouterLink :to="`/admin/users/${targetId()}`">返回用户详情</RouterLink></p>
    <p>用户名也是登录名；更改后原名称不再用于登录。版本以服务器当前详情为准。</p>
    <template v-if="!identity || !allowedAtEntry">
      <p role="status">需要已登录且不受改密限制的部署管理员会话。</p>
      <RouterLink to="/login">前往账户与登录</RouterLink>
    </template>
    <template v-else>
      <p>当前部署管理员：{{ identity.user.username_display }}</p>
      <p v-if="error" role="alert">{{ error }}</p>
      <p v-if="notice" role="alert">{{ notice }}</p>
      <p v-if="busy" role="status">正在处理账户信息…</p>
      <p v-if="!session.canSubmit" role="status">当前会话仅可读取；改名前需重新登录。</p>
      <RouterLink v-if="!session.canSubmit" to="/login">重新登录</RouterLink>
      <p v-if="firstResult" role="status">本次写入回执：{{ firstResult.username_display }}，版本 {{ firstResult.etag }}。这不是当前状态证明。</p>
      <dl v-if="current" aria-label="服务器当前用户详情">
        <dt>用户名</dt><dd>{{ current.username_display }}</dd>
        <dt>用户 ID</dt><dd>{{ current.user_id }}</dd>
        <dt>状态</dt><dd>{{ current.account_state === 'ENABLED' ? '启用' : '停用' }}</dd>
        <dt>当前版本</dt><dd>{{ current.etag }}</dd>
      </dl>
      <form v-if="current && !reviewRequired" @submit.prevent="submit">
        <label for="user-new-name">新用户名</label>
        <input id="user-new-name" v-model="candidate" name="new_user_name" maxlength="255" autocomplete="off"
          required :disabled="busy || !canWrite()" />
        <label>
          <input v-model="confirm" type="checkbox" name="confirm_user_name" :disabled="busy || !canWrite()" />
          我已核对目标用户、当前版本，并确认更改登录名。
        </label>
        <button type="submit" :disabled="busy || !canWrite() || !confirm || !candidate.trim() || candidate.normalize('NFC').trim() === current.username_display">提交改名</button>
      </form>
      <p v-if="reviewRequired" role="status">本页已停止后续改名提交。核对审计与当前详情后，重新进入页面再作新决定。</p>
      <button type="button" :disabled="busy" @click="load">重新读取当前详情</button>
    </template>
  </section>
</template>

<style scoped>
.user-name { max-width: 48rem; margin: 1rem auto; padding: 1.5rem; background: #fff; border-radius: 1rem; }
.user-name p { line-height: 1.65; }
.user-name dl { display: grid; grid-template-columns: minmax(5rem, auto) 1fr; gap: .65rem 1rem; }
.user-name dt { font-weight: 700; }
.user-name dd { margin: 0; overflow-wrap: anywhere; }
.user-name label { display: block; margin: .8rem 0; }
.user-name button { margin: .4rem .6rem .4rem 0; }
.user-name button:disabled { opacity: .55; cursor: not-allowed; }
.user-name [role="alert"] { color: #a21d25; }
</style>
