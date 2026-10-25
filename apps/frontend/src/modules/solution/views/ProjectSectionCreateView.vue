<script setup lang="ts">
import { inject, onUnmounted, ref, toRaw, watch } from "vue";
import { RouterLink, useRoute, useRouter } from "vue-router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { sessionClientKey } from "@/modules/auth/api/sessionContext";
import { OutlineReadClient, type OutlineCurrent } from "@/modules/solution/api/outlineReadClient";
import { SectionCreateClient, SectionCreateError, normalizeSectionKey } from "@/modules/solution/api/sectionCreateClient";

const props = defineProps<{ session?: SessionClient; reader?: OutlineReadClient; creator?: SectionCreateClient }>();
const session = toRaw(props.session ?? inject(sessionClientKey, null) ?? new SessionClient());
const reader = toRaw(props.reader ?? new OutlineReadClient());
const creator = toRaw(props.creator ?? new SectionCreateClient(session));
const route = useRoute(); const router = useRouter();
const projectId = () => typeof route.params.projectId === "string" ? route.params.projectId : "";
const outlineId = () => typeof route.params.outlineId === "string" ? route.params.outlineId : "";
const linkProjectId = ref(projectId()); const linkOutlineId = ref(outlineId());
const parent = ref<OutlineCurrent | null>(null); const parentBusy = ref(false); const parentError = ref("");
const sectionKey = ref("");
const pending = ref<{ project: string; outline: string; actor: string; sectionKey: string; key: string } | null>(null);
const locked = ref(false); const confirmRetry = ref(false); const busy = ref(false); const error = ref("");
const createdId = ref("");
let generation = 0; let mounted = true;
function authorized() {
  return mounted && !!session.view && !session.view.password_change_required && session.canSubmit
    && session.view.authorized_projects.some(item => item.project_id === projectId()
      && (item.role === "PROJECT_MANAGER" || item.role === "IMPLEMENTATION_MEMBER"));
}
function canCreate() {
  return authorized() && parent.value?.project_id === projectId()
    && parent.value.solution_outline_id === outlineId() && parent.value.outline_state === "ACTIVE";
}
function storageKey() {
  return `plm.sol.section.create.pending.${session.view?.user.user_id ?? "none"}.${projectId()}.${outlineId()}`;
}
function restore() {
  pending.value = null; locked.value = false; confirmRetry.value = false; error.value = ""; createdId.value = "";
  sectionKey.value = "";
  if (!authorized()) return;
  try {
    const raw = window.sessionStorage.getItem(storageKey());
    if (!raw) return;
    const value: unknown = JSON.parse(raw);
    if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("invalid");
    const item = value as Record<string, unknown>;
    if (item.project !== projectId() || item.outline !== outlineId()
      || item.actor !== session.view?.user.user_id
      || typeof item.sectionKey !== "string" || item.sectionKey !== normalizeSectionKey(item.sectionKey)
      || typeof item.key !== "string" || !/^[\x20-\x7e]{16,128}$/.test(item.key)) throw new Error("invalid");
    pending.value = item as { project: string; outline: string; actor: string; sectionKey: string; key: string };
    sectionKey.value = item.sectionKey;
  } catch {
    locked.value = true;
    error.value = "原创建记录无法读取，已停止提交；请核对章节和审计记录。";
  }
}
async function loadParent() {
  if (!authorized() || parentBusy.value) return;
  const project = projectId(), outline = outlineId(), run = ++generation;
  parentBusy.value = true; parent.value = null; parentError.value = "";
  try {
    const result = await reader.current(project, outline);
    if (!mounted || run !== generation || project !== projectId() || outline !== outlineId()) return;
    if (result.project_id !== project || result.solution_outline_id !== outline) throw new Error("父目录身份不匹配。");
    parent.value = result;
  } catch (failure) {
    if (mounted && run === generation) parentError.value = failure instanceof Error
      ? failure.message : "暂时无法读取父目录。";
  } finally { if (mounted && run === generation) parentBusy.value = false; }
}
watch(() => [route.params.projectId, route.params.outlineId], () => {
  if (route.name !== "project-section-create") return;
  linkProjectId.value = projectId(); linkOutlineId.value = outlineId();
  generation += 1; parentBusy.value = false; parent.value = null; parentError.value = "";
  restore(); void loadParent();
}, { immediate: true });
onUnmounted(() => { mounted = false; generation += 1; });
async function submit() {
  if (!canCreate() || busy.value || locked.value || createdId.value || pending.value && !confirmRetry.value) return;
  const project = projectId(), outline = outlineId(), actor = session.view!.user.user_id;
  let attempt = pending.value;
  if (!attempt) {
    let normalized: string;
    try { normalized = normalizeSectionKey(sectionKey.value); }
    catch (failure) { error.value = failure instanceof Error ? failure.message : "章节键无效。"; return; }
    attempt = { project, outline, actor, sectionKey: normalized, key: crypto.randomUUID() };
    try { window.sessionStorage.setItem(storageKey(), JSON.stringify(attempt)); }
    catch { error.value = "无法保存原操作号，本次未提交。"; return; }
    pending.value = attempt; sectionKey.value = normalized;
  }
  if (attempt.project !== project || attempt.outline !== outline || attempt.actor !== actor) {
    locked.value = true; return;
  }
  confirmRetry.value = false; busy.value = true; error.value = "";
  try {
    const created = await creator.create(attempt.project, attempt.outline, attempt.sectionKey, attempt.key);
    if (!mounted || !canCreate() || project !== projectId() || outline !== outlineId()
      || actor !== session.view?.user.user_id) return;
    createdId.value = created.solution_section_id;
    try { window.sessionStorage.removeItem(storageKey()); }
    catch { locked.value = true; error.value = "章节已创建，但原操作号清理失败；请停止再次提交。"; return; }
    pending.value = null;
    try { await router.push({ name: "project-section-detail", params: { projectId: project,
      sectionId: created.solution_section_id } }); }
    catch { error.value = "章节已创建，但自动跳转失败。请使用下方详情链接。"; }
  } catch (failure) {
    if (!mounted) return;
    if (failure instanceof SectionCreateError && failure.code === "CONFLICT_IDEMPOTENCY") locked.value = true;
    error.value = failure instanceof Error ? failure.message : "创建结果无法确认，请保留原操作号。";
  } finally { if (mounted) busy.value = false; }
}
</script>

<template>
  <section class="section-create" aria-labelledby="section-create-title" :aria-busy="busy || parentBusy">
    <p class="section-kicker">项目方案</p><h1 id="section-create-title">创建方案章节</h1>
    <p>章节仅建立逻辑身份；不代表方案正文、评审或客户确认已经完成。</p>
    <p><RouterLink :to="{ name: 'project-outline-detail', params: { projectId: linkProjectId,
      outlineId: linkOutlineId } }">返回父目录</RouterLink></p>
    <p v-if="!authorized()" role="status">仅当前项目负责人或实施成员可创建；请确认会话与项目权限。</p>
    <template v-else>
      <p v-if="parentBusy" role="status">正在核对父目录…</p>
      <p v-if="parentError" role="alert">{{ parentError }}</p>
      <p v-if="parent && parent.outline_state !== 'ACTIVE'" role="status">父目录已归档，不可创建章节。</p>
      <template v-if="canCreate()">
        <p>父目录：{{ parent?.name }}</p>
        <p v-if="error" role="alert">{{ error }}</p>
        <p v-if="createdId"><RouterLink :to="{ name: 'project-section-detail', params: { projectId: route.params.projectId,
          sectionId: createdId } }">查看已创建章节详情</RouterLink></p>
        <form v-else @submit.prevent="submit">
          <label for="section-key">章节键</label>
          <input id="section-key" v-model="sectionKey" required maxlength="128" :disabled="busy || !!pending || locked" />
          <p v-if="pending" role="status">原操作号已保存在本浏览器会话。结果未确认时请勿新建操作；可核对后使用同一章节键和操作号重试。</p>
          <label v-if="pending && !locked"><input v-model="confirmRetry" type="checkbox" :disabled="busy" /> 我确认按原章节键和原操作号重试</label>
          <button type="submit" :disabled="busy || locked || !!(pending && !confirmRetry)">
            {{ busy ? "正在提交…" : pending ? "按原操作号重试" : "创建章节" }}
          </button>
        </form>
      </template>
    </template>
  </section>
</template>

<style scoped>
.section-create{max-width:44rem;margin:1rem auto;padding:1.5rem;background:#fff;border-radius:1rem}
.section-create form{display:grid;gap:.8rem}.section-create [role=alert]{color:#a21d25}
</style>
