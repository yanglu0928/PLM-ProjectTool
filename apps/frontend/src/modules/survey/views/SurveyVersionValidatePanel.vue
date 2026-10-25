<script setup lang="ts">
import { inject, onUnmounted, ref, shallowRef, toRaw } from "vue";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { sessionClientKey } from "@/modules/auth/api/sessionContext";
import type { SurveyVersionView } from "@/modules/survey/api/surveyReadClient";
import { SurveyVersionValidateClient, SurveyVersionValidateError, type SurveyValidationIssue,
  type SurveyVersionValidationReport } from "@/modules/survey/api/surveyVersionValidateClient";

const props = defineProps<{ version: SurveyVersionView; session?: SessionClient; validator?: SurveyVersionValidateClient }>();
const session = toRaw(props.session ?? inject(sessionClientKey, null) ?? new SessionClient());
const validator = toRaw(props.validator ?? new SurveyVersionValidateClient(session));
const actor = session.view?.user.user_id;
type Pending = { actor: string; project: string; survey: string; version: string; key: string };
const pending = shallowRef<Pending | null>(null); const report = shallowRef<SurveyVersionValidationReport | null>(null);
const retry = ref(false); const busy = ref(false); const locked = ref(false); const error = ref("");
let mounted = true;
const labels: Record<SurveyValidationIssue, string> = {
  CONTENT_FINGERPRINT_MISMATCH: "固定版本内容指纹不一致。", COUNT_MISMATCH: "固定版本声明的项目数量与内容不一致。",
  QUESTION_RULE_INVALID: "问题、回答规则或选项不完整。", CONDITION_RULE_INVALID: "问题显示条件格式无效。",
  CONDITION_REFERENCE_INVALID: "显示条件引用的问题不可用。", CONDITION_CYCLE: "问题显示条件存在循环。",
  SOURCE_UNAVAILABLE: "固定来源不可用或不再满足当前资格。", TARGET_DEPARTMENT_UNAVAILABLE: "目标部门不可用。",
};
function canValidate(): boolean { const view = session.view; return mounted && !!actor && view?.user.user_id === actor
  && !view.password_change_required && props.version.state === "DRAFT" && view.authorized_projects.some(p =>
    p.project_id === props.version.project_id && (p.role === "PROJECT_MANAGER" || p.role === "IMPLEMENTATION_MEMBER")); }
function storageKey() { const v = props.version; return `plm.survey.version.validate.pending.${actor ?? "none"}.${v.project_id}.${v.survey_id}.${v.survey_version_id}`; }
function restore() { if (!actor) return; try { const raw = sessionStorage.getItem(storageKey()); if (!raw) return;
  const value: unknown = JSON.parse(raw); if (!value || typeof value !== "object" || Array.isArray(value)) throw Error();
  const d = value as Record<string, unknown>, v = props.version;
  if (Object.keys(d).length !== 5 || d.actor !== actor || d.project !== v.project_id || d.survey !== v.survey_id
    || d.version !== v.survey_version_id || typeof d.key !== "string" || !/^[\x20-\x7e]{16,128}$/.test(d.key)) throw Error();
  pending.value = d as Pending;
} catch { locked.value = true; error.value = "原校验操作号无法安全读取；请核对审计，勿换号重试。"; } }
function clearPending(attempt: Pending) { try { if (sessionStorage.getItem(storageKey()) !== JSON.stringify(attempt)) throw Error();
  sessionStorage.removeItem(storageKey()); pending.value = null; return true;
} catch { locked.value = true; error.value = "无法清除原操作号；请核对审计。"; return false; } }
async function validate() { if (!canValidate() || !session.canSubmit || busy.value || locked.value || report.value
    || pending.value && !retry.value) return;
  let attempt = pending.value; if (!attempt) { const v = props.version; attempt = { actor: actor!, project: v.project_id,
    survey: v.survey_id, version: v.survey_version_id, key: `survey-version-validation-${crypto.randomUUID()}` };
    try { const raw = JSON.stringify(attempt); sessionStorage.setItem(storageKey(), raw);
      if (sessionStorage.getItem(storageKey()) !== raw) throw Error(); pending.value = attempt;
    } catch { error.value = "无法安全保存原校验操作号，请检查浏览器会话存储。"; return; } }
  if (attempt.actor !== actor || attempt.project !== props.version.project_id || attempt.survey !== props.version.survey_id
    || attempt.version !== props.version.survey_version_id) { locked.value = true; return; }
  busy.value = true; retry.value = false; error.value = "";
  try { const result = await validator.validate(props.version, attempt.key); if (!mounted || !canValidate()) return;
    if (!clearPending(attempt)) return; report.value = result;
  } catch (failure) { if (!mounted) return;
    if (failure instanceof SurveyVersionValidateError && failure.code === "CONFLICT_IDEMPOTENCY") locked.value = true;
    if (failure instanceof SurveyVersionValidateError && !failure.uncertain && failure.code !== "CONFLICT_IDEMPOTENCY") clearPending(attempt);
    error.value = failure instanceof Error ? failure.message : "校验结果无法确认；请保留原操作号。";
  } finally { if (mounted) busy.value = false; }
}
const unsubscribe = session.subscribe(() => { report.value = null; retry.value = false;
  if (busy.value || pending.value) error.value = "会话已变化；请核对原校验结果，勿换号重试。"; });
if (typeof window !== "undefined") restore();
onUnmounted(() => { mounted = false; unsubscribe(); });
</script>

<template><section v-if="canValidate()" aria-label="调研版本当前完整性校验" :aria-busy="busy">
  <h3>当前来源与问题完整性校验</h3>
  <p>只生成当前校验报告，不修改草稿状态；通过也不代表送审、评审批准或客户确认。</p>
  <p v-if="error" role="alert">{{ error }}</p>
  <template v-if="report"><p role="status">{{ report.valid ? "本次校验通过；仍须独立送审与人工批准。" : "本次校验未通过，请先处理阻断项。" }}</p>
    <p>问题 {{ report.question_count }}，选项 {{ report.option_count }}，来源 {{ report.source_count }}，目标部门 {{ report.target_department_count }}，条件问题 {{ report.conditional_question_count }}。</p>
    <ul v-if="report.blocking_issues.length"><li v-for="issue in report.blocking_issues" :key="issue">{{ labels[issue] }}</li></ul>
    <p>校验时间：{{ report.checked_at }}；审计事件：{{ report.audit_event_id }}</p></template>
  <template v-else><p v-if="pending" role="status">原校验操作号已保留；请核对审计后，同号重试。</p>
    <label v-if="pending"><input v-model="retry" type="checkbox" :disabled="busy || locked" />我已核对历史，沿用原操作号重试</label>
    <button type="button" :disabled="busy || locked || !session.canSubmit || !!pending && !retry" @click="validate">
      {{ busy ? "正在校验…" : pending ? "按原操作号重试校验" : "运行当前来源校验" }}</button>
  </template>
</section></template>
