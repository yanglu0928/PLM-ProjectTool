<script setup lang="ts">
import { inject, onUnmounted, ref, toRaw, watch } from "vue";
import { RouterLink } from "vue-router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { sessionClientKey } from "@/modules/auth/api/sessionContext";
import { OutputRequestCreateClient, OutputRequestCreateError,
  type OutputRequestCreateReceipt } from "@/modules/output/api/outputRequestCreateClient";
import type { RequirementVersionView } from "@/modules/requirement/api/requirementReadClient";

const props = defineProps<{ projectId: string; version: RequirementVersionView; approvedVersionRef: string | null;
  session?: SessionClient; creator?: OutputRequestCreateClient }>();
const session = toRaw(props.session ?? inject(sessionClientKey, null) ?? new SessionClient());
const creator = toRaw(props.creator ?? new OutputRequestCreateClient(session));
const busy = ref(false); const receipt = ref<OutputRequestCreateReceipt | null>(null);
const error = ref(""); const uncertain = ref(false); const idempotencyKey = ref<string | null>(null);
let mounted = true; let generation = 0;
watch(() => [props.projectId, props.version.requirement_version_id, props.approvedVersionRef], () => {
  generation += 1; busy.value = false; receipt.value = null; error.value = ""; uncertain.value = false; idempotencyKey.value = null;
});
onUnmounted(() => { mounted = false; generation += 1; });
function canRender() {
  const view = session.view;
  return mounted && props.version.project_id === props.projectId
    && props.version.state === "APPROVED"
    && props.approvedVersionRef === props.version.requirement_version_id
    && !!view && !view.password_change_required
    && view.authorized_projects.some(item => item.project_id === props.projectId
      && (item.role === "PROJECT_MANAGER" || item.role === "IMPLEMENTATION_MEMBER"));
}
function canCreate() { return canRender() && session.canSubmit; }
async function requestDocx() {
  if (!canCreate() || busy.value || receipt.value || uncertain.value) return;
  const current = ++generation; const project = props.projectId; const versionId = props.version.requirement_version_id;
  busy.value = true; error.value = "";
  try {
    idempotencyKey.value ??= globalThis.crypto.randomUUID();
    const result = await creator.create(project, versionId, idempotencyKey.value);
    if (!mounted || current !== generation || project !== props.projectId
      || versionId !== props.version.requirement_version_id) return;
    receipt.value = result;
  } catch (failure) {
    if (!mounted || current !== generation) return;
    if (failure instanceof OutputRequestCreateError) {
      error.value = failure.message; uncertain.value = failure.uncertain;
    } else { error.value = "输出请求暂时无法确认，请先查看输出请求历史。"; uncertain.value = true; }
  } finally { if (mounted && current === generation) busy.value = false; }
}
</script>

<template>
  <section v-if="canRender()" class="output-create" aria-labelledby="output-create-title">
    <h3 id="output-create-title">生成需求说明文档</h3>
    <p>只针对当前已批准固定版本发起 DOCX 请求。请求受理不代表文件已生成。</p>
    <button v-if="!receipt && !uncertain" type="button" :disabled="busy || !session.canSubmit" @click="requestDocx">
      {{ busy ? "正在提交…" : "请求生成 DOCX" }}
    </button>
    <p v-if="error" role="alert">{{ error }}</p>
    <RouterLink v-if="error" :to="{ name: 'project-output-requests', params: { projectId: props.projectId } }">查看输出请求历史</RouterLink>
    <div v-if="receipt" role="status">
      <p>请求已受理，当前状态：{{ receipt.state }}。文件是否生成请继续查看历史。</p>
      <p>请求编号：<span class="request-id">{{ receipt.output_request_id }}</span></p>
      <RouterLink :to="{ name: 'project-output-requests', params: { projectId: props.projectId } }">查看输出请求历史</RouterLink>
    </div>
  </section>
</template>

<style scoped>
.output-create{margin:1rem 0;padding:1rem;border:1px solid #d8dee7;border-radius:.75rem;background:#f8fafc}
.request-id{font-family:ui-monospace,monospace;overflow-wrap:anywhere}
</style>
