<script setup lang="ts">
import { computed, ref, toRaw, watch } from "vue";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import type { ReferenceCurrent } from "@/modules/solution/api/referenceReadClient";
import type { GlobalReferenceCurrent } from "@/modules/solution/api/globalReferenceReadClient";
import { ReferenceEligibilityClient, ReferenceEligibilityClientError,
  type EligibilityTarget, type ReferenceEligibilityReceipt } from "@/modules/solution/api/referenceEligibilityClient";

type Current = ReferenceCurrent | GlobalReferenceCurrent;
const props = defineProps<{ current: Current; session: SessionClient; eligibility?: ReferenceEligibilityClient }>();
const emit = defineEmits<{ accepted: [receipt: ReferenceEligibilityReceipt] }>();
const session = toRaw(props.session);
const client = toRaw(props.eligibility ?? new ReferenceEligibilityClient(session));
const target = ref<EligibilityTarget | null>(null);
const reason = ref("");
const pending = ref<{ current: Current; target: EligibilityTarget; reason: string; key: string } | null>(null);
const busy = ref(false); const uncertainResult = ref(false); const error = ref("");
const allowed = computed<readonly EligibilityTarget[]>(() => ({
  REFERENCE_ONLY: ["ELIGIBLE", "RESTRICTED", "REVOKED"],
  ELIGIBLE: ["RESTRICTED", "REVOKED"], RESTRICTED: ["ELIGIBLE", "REVOKED"], REVOKED: [],
}[props.current.eligibility_state] as readonly EligibilityTarget[]));
const mayDecide = computed(() => {
  const view = session.view;
  return !!view && !view.password_change_required && session.canSubmit && allowed.value.length > 0
    && (props.current.scope === "GLOBAL" ? view.deployment_role === "DEPLOYMENT_ADMIN"
      : view.authorized_projects.some(item => item.project_id === props.current.project_id
        && item.role === "PROJECT_MANAGER"));
});
const validReason = computed(() => reason.value.length >= 1 && reason.value.length <= 2000
  && reason.value === reason.value.trim() && reason.value === reason.value.normalize("NFC")
  && !/\p{Cc}/u.test(reason.value));
function prepare() {
  if (!mayDecide.value || busy.value || pending.value || !target.value
    || !allowed.value.includes(target.value) || !validReason.value) return;
  pending.value = { current: props.current, target: target.value,
    reason: reason.value, key: crypto.randomUUID() };
  error.value = ""; uncertainResult.value = false;
}
async function submit() {
  if (!pending.value || busy.value || !mayDecide.value) return;
  const command = pending.value;
  busy.value = true; error.value = "";
  try {
    const receipt = await client.set(command.current, command.target, command.reason, command.key);
    pending.value = null; uncertainResult.value = false;
    emit("accepted", receipt);
  } catch (failure) {
    uncertainResult.value = failure instanceof ReferenceEligibilityClientError && failure.uncertain;
    error.value = failure instanceof Error ? failure.message : "提交结果不确定，请保留原操作号。";
    if (!uncertainResult.value) pending.value = null;
  } finally { busy.value = false; }
}
function cancel() {
  if (busy.value || uncertainResult.value) return;
  pending.value = null; error.value = "";
}
watch(() => [props.current.reference_solution_id, props.current.reference_version_id, props.current.etag], () => {
  if (uncertainResult.value) return;
  target.value = null; reason.value = ""; pending.value = null; error.value = "";
});
</script>

<template>
  <section aria-label="参考方案人工资格决定">
    <h3>人工资格决定</h3>
    <p>当前标记仅来自刚读取的参考方案；标记为“可用”也不代替使用时对来源、权限和版本的实时核验。</p>
    <p v-if="current.eligibility_state === 'REVOKED'" role="status">此参考身份已撤销，不能恢复资格。</p>
    <p v-else-if="!mayDecide && !pending" role="status">仅具备当前权限的负责人可提交资格决定。</p>
    <template v-else>
      <template v-if="!pending">
        <fieldset><legend>选择当前资格</legend>
          <label v-if="allowed.includes('ELIGIBLE')"><input v-model="target" type="radio" value="ELIGIBLE"> 可用（已核对当前来源）</label>
          <label v-if="allowed.includes('RESTRICTED')"><input v-model="target" type="radio" value="RESTRICTED"> 受限</label>
          <label v-if="allowed.includes('REVOKED')"><input v-model="target" type="radio" value="REVOKED"> 永久撤销</label>
        </fieldset>
        <label>决定理由（1～2000 字，需说明核对依据或限制原因）
          <textarea v-model="reason" maxlength="2000" rows="4" />
        </label>
        <p>提交前请核对固定文档/证据原文；服务端提交时还会重新验证当前来源及权限。</p>
        <button type="button" :disabled="!mayDecide || !target || !validReason" @click="prepare">核对并进入确认</button>
      </template>
      <div v-else role="group" aria-label="资格决定二次确认">
        <p>请确认：将当前参考方案设为「{{ pending.target }}」；理由：{{ pending.reason }}</p>
        <p>此操作会写入不可变资格事件和审计；成功回执只是首次提交记录，之后仍需重新读取当前状态。</p>
        <p v-if="uncertainResult">结果不确定。原操作号：<code>{{ pending.key }}</code>。请勿更换操作号重试。</p>
        <button type="button" :disabled="busy || !mayDecide" @click="submit">{{ busy ? "正在提交…" : uncertainResult ? "按原操作号重试" : "确认提交资格决定" }}</button>
        <button v-if="!uncertainResult" type="button" :disabled="busy" @click="cancel">返回修改</button>
      </div>
    </template>
    <p v-if="error" role="alert">{{ error }}</p>
  </section>
</template>
