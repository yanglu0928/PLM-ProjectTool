<script setup lang="ts">
import { inject, onUnmounted, ref, toRaw, watch } from "vue";
import { RouterLink, useRoute, useRouter } from "vue-router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { sessionClientKey } from "@/modules/auth/api/sessionContext";
import { PlanCreateClient, PlanCreateError, normalizePlanName } from "@/modules/plan/api/planCreateClient";

const props = defineProps<{ session?: SessionClient; creator?: PlanCreateClient }>();
const session = toRaw(props.session ?? inject(sessionClientKey, null) ?? new SessionClient());
const creator = toRaw(props.creator ?? new PlanCreateClient(session));
const route = useRoute(); const router = useRouter();
const projectId = () => typeof route.params.projectId === "string" ? route.params.projectId : "";
const name = ref("");
const pending = ref<{ project: string; actor: string; name: string; key: string } | null>(null);
const locked = ref(false); const confirmRetry = ref(false); const busy = ref(false); const error = ref("");
const createdId = ref("");
let mounted = true; let generation = 0;
function authorized() {
  return mounted && !!session.view && !session.view.password_change_required && session.canSubmit
    && session.view.authorized_projects.some(item => item.project_id === projectId()
      && (item.role === "PROJECT_MANAGER" || item.role === "IMPLEMENTATION_MEMBER"));
}
function storageKey() { return `plm.plan.create.pending.${session.view?.user.user_id ?? "none"}.${projectId()}`; }
function restore() {
  generation += 1;
  pending.value = null; locked.value = false; confirmRetry.value = false;
  busy.value = false; error.value = ""; createdId.value = ""; name.value = "";
  try {
    const raw = window.sessionStorage.getItem(storageKey());
    if (!raw) return;
    const value: unknown = JSON.parse(raw);
    if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("invalid");
    const item = value as Record<string, unknown>;
    if (Object.keys(item).length !== 4 || !["project", "actor", "name", "key"].every(
      field => Object.hasOwn(item, field))
      || item.project !== projectId() || item.actor !== session.view?.user.user_id
      || typeof item.name !== "string" || item.name !== normalizePlanName(item.name)
      || typeof item.key !== "string" || !/^[\x20-\x7e]{16,128}$/.test(item.key)) throw new Error("invalid");
    pending.value = item as { project: string; actor: string; name: string; key: string };
    name.value = item.name;
  } catch {
    locked.value = true;
    error.value = "原创建记录无法读取，已停止提交；请核对计划和审计记录。";
  }
}
watch(() => route.params.projectId, restore, { immediate: true });
onUnmounted(() => { mounted = false; generation += 1; });
async function submit() {
  if (!authorized() || busy.value || locked.value || createdId.value
    || pending.value && !confirmRetry.value) return;
  const project = projectId(), actor = session.view!.user.user_id, run = generation;
  let attempt = pending.value;
  if (!attempt) {
    let normalized: string;
    try { normalized = normalizePlanName(name.value); }
    catch (failure) { error.value = failure instanceof Error ? failure.message : "计划名称无效。"; return; }
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
    if (!mounted || run !== generation || !authorized() || project !== projectId()
      || actor !== session.view?.user.user_id) return;
    createdId.value = created.plan_id;
    try { window.sessionStorage.removeItem(storageKey()); }
    catch { locked.value = true; error.value = "计划已创建，但原操作号清理失败；请停止再次提交。"; return; }
    pending.value = null;
    try { await router.push({ name: "project-plan-detail", params: { projectId: project,
      planId: created.plan_id } }); }
    catch { error.value = "计划已创建，但自动跳转失败。请使用下方详情链接。"; }
  } catch (failure) {
    if (!mounted || run !== generation || project !== projectId()
      || actor !== session.view?.user.user_id) return;
    if (failure instanceof PlanCreateError && failure.code === "CONFLICT_IDEMPOTENCY") locked.value = true;
    error.value = failure instanceof Error ? failure.message : "创建结果无法确认，请保留原操作号。";
  } finally { if (mounted && run === generation) busy.value = false; }
}
</script>

<template>
  <section class="plan-create" aria-labelledby="plan-create-title" :aria-busy="busy">
    <p class="section-kicker">项目实施</p><h1 id="plan-create-title">创建实施计划</h1>
    <p class="warning">本操作仅建立计划身份，不生成计划版本、WBS 任务、评审结论或交付文件。</p>
    <p><RouterLink :to="{ name: 'project-plans', params: { projectId: route.params.projectId } }">返回实施计划</RouterLink></p>
    <p v-if="!authorized()" role="status">仅当前项目负责人或实施成员可创建；请确认会话与项目权限。</p>
    <template v-else>
      <p v-if="error" role="alert">{{ error }}</p>
      <p v-if="createdId"><RouterLink :to="{ name: 'project-plan-detail', params: { projectId: route.params.projectId,
        planId: createdId } }">查看已创建计划详情</RouterLink></p>
      <form v-else @submit.prevent="submit">
        <label for="plan-name">计划名称</label>
        <input id="plan-name" v-model="name" required maxlength="500" :disabled="busy || !!pending || locked" />
        <p v-if="pending" role="status">原操作号已保存在本浏览器会话。结果未确认时请先核对，再使用同一名称和操作号重试。</p>
        <label v-if="pending && !locked"><input v-model="confirmRetry" type="checkbox" :disabled="busy" /> 我确认按原名称和原操作号重试</label>
        <button type="submit" :disabled="busy || locked || !!(pending && !confirmRetry)">
          {{ busy ? "正在提交…" : pending ? "按原操作号重试" : "创建计划" }}
        </button>
      </form>
    </template>
  </section>
</template>

<style scoped>
.plan-create{max-width:44rem;margin:1rem auto;padding:1.5rem;background:#fff;border-radius:1rem}
.plan-create form{display:grid;gap:.8rem}.plan-create [role=alert]{color:#a21d25}
.warning{padding:.8rem 1rem;border-left:.3rem solid #d29b42;background:#fff8e9}
</style>
