<script setup lang="ts">
import { inject, onUnmounted, ref, toRaw, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { sessionClientKey } from "@/modules/auth/api/sessionContext";
import { ProjectDepartmentCreateClient, ProjectDepartmentCreateError,
  type ProjectDepartmentCreateFirstReceipt,
  type ProjectDepartmentCreateInput } from "@/modules/project/api/projectDepartmentCreateClient";

const props = defineProps<{ session?: SessionClient; creator?: ProjectDepartmentCreateClient }>();
const session = toRaw(props.session ?? inject(sessionClientKey, null) ?? new SessionClient());
const creator = toRaw(props.creator ?? new ProjectDepartmentCreateClient(session));
const route = useRoute();
const identity = session.view;
const initialProjectId = typeof route.params.projectId === "string" ? route.params.projectId : "";
const allowedAtEntry = !!identity && !identity.password_change_required && session.canSubmit
  && identity.authorized_projects.some((item) => item.project_id === initialProjectId && item.role === "PROJECT_MANAGER");
const code = ref("");
const name = ref("");
const confirmChoice = ref(false);
const confirmOriginal = ref(false);
const busy = ref(false);
const error = ref("");
const receipt = ref<ProjectDepartmentCreateFirstReceipt | null>(null);
const pending = ref<{ readonly projectId: string; readonly actorId: string;
  readonly input: ProjectDepartmentCreateInput; readonly key: string } | null>(null);
const recoveryBlocked = ref(false);
let mounted = true;
let generation = 0;

function stillAuthorized() {
  return mounted && allowedAtEntry && route.params.projectId === initialProjectId
    && session.canSubmit && session.view?.user.user_id === identity?.user.user_id
    && !!session.view?.authorized_projects.some((item) => item.project_id === initialProjectId
      && item.role === "PROJECT_MANAGER");
}
watch([code, name], () => { if (!pending.value) confirmChoice.value = false; });
watch(() => route.params.projectId, () => {
  generation += 1;
  receipt.value = null;
  busy.value = false;
  if (pending.value) recoveryBlocked.value = true;
});
onUnmounted(() => { mounted = false; generation += 1; pending.value = null; });

async function submit() {
  if (!stillAuthorized() || busy.value || recoveryBlocked.value || receipt.value) return;
  const recovery = pending.value;
  if (recovery && (!confirmOriginal.value || recovery.actorId !== session.view?.user.user_id)) return;
  if (!recovery && !confirmChoice.value) return;
  const attempt = recovery ?? Object.freeze({ projectId: initialProjectId,
    actorId: identity!.user.user_id, input: Object.freeze({ code: code.value, name: name.value }),
    key: crypto.randomUUID() });
  const current = ++generation;
  pending.value = attempt;
  confirmOriginal.value = false;
  busy.value = true; error.value = "";
  try {
    const result = await creator.create(attempt.projectId, attempt.input, attempt.key);
    if (!stillAuthorized() || current !== generation) return;
    receipt.value = result;
    pending.value = null;
  } catch (failure) {
    if (!mounted || current !== generation || route.params.projectId !== initialProjectId) return;
    if (failure instanceof ProjectDepartmentCreateError && failure.uncertain) {
      error.value = "创建结果无法确认。先核对部门历史和审计；如需恢复，明确确认后只复用原编码、名称和操作记录。";
    } else if (failure instanceof ProjectDepartmentCreateError && failure.code === "CONFLICT_IDEMPOTENCY") {
      recoveryBlocked.value = true;
      pending.value = null;
      error.value = "原操作记录与输入冲突，已停止本页创建，请核对部门历史和审计。";
    } else if (failure instanceof ProjectDepartmentCreateError) {
      pending.value = null;
      confirmChoice.value = false;
      error.value = failure.message;
    } else {
      error.value = "创建结果无法确认。请保留原操作记录，不要新建请求。";
    }
  } finally { if (mounted && current === generation) busy.value = false; }
}
</script>

<template>
  <section class="department-create" aria-labelledby="department-create-title" :aria-busy="busy">
    <p class="section-kicker">项目组织</p>
    <h1 id="department-create-title">创建项目部门</h1>
    <p>请核对部门编号和名称。服务器会再次检查当前项目负责人权限、项目状态与编号是否重复。</p>
    <p><RouterLink :to="{ name: 'project-departments', params: { projectId: initialProjectId } }">返回部门历史</RouterLink></p>
    <template v-if="!allowedAtEntry || !stillAuthorized()">
      <p role="status">需要当前项目负责人可提交的登录会话；会话或项目变化后请重新登录。</p>
      <RouterLink to="/login">前往账户与登录</RouterLink>
    </template>
    <template v-else>
      <p v-if="error" role="alert">{{ error }}</p>
      <template v-if="receipt">
        <p role="status">本次创建首次回执：{{ receipt.first_result.name }}（{{ receipt.first_result.code }}）· {{ receipt.first_result.etag }}。这不是当前状态证明。</p>
        <p>请返回部门历史重新读取，核对当前状态。</p>
      </template>
      <template v-else>
        <p v-if="pending" role="status">原操作仅保留在本页内存。离开或刷新后若仍不确定，先核对历史和审计，勿使用新操作记录重复创建。</p>
        <form @submit.prevent="submit">
          <label for="department-code">部门编号</label>
          <input id="department-code" v-model="code" required maxlength="64" autocomplete="off" :disabled="busy || !!pending" />
          <label for="department-name">部门名称</label>
          <input id="department-name" v-model="name" required maxlength="255" autocomplete="off" :disabled="busy || !!pending" />
          <label v-if="!pending"><input v-model="confirmChoice" type="checkbox" :disabled="busy" />我已核对部门编号、名称和当前项目</label>
          <label v-if="pending && !recoveryBlocked"><input v-model="confirmOriginal" name="confirm_original_department" type="checkbox" :disabled="busy" />我确认只复用原编号、名称和原操作记录恢复</label>
          <button type="submit" :disabled="busy || recoveryBlocked || !!(pending && !confirmOriginal) || (!pending && !confirmChoice)">
            {{ busy ? '正在提交…' : pending ? '按原操作记录恢复' : '创建部门' }}
          </button>
        </form>
      </template>
    </template>
  </section>
</template>

<style scoped>
.department-create { max-width: 44rem; margin: 1rem auto; padding: 1.5rem; background: #fff; border-radius: 1rem; }
.department-create form { display: grid; gap: .7rem; margin-top: 1rem; }
.department-create input:not([type="checkbox"]) { width: 100%; padding: .55rem; }
.department-create p { line-height: 1.65; }
.department-create [role="alert"] { color: #a21d25; }
.department-create button:disabled { opacity: .55; cursor: not-allowed; }
</style>
