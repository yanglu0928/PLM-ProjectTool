<script setup lang="ts">
import { inject, onMounted, onUnmounted, ref, shallowRef, toRaw } from "vue";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { sessionClientKey } from "@/modules/auth/api/sessionContext";
import type { CapabilityVersion } from "@/modules/capability/api/capabilityReadClient";
import { CapabilityVersionValidateClient, CapabilityValidateError,
  type CapabilityValidationReport } from "@/modules/capability/api/capabilityVersionValidateClient";

const props = defineProps<{ version: CapabilityVersion; session?: SessionClient;
  validator?: CapabilityVersionValidateClient }>();
const session = toRaw(props.session ?? inject(sessionClientKey, null) ?? new SessionClient());
const validator = toRaw(props.validator ?? new CapabilityVersionValidateClient(session));
const actorId = session.view?.user.user_id;
type Pending = { readonly actor: string; readonly baselineId: string;
  readonly versionId: string; readonly key: string };
const pending = shallowRef<Pending | null>(null); const retryConfirmed = ref(false);
const report = shallowRef<CapabilityValidationReport | null>(null);
const busy = ref(false); const locked = ref(false); const error = ref("");
let mounted = true;
function canValidate(): boolean {
  const current = session.view;
  return mounted && !!actorId && current?.user.user_id === actorId
    && current.deployment_role === "DEPLOYMENT_ADMIN"
    && !current.password_change_required && session.canSubmit && props.version.state === "DRAFT";
}
function storageKey(): string {
  return `plm.cap.version.validate.pending.${actorId ?? "none"}.${props.version.baseline_version_id}`;
}
function restore(): void {
  if (!actorId) return;
  try {
    const raw = window.sessionStorage.getItem(storageKey()); if (!raw) return;
    const value: unknown = JSON.parse(raw);
    if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("invalid");
    const data = value as Record<string, unknown>;
    if (Object.keys(data).length !== 4 || data.actor !== actorId
      || data.baselineId !== props.version.baseline_id
      || data.versionId !== props.version.baseline_version_id
      || typeof data.key !== "string" || !/^[\x20-\x7e]{16,128}$/.test(data.key)) {
      throw new Error("invalid");
    }
    pending.value = { actor: actorId, baselineId: props.version.baseline_id,
      versionId: props.version.baseline_version_id, key: data.key };
  } catch { locked.value = true; error.value = "原校验记录无法安全读取；请核对审计，勿换号重试。"; }
}
function clearPending(attempt: Pending): boolean {
  try {
    if (window.sessionStorage.getItem(storageKey()) !== JSON.stringify(attempt)) throw new Error("changed");
    window.sessionStorage.removeItem(storageKey()); pending.value = null; return true;
  } catch { locked.value = true; error.value = "无法清除原操作记录；请保留操作号并核对审计。"; return false; }
}
async function validate(): Promise<void> {
  if (!canValidate() || busy.value || locked.value || report.value
    || pending.value && !retryConfirmed.value) return;
  let attempt = pending.value;
  if (!attempt) {
    attempt = { actor: actorId!, baselineId: props.version.baseline_id,
      versionId: props.version.baseline_version_id,
      key: `capability-version-validation-${crypto.randomUUID()}` };
    try {
      const encoded = JSON.stringify(attempt); window.sessionStorage.setItem(storageKey(), encoded);
      if (window.sessionStorage.getItem(storageKey()) !== encoded) throw new Error("write");
      pending.value = attempt;
    } catch { error.value = "无法安全保存原校验操作号，请检查浏览器会话存储。"; return; }
  }
  if (attempt.actor !== actorId || attempt.baselineId !== props.version.baseline_id
    || attempt.versionId !== props.version.baseline_version_id) { locked.value = true; return; }
  busy.value = true; retryConfirmed.value = false; error.value = "";
  try {
    const result = await validator.validate(props.version, attempt.key);
    if (!mounted || !canValidate()) return;
    if (!clearPending(attempt)) return;
    report.value = result;
  } catch (failure) {
    if (!mounted) return;
    if (failure instanceof CapabilityValidateError && failure.code === "CONFLICT_IDEMPOTENCY") locked.value = true;
    if (failure instanceof CapabilityValidateError && !failure.uncertain
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
  <section v-if="canValidate()" aria-label="能力版本当前来源校验" :aria-busy="busy">
    <h4>当前来源校验</h4>
    <p>校验只生成本次来源与证据的报告，不改变 DRAFT，也不是审批结论。</p>
    <p v-if="error" role="alert">{{ error }}</p>
    <template v-if="report">
      <p role="status">{{ report.valid ? '当前来源校验通过；仍须独立正式评审。' : '当前来源校验未通过，不能送审。' }}</p>
      <p>条目 {{ report.item_count }}，文档引用 {{ report.document_ref_count }}，证据引用 {{ report.evidence_ref_count }}</p>
      <ul v-if="report.blocking_issues.length"><li v-for="issue in report.blocking_issues" :key="issue">
        {{ issue === 'SOURCE_UNAVAILABLE' ? '固定文档来源不可用' : '证据资格或同源关系不可用' }}
      </li></ul>
      <p>校验时间：{{ report.checked_at }}</p>
    </template>
    <template v-else>
      <p v-if="pending" role="status">原校验操作号已保留；先核对审计，再决定是否同号重试。</p>
      <label v-if="pending"><input v-model="retryConfirmed" type="checkbox" :disabled="busy || locked" /> 已核对历史，沿用原操作号重试</label>
      <button type="button" :disabled="busy || locked || !!pending && !retryConfirmed"
        @click="validate">{{ pending ? '按原操作号重试校验' : '运行当前来源校验' }}</button>
    </template>
  </section>
</template>
