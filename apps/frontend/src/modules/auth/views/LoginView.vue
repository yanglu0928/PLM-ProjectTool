<script setup lang="ts">
import { onBeforeUnmount, ref, shallowRef, toRaw } from "vue";
import { SessionClient, SessionClientError, type SessionView } from "@/modules/auth/api/sessionClient";

const props = defineProps<{ client?: SessionClient }>();
// Vue proxies cannot be used as `this` for a class with JS private fields.
const api = props.client ? toRaw(props.client) : new SessionClient();
const username = ref("");
const password = ref("");
const busy = ref(false);
const view = shallowRef<SessionView | null>(null);
const canSubmit = ref(false);
const message = ref("");
const error = ref("");
let mounted = true;
onBeforeUnmount(() => { mounted = false; password.value = ""; });

async function perform(action: () => Promise<unknown>, success: string) {
  if (busy.value) return;
  busy.value = true;
  view.value = null;
  canSubmit.value = false;
  message.value = "";
  error.value = "";
  try {
    // The client captures the request synchronously, before the form is cleared.
    const pending = action();
    password.value = "";
    await pending;
    if (mounted) {
      view.value = api.view;
      canSubmit.value = api.canSubmit;
      message.value = success;
    }
  } catch (failure) {
    if (mounted) error.value = failure instanceof SessionClientError
      ? failure.message : "暂时无法确认登录状态，请重新登录。";
  } finally {
    password.value = "";
    if (mounted) busy.value = false;
  }
}
function login() {
  return perform(() => api.login(username.value, password.value), "登录成功。");
}
function current() {
  return perform(() => api.current(), "已读取当前身份。提交操作前请重新登录。");
}
function renew() {
  return perform(() => api.renew(), "会话已续期。");
}
function logout() {
  return perform(() => api.logout(crypto.randomUUID()), "已退出当前会话。");
}
</script>

<template>
  <section class="auth-panel" aria-labelledby="login-title" :aria-busy="busy">
    <p class="section-kicker">账户与会话</p>
    <h1 id="login-title">登录项目实施辅助工具</h1>
    <p>请使用部署管理员提供的账户。密码和安全令牌不会保存到浏览器持久存储。</p>
    <form @submit.prevent="login">
      <label for="login-username">用户名</label>
      <input id="login-username" v-model="username" name="username" autocomplete="username" required :disabled="busy" />
      <label for="login-password">密码</label>
      <input id="login-password" v-model="password" name="password" type="password" autocomplete="current-password" required :disabled="busy" />
      <button type="submit" :disabled="busy || !username || !password">{{ busy ? '正在处理…' : '登录 / 重新登录' }}</button>
    </form>
    <p v-if="error" role="alert">{{ error }}</p>
    <p v-if="message" role="status">{{ message }}</p>
    <div class="auth-actions">
      <button type="button" :disabled="busy" @click="current">读取当前身份</button>
      <button type="button" :disabled="busy || !canSubmit" @click="renew">续期会话</button>
      <button type="button" :disabled="busy || !canSubmit" @click="logout">退出登录</button>
    </div>
    <p v-if="!canSubmit && !busy">刷新或离开此页面后，安全令牌不会保留。读取当前身份仅恢复只读显示；续期、退出和其他提交操作需重新登录。</p>
    <section v-if="view" aria-labelledby="identity-title" class="auth-identity">
      <h2 id="identity-title">当前身份</h2>
      <p>用户名：{{ view.user.username_display }}</p>
      <p v-if="view.password_change_required" role="status">此账户需要修改密码，目前只能使用受限会话。改密页面尚待接入，不能进入项目业务。</p>
      <template v-else>
        <p>部署角色：{{ view.deployment_role === 'DEPLOYMENT_ADMIN' ? '部署管理员' : '普通用户' }}</p>
        <p>授权项目：{{ view.authorized_projects.length }} 个</p>
        <ul v-if="view.authorized_projects.length">
          <li v-for="project in view.authorized_projects" :key="project.project_id">{{ project.name }}</li>
        </ul>
      </template>
      <p>会话空闲到期：<time :datetime="view.idle_expires_at">{{ new Date(view.idle_expires_at).toLocaleString('zh-CN') }}</time></p>
      <p>显示的身份与项目摘要仅供参考，所有操作仍由服务器实时检查权限。</p>
    </section>
  </section>
</template>

<style scoped>
.auth-panel { max-width: 42rem; margin: 1rem auto; padding: 1.5rem; background: #fff; border-radius: 1rem; }
form { display: grid; gap: .65rem; margin: 1.5rem 0; }
input { width: 100%; min-height: 2.75rem; padding: .6rem; border: 1px solid #64746b; border-radius: .4rem; font: inherit; }
input:focus-visible { outline: 3px solid #e09f3e; outline-offset: 2px; }
button:disabled { cursor: not-allowed; opacity: .55; }
.auth-actions { display: flex; gap: .6rem; flex-wrap: wrap; }
.auth-identity { margin-top: 1.5rem; padding-top: 1rem; border-top: 1px solid #d6ded7; }
[role="alert"] { color: #a21d25; }
p { line-height: 1.65; }
</style>
