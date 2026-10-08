<script setup lang="ts">
import { inject, onUnmounted, ref, toRaw, watch } from "vue";
import { RouterLink, useRoute, useRouter } from "vue-router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { sessionClientKey } from "@/modules/auth/api/sessionContext";
import { OutlineCreateClient, OutlineCreateError, normalizeOutlineName } from "@/modules/solution/api/outlineCreateClient";

const props = defineProps<{ session?: SessionClient; creator?: OutlineCreateClient }>();
const session = toRaw(props.session ?? inject(sessionClientKey, null) ?? new SessionClient());
const creator = toRaw(props.creator ?? new OutlineCreateClient(session));
const route = useRoute(); const router = useRouter();
const projectId = () => typeof route.params.projectId === "string" ? route.params.projectId : "";
const name = ref(""); const pending = ref<{ project: string; actor: string; name: string; key: string } | null>(null);
const locked = ref(false); const confirmRetry = ref(false); const busy = ref(false); const error = ref("");
const createdId = ref("");
let mounted = true;
function authorized() {
  return mounted && !!session.view && !session.view.password_change_required && session.canSubmit
    && session.view.authorized_projects.some(item => item.project_id === projectId()
      && (item.role === "PROJECT_MANAGER" || item.role === "IMPLEMENTATION_MEMBER"));
}
function storageKey() { return `plm.sol.outline.create.pending.${session.view?.user.user_id ?? "none"}.${projectId()}`; }
function restore() {
  pending.value = null; locked.value = false; confirmRetry.value = false; error.value = ""; createdId.value = "";
  try {
    const raw = window.sessionStorage.getItem(storageKey());
    if (!raw) return;
    const value: unknown = JSON.parse(raw);
    if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("invalid");
    const item = value as Record<string, unknown>;
    if (item.project !== projectId() || item.actor !== session.view?.user.user_id
      || typeof item.name !== "string" || item.name !== normalizeOutlineName(item.name)
      || typeof item.key !== "string" || !/^[\x20-\x7e]{16,128}$/.test(item.key)) throw new Error("invalid");
    pending.value = item as { project: string; actor: string; name: string; key: string };
    name.value = item.name;
  } catch {
    locked.value = true;
    error.value = "原创建记录无法读取，已停止提交；请核对目录和审计记录。";
  }
}
watch(() => route.params.projectId, restore, { immediate: true });
onUnmounted(() => { mounted = false; });
async function submit() {
  if (!authorized() || busy.value || locked.value || createdId.value || pending.value && !confirmRetry.value) return;
  const project = projectId(), actor = session.view!.user.user_id;
  let attempt = pending.value;
  if (!attempt) {
    let normalized: string;
    try { normalized = normalizeOutlineName(name.value); }
    catch (failure) { error.value = failure instanceof Error ? failure.message : "目录名称无效。"; return; }
    attempt = { project, actor, name: normalized, key: crypto.randomUUID() };
    try { window.sessionStorage.setItem(storageKey(), JSON.stringify(attempt)); }
    catch { error.value = "无法保存原操作号，本次未提交。"; return; }
    pending.value = attempt;
    name.value = normalized;
  }
  if (attempt.project !== project || attempt.actor !== actor) { locked.value = true; return; }
  confirmRetry.value = false; busy.value = true; error.value = "";
  try {
    const created = await creator.create(attempt.project, attempt.name, attempt.key);
    if (!mounted || !authorized() || project !== projectId() || actor !== session.view?.user.user_id) return;
    createdId.value = created.solution_outline_id;
    try { window.sessionStorage.removeItem(storageKey()); }
    catch { locked.value = true; error.value = "目录已创建，但原操作号清理失败；请停止再次提交。"; return; }
    pending.value = null;
    try { await router.push({ name: "project-outline-detail", params: { projectId: project,
      outlineId: created.solution_outline_id } }); }
    catch { error.value = "目录已创建，但自动跳转失败。请使用下方详情链接。"; }
  } catch (failure) {
    if (!mounted) return;
    if (failure instanceof OutlineCreateError && failure.code === "CONFLICT_IDEMPOTENCY") locked.value = true;
    error.value = failure instanceof Error ? failure.message : "创建结果无法确认，请保留原操作号。";
  } finally { if (mounted) busy.value = false; }
}
</script>

<template>
  <section class="outline-create" aria-labelledby="outline-create-title" :aria-busy="busy">
    <p class="section-kicker">项目方案</p><h1 id="outline-create-title">创建方案目录</h1>
    <p>目录仅建立逻辑身份；不代表方案正文、评审或客户确认已经完成。</p>
    <p><RouterLink :to="{ name: 'project-outlines', params: { projectId: route.params.projectId } }">返回方案目录</RouterLink></p>
    <p v-if="!authorized()" role="status">仅当前项目负责人或实施成员可创建；请确认会话与项目权限。</p>
    <template v-else>
      <p v-if="error" role="alert">{{ error }}</p>
      <p v-if="createdId"><RouterLink :to="{ name: 'project-outline-detail', params: { projectId: route.params.projectId,
        outlineId: createdId } }">查看已创建目录详情</RouterLink></p>
      <form v-else @submit.prevent="submit">
        <label for="outline-name">目录名称</label>
        <input id="outline-name" v-model="name" required maxlength="500" :disabled="busy || !!pending || locked" />
        <p v-if="pending" role="status">原操作号已保存在本浏览器会话。结果未确认时请勿新建操作；可核对后使用同一名称和操作号重试。</p>
        <label v-if="pending && !locked"><input v-model="confirmRetry" type="checkbox" :disabled="busy" /> 我确认按原名称和原操作号重试</label>
        <button type="submit" :disabled="busy || locked || !!(pending && !confirmRetry)">
          {{ busy ? "正在提交…" : pending ? "按原操作号重试" : "创建目录" }}
        </button>
      </form>
    </template>
  </section>
</template>

<style scoped>
.outline-create{max-width:44rem;margin:1rem auto;padding:1.5rem;background:#fff;border-radius:1rem}
.outline-create form{display:grid;gap:.8rem}.outline-create [role=alert]{color:#a21d25}
</style>
