<script setup lang="ts">
import { inject, onMounted, onUnmounted, ref, toRaw } from "vue";
import { RouterLink } from "vue-router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { sessionClientKey } from "@/modules/auth/api/sessionContext";
import { ProjectMemberReadClient, type ProjectMemberView } from "@/modules/project/api/projectMemberReadClient";
import type { SurveyVersionView } from "@/modules/survey/api/surveyReadClient";
import { SurveyVersionSubmitReviewClient, SurveySubmitReviewError, type SurveyReviewSubmission }
  from "@/modules/survey/api/surveyVersionSubmitReviewClient";

const props = defineProps<{ version: SurveyVersionView; session?: SessionClient; members?: ProjectMemberReadClient;
  submitter?: SurveyVersionSubmitReviewClient }>();
const session = toRaw(props.session ?? inject(sessionClientKey, null) ?? new SessionClient());
const members = toRaw(props.members ?? new ProjectMemberReadClient());
const submitter = toRaw(props.submitter ?? new SurveyVersionSubmitReviewClient(session));
const actor = session.view?.user.user_id; const available = ref<readonly ProjectMemberView[]>([]);
const selected = ref<string[]>([]); const loaded = ref(false); const busy = ref(false); const sending = ref(false);
const error = ref(""); const submitted = ref<SurveyReviewSubmission | null>(null);
const confirmed = ref(false); const retryConfirmed = ref(false); const locked = ref(false);
type Attempt = { actor: string; project: string; survey: string; version: string; reviewer_ids: readonly string[]; key: string };
const pending = ref<Attempt | null>(null); let mounted = true;
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
function manager(): boolean { const view = session.view; return mounted && !!actor && view?.user.user_id === actor
  && !view.password_change_required && view.authorized_projects.some(p => p.project_id === props.version.project_id && p.role === "PROJECT_MANAGER"); }
function ready(): boolean { const v = props.version; return manager() && !pending.value && !submitted.value
  && v.state === "DRAFT" && v.review_ref === null && v.review_round_ref === null; }
function storageKey() { const v = props.version; return `plm.survey.version.review.pending.${actor ?? "none"}.${v.project_id}.${v.survey_id}.${v.survey_version_id}`; }
function restore() { if (!manager()) return; try { const raw = sessionStorage.getItem(storageKey()); if (!raw) return;
  const value: unknown = JSON.parse(raw); if (!value || typeof value !== "object" || Array.isArray(value)) throw Error();
  const item = value as Record<string, unknown>, ids = item.reviewer_ids, v = props.version;
  if (Object.keys(item).length !== 6 || item.actor !== actor || item.project !== v.project_id || item.survey !== v.survey_id
    || item.version !== v.survey_version_id || !Array.isArray(ids) || ids.length < 1 || ids.length > 32
    || ids.some(id => typeof id !== "string" || !uuid.test(id)) || new Set(ids).size !== ids.length
    || typeof item.key !== "string" || !/^[\x20-\x7e]{16,128}$/.test(item.key)) throw Error();
  pending.value = item as Attempt;
} catch { locked.value = true; error.value = "原送审记录无法安全读取；请核对评审与审计，勿换号重试。"; } }
async function loadMembers() { if (!manager() || busy.value || sending.value || pending.value) return;
  busy.value = true; error.value = "";
  try { const all: ProjectMemberView[] = [], cursors = new Set<string>(); let cursor: string | null = null;
    for (let page = 0; page < 20; page++) { const result = await members.list(props.version.project_id, cursor); all.push(...result.items);
      if (!result.has_more) { cursor = null; break; }
      if (!result.next_cursor || cursors.has(result.next_cursor)) throw Error("成员分页未能完整读取");
      cursors.add(result.next_cursor); cursor = result.next_cursor; }
    if (cursor !== null || new Set(all.map(item => item.member_id)).size !== all.length) throw Error("成员列表不完整");
    if (!mounted || !manager()) return;
    available.value = Object.freeze(all.filter(item => item.state === "ACTIVE"
      && (item.role === "CUSTOMER_MANAGER" || item.role === "CUSTOMER_MEMBER"))
      .sort((a, b) => a.user.display_name.localeCompare(b.user.display_name, "zh-CN")));
    const allowed = new Set(available.value.map(item => item.user.user_id)); selected.value = selected.value.filter(id => allowed.has(id));
    loaded.value = true; confirmed.value = false;
  } catch (failure) { if (mounted) { available.value = []; loaded.value = false;
    error.value = failure instanceof Error ? failure.message : "暂时无法读取当前客户评审人。"; } }
  finally { if (mounted) busy.value = false; }
}
async function submit() { if (!manager() || !session.canSubmit || busy.value || sending.value || locked.value) return;
  const version = props.version; let attempt = pending.value;
  if (attempt) { if (!retryConfirmed.value || attempt.actor !== actor || attempt.project !== version.project_id
      || attempt.survey !== version.survey_id || attempt.version !== version.survey_version_id) return; }
  else { if (!ready() || !loaded.value || !confirmed.value || !selected.value.length) return;
    const allowed = new Set(available.value.map(item => item.user.user_id));
    if (selected.value.length > 32 || selected.value.some(id => !allowed.has(id))) return;
    attempt = { actor: actor!, project: version.project_id, survey: version.survey_id, version: version.survey_version_id,
      reviewer_ids: Object.freeze([...selected.value].sort()), key: `survey-review-${crypto.randomUUID()}` };
    try { const encoded = JSON.stringify(attempt); sessionStorage.setItem(storageKey(), encoded);
      if (sessionStorage.getItem(storageKey()) !== encoded) throw Error(); pending.value = attempt;
    } catch { error.value = "无法保存原操作号，本次未发送送审。"; return; } }
  sending.value = true; retryConfirmed.value = false; error.value = "";
  try { const result = await submitter.submit(version, attempt.reviewer_ids, attempt.key);
    if (!mounted || !manager()) return;
    if (result.submitted_by !== actor || result.project_id !== version.project_id || result.survey_id !== version.survey_id
      || result.survey_version_id !== version.survey_version_id) { locked.value = true; error.value = "送审回执与当前调研版本不一致；请核对审计。"; return; }
    submitted.value = result;
    try { if (sessionStorage.getItem(storageKey()) !== JSON.stringify(attempt)) throw Error();
      sessionStorage.removeItem(storageKey()); pending.value = null;
    } catch { locked.value = true; error.value = "送审回执已收到，但原操作号清理失败；请勿再次提交。"; }
  } catch (failure) { if (!mounted) return; const known = failure instanceof SurveySubmitReviewError ? failure : null;
    error.value = known?.message ?? "送审结果无法确认；请保留原操作号。";
    if (known?.code === "CONFLICT_IDEMPOTENCY") locked.value = true;
    else if (known && !known.uncertain) { try { sessionStorage.removeItem(storageKey()); pending.value = null; } catch { locked.value = true; } }
  } finally { if (mounted) sending.value = false; }
}
const unsubscribe = session.subscribe(() => { submitted.value = null; retryConfirmed.value = false;
  if (sending.value || pending.value) error.value = "会话已变化；请核对原送审结果，勿换号重试。"; });
onMounted(restore); onUnmounted(() => { mounted = false; unsubscribe(); });
</script>

<template><section v-if="manager()" aria-label="调研版本客户评审送审" :aria-busy="busy || sending">
  <h3>提交调研版本给客户评审人</h3><p>仅送审当前固定草稿；服务器会重新核验来源、部门和评审资格。送审仅进入 IN_REVIEW，不代表客户批准或签署。</p>
  <p v-if="!session.canSubmit && !sending" role="status">当前会话仅可查看；请重新登录后再送审。</p>
  <p v-if="busy" role="status">正在读取完整的当前项目成员列表…</p><p v-if="error" role="alert">{{ error }}</p>
  <p v-if="pending" role="status">原送审结果未确认；评审人集合和操作号已保留，请先核对评审记录。</p>
  <label v-if="pending"><input v-model="retryConfirmed" type="checkbox" :disabled="sending || locked" />我已核对评审记录，按原评审人和操作号重试</label>
  <template v-else-if="ready()"><button type="button" :disabled="busy || sending || locked" @click="loadMembers">{{ loaded ? "刷新当前项目评审人" : "读取当前项目评审人" }}</button>
    <fieldset v-if="available.length" :disabled="sending"><legend>选择 ACTIVE 客户评审人（最多 32 人）</legend>
      <label v-for="member in available" :key="member.member_id"><input v-model="selected" type="checkbox" :value="member.user.user_id"
        :disabled="selected.length >= 32 && !selected.includes(member.user.user_id)" />{{ member.user.display_name }}（{{ member.role }}）</label></fieldset>
    <p v-else role="status">{{ loaded ? "当前没有可选择的合格客户评审人。" : "请先读取成员；列表未完整读取时不能送审。" }}</p>
    <label><input v-model="confirmed" type="checkbox" :disabled="sending" />我已核对该固定版本和问题，确认提交给所选客户评审人；这不代表客户确认</label>
  </template><p v-else-if="!submitted" role="status">当前版本不是未送审草稿；请刷新详情或查看已有评审。</p>
  <button v-if="pending || ready()" type="button" :disabled="sending || busy || locked || !session.canSubmit
    || (pending ? !retryConfirmed : !loaded || !confirmed || !selected.length)" @click="submit">{{ sending ? "正在送审…" : pending ? "按原操作号重试送审" : "提交调研版本评审" }}</button>
  <p v-if="submitted" role="status">已送审，评审 {{ submitted.review_id }}，首轮 {{ submitted.review_round_id }}；尚未批准。
    <RouterLink :to="{ name: 'project-review-detail', params: { projectId: submitted.project_id, reviewId: submitted.review_id } }">打开评审</RouterLink></p>
</section></template>
