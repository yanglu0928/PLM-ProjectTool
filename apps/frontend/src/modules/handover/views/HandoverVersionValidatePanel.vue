<script setup lang="ts">
import { inject, onMounted, onUnmounted, ref, shallowRef, toRaw } from "vue";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { sessionClientKey } from "@/modules/auth/api/sessionContext";
import type { HandoverAnalysisVersionView } from "@/modules/handover/api/handoverReadClient";
import { HandoverVersionValidateClient, HandoverVersionValidateError,
  type HandoverValidationIssue, type HandoverVersionValidationReport } from "@/modules/handover/api/handoverVersionValidateClient";

const props = defineProps<{ version: HandoverAnalysisVersionView; session?: SessionClient;
  validator?: HandoverVersionValidateClient }>();
const session = toRaw(props.session ?? inject(sessionClientKey, null) ?? new SessionClient());
const validator = toRaw(props.validator ?? new HandoverVersionValidateClient(session));
const actorId = session.view?.user.user_id;
type Pending = { readonly actor: string; readonly project: string; readonly analysis: string;
  readonly version: string; readonly key: string };
const pending = shallowRef<Pending | null>(null); const retryConfirmed = ref(false);
const report = shallowRef<HandoverVersionValidationReport | null>(null);
const busy = ref(false); const locked = ref(false); const error = ref("");
let mounted = true;
const labels: Record<HandoverValidationIssue, string> = {
  CONTENT_FINGERPRINT_MISMATCH: "固定版本内容指纹不一致，请停止送审并联系项目管理员。",
  SOURCE_UNAVAILABLE: "原固定文档已不可用或不再匹配。",
  EVIDENCE_UNAVAILABLE: "问题所引证据资格或同源关系不可用。",
  CAPABILITY_UNAVAILABLE: "所引标准能力不再是当前已批准版本或条目不可用。",
  AI_PROVENANCE_UNAVAILABLE: "所引 AI 任务来源状态不可用。",
  INPUT_GUIDANCE_INCOMPLETE: "待确认问题的人工填写提示或问题字段不完整。",
  ACTION_ITEM_REQUIRED: "资料缺失问题须由实施待办承接，不能直接送审。",
};
function canValidate(): boolean { const current = session.view;
  return mounted && !!actorId && current?.user.user_id === actorId
    && !current.password_change_required && props.version.state === "DRAFT"
    && current.authorized_projects.some(project => project.project_id === props.version.project_id
      && (project.role === "PROJECT_MANAGER" || project.role === "IMPLEMENTATION_MEMBER"));
}
function storageKey(): string { const value = props.version;
  return `plm.hnd.version.validate.pending.${actorId ?? "none"}.${value.project_id}.${value.handover_analysis_id}.${value.handover_analysis_version_id}`;
}
function restore(): void {
  if (!actorId) return;
  try {
    const raw = sessionStorage.getItem(storageKey()); if (!raw) return;
    const value: unknown = JSON.parse(raw);
    if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("invalid");
    const data = value as Record<string, unknown>, version = props.version;
    if (Object.keys(data).length !== 5 || data.actor !== actorId || data.project !== version.project_id
      || data.analysis !== version.handover_analysis_id || data.version !== version.handover_analysis_version_id
      || typeof data.key !== "string" || !/^[\x20-\x7e]{16,128}$/.test(data.key)) throw new Error("invalid");
    pending.value = data as Pending;
  } catch { locked.value = true; error.value = "原校验记录无法安全读取；请核对审计，勿换号重试。"; }
}
function clearPending(attempt: Pending): boolean {
  try {
    if (sessionStorage.getItem(storageKey()) !== JSON.stringify(attempt)) throw new Error("changed");
    sessionStorage.removeItem(storageKey()); pending.value = null; return true;
  } catch { locked.value = true; error.value = "无法清除原操作记录；请保留操作号并核对审计。"; return false; }
}
async function validate(): Promise<void> {
  if (!canValidate() || !session.canSubmit || busy.value || locked.value || report.value
    || pending.value && !retryConfirmed.value) return;
  let attempt = pending.value;
  if (!attempt) {
    const version = props.version;
    attempt = { actor: actorId!, project: version.project_id, analysis: version.handover_analysis_id,
      version: version.handover_analysis_version_id, key: `handover-version-validation-${crypto.randomUUID()}` };
    try {
      const encoded = JSON.stringify(attempt); sessionStorage.setItem(storageKey(), encoded);
      if (sessionStorage.getItem(storageKey()) !== encoded) throw new Error("write");
      pending.value = attempt;
    } catch { error.value = "无法安全保存原校验操作号，请检查浏览器会话存储。"; return; }
  }
  if (attempt.actor !== actorId || attempt.project !== props.version.project_id
    || attempt.analysis !== props.version.handover_analysis_id
    || attempt.version !== props.version.handover_analysis_version_id) { locked.value = true; return; }
  busy.value = true; retryConfirmed.value = false; error.value = "";
  try {
    const result = await validator.validate(props.version, attempt.key);
    if (!mounted || !canValidate()) return;
    if (!clearPending(attempt)) return;
    report.value = result;
  } catch (failure) {
    if (!mounted) return;
    if (failure instanceof HandoverVersionValidateError && failure.code === "CONFLICT_IDEMPOTENCY") locked.value = true;
    if (failure instanceof HandoverVersionValidateError && !failure.uncertain
      && failure.code !== "CONFLICT_IDEMPOTENCY") clearPending(attempt);
    error.value = failure instanceof Error ? failure.message : "校验结果无法确认；请保留原操作号。";
  } finally { if (mounted) busy.value = false; }
}
const unsubscribe = session.subscribe(() => {
  report.value = null; retryConfirmed.value = false;
  if (busy.value || pending.value) error.value = "会话已变化；请核对原校验结果，勿换号重试。";
});
onMounted(restore);
onUnmounted(() => { mounted = false; unsubscribe(); });
</script>

<template>
  <section v-if="canValidate()" aria-label="交接版本当前来源校验" :aria-busy="busy">
    <h3>当前来源与问题完整性校验</h3>
    <p>只生成本次校验报告，不修改 DRAFT；通过也不是客户确认、送审或评审批准。来源之后变化须重新校验。</p>
    <p v-if="!session.canSubmit && !busy" role="status">当前会话仅可查看；请重新登录后再校验。</p>
    <p v-if="error" role="alert">{{ error }}</p>
    <template v-if="report">
      <p role="status">{{ report.valid ? '本次校验通过；仍须独立送审与人工批准。' : '本次校验未通过，请先处理阻断项。' }}</p>
      <p>问题 {{ report.item_count }}，固定文档 {{ report.source_count }}，证据引用 {{ report.evidence_count }}，
        标准能力引用 {{ report.capability_ref_count }}，AI 任务引用 {{ report.ai_task_count }}。</p>
      <ul v-if="report.blocking_issues.length"><li v-for="issue in report.blocking_issues" :key="issue">{{ labels[issue] }}</li></ul>
      <p>校验时间：{{ report.checked_at }}；审计事件：{{ report.audit_event_id }}</p>
    </template>
    <template v-else>
      <p v-if="pending" role="status">原校验操作号已保留；请先核对审计，再决定是否同号重试。</p>
      <label v-if="pending"><input v-model="retryConfirmed" type="checkbox" :disabled="busy || locked" />我已核对历史，沿用原操作号重试</label>
      <button type="button" :disabled="busy || locked || !session.canSubmit || !!pending && !retryConfirmed"
        @click="validate">{{ pending ? '按原操作号重试校验' : '运行当前来源校验' }}</button>
    </template>
  </section>
</template>
