<script setup lang="ts">
import { computed, inject, onUnmounted, ref, toRaw, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { sessionClientKey } from "@/modules/auth/api/sessionContext";
import { ProjectReviewClient, ProjectReviewError, type ProjectReviewView as ReviewView,
  type ReviewDecisionKind, type ReviewDecisionReceipt } from "@/modules/review/api/projectReviewClient";

const props=defineProps<{session?:SessionClient;reviews?:ProjectReviewClient}>();
const session=toRaw(props.session??inject(sessionClientKey,null)??new SessionClient());
const reviews=toRaw(props.reviews??new ProjectReviewClient(session)); const route=useRoute();
const current=ref<ReviewView|null>(null); const receipt=ref<ReviewDecisionReceipt|null>(null);
const busy=ref(false); const deciding=ref(false); const error=ref(""); const decisionError=ref("");
const returnComment=ref(""); const confirmApprove=ref(false); const confirmRetry=ref(false); const locked=ref(false);
type Pending={actor:string;project:string;review:string;round:string;decision:ReviewDecisionKind;comment:string|null;key:string};
const pending=ref<Pending|null>(null); let mounted=true;let generation=0;
const projectId=()=>typeof route.params.projectId==="string"?route.params.projectId:"";
const reviewId=()=>typeof route.params.reviewId==="string"?route.params.reviewId:"";
const mayRead=()=>mounted&&!!session.view&&!session.view.password_change_required&&session.view.authorized_projects.some(p=>p.project_id===projectId());
const assignment=computed(()=>current.value?.active_round?.assignments.find(a=>a.reviewer_id===session.view?.user.user_id)??null);
const isHandover=computed(()=>current.value?.subject_ref.resource_type==="HND-02");
const isSection=computed(()=>current.value?.subject_ref.resource_type==="SOL-05");
const isOutline=computed(()=>current.value?.subject_ref.resource_type==="SOL-03");
const isSurvey=computed(()=>current.value?.subject_ref.resource_type==="SRV-02");
const subjectLabel=computed(()=>isSurvey.value?"调研问题":isHandover.value?"交接分析":isOutline.value?"方案大纲":isSection.value?"方案章节":"结构化专项");
const mayDecide=computed(()=>!!current.value&&current.value.state==="IN_REVIEW"&&assignment.value?.state==="PENDING"&&session.canSubmit&&!locked.value);
function storageKey(){return `plm.review.decide.pending.${session.view?.user.user_id??"none"}.${projectId()}.${reviewId()}`}
function validPending(v:unknown):v is Pending{if(!v||typeof v!=="object"||Array.isArray(v))return false;const i=v as Record<string,unknown>;const id=/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;return i.actor===session.view?.user.user_id&&i.project===projectId()&&i.review===reviewId()&&typeof i.round==="string"&&id.test(i.round)&&["APPROVE","RETURN"].includes(String(i.decision))&&(i.comment===null||typeof i.comment==="string")&&typeof i.key==="string"&&/^[\x20-\x7e]{16,128}$/.test(i.key as string)&&((i.decision==="APPROVE"&&i.comment===null)||(i.decision==="RETURN"&&!!(i.comment as string).trim()))}
function restore(){pending.value=null;confirmRetry.value=false;locked.value=false;decisionError.value="";if(!mayRead())return;try{const raw=sessionStorage.getItem(storageKey());if(!raw)return;const parsed:unknown=JSON.parse(raw);if(!validPending(parsed))throw new Error();pending.value=parsed}catch{locked.value=true;decisionError.value="原决定记录无法读取，已停止再次提交；请核对评审与审计记录。"}}
async function load(){if(!mayRead()||busy.value)return;const p=projectId(),r=reviewId(),run=++generation;busy.value=true;error.value="";current.value=null;receipt.value=null;try{const result=await reviews.read(p,r);if(!mounted||run!==generation||p!==projectId()||r!==reviewId())return;current.value=result;if(pending.value&&pending.value.round!==result.active_round?.review_round_id){locked.value=true;decisionError.value="评审轮次已变化，已停止原决定重试；请核对审计记录。"}}catch(e){if(mounted&&run===generation)error.value=e instanceof Error?e.message:"暂时无法读取评审。"}finally{if(mounted&&run===generation)busy.value=false}}
async function decide(kind:ReviewDecisionKind){if(deciding.value||busy.value||locked.value||!current.value)return;const actor=session.view?.user.user_id;if(!actor)return;let attempt=pending.value;if(attempt){if(!confirmRetry.value)return}else{if(!mayDecide.value||kind==="APPROVE"&&!confirmApprove.value||kind==="RETURN"&&!returnComment.value.trim())return;attempt={actor,project:projectId(),review:reviewId(),round:current.value.active_round!.review_round_id,decision:kind,comment:kind==="RETURN"?returnComment.value.trim():null,key:`review-decision-${crypto.randomUUID()}`};try{sessionStorage.setItem(storageKey(),JSON.stringify(attempt))}catch{decisionError.value="无法保存原决定操作号，本次未发送。";return}pending.value=attempt}const before=current.value;const run=generation;deciding.value=true;confirmRetry.value=false;decisionError.value="";try{const result=await reviews.decide(before,attempt.decision,attempt.comment,attempt.key);if(!mounted||run!==generation||actor!==session.view?.user.user_id)return;receipt.value=result;try{sessionStorage.removeItem(storageKey());pending.value=null}catch{locked.value=true;decisionError.value="决定回执已收到，但原操作号清理失败；请勿再次提交。"}current.value=null;const refreshed=await reviews.read(projectId(),reviewId());if(refreshed.review_id!==result.review_id||refreshed.state!==result.state||refreshed.etag!==result.etag){locked.value=true;decisionError.value="决定回执与当前评审状态不一致，已停止后续提交；请核对审计记录。";return}current.value=refreshed;returnComment.value="";confirmApprove.value=false}catch(e){if(!mounted||run!==generation)return;const known=e instanceof ProjectReviewError?e:null;decisionError.value=known?.message??"决定结果无法确认；请保留原决定和操作号。";if(known?.code==="CONFLICT_IDEMPOTENCY")locked.value=true;else if(known&&!known.uncertain){try{sessionStorage.removeItem(storageKey());pending.value=null}catch{locked.value=true}}}finally{if(mounted&&run===generation)deciding.value=false}}
watch(()=>[route.name,route.params.projectId,route.params.reviewId],()=>{generation+=1;current.value=null;receipt.value=null;busy.value=false;deciding.value=false;error.value="";returnComment.value="";confirmApprove.value=false;restore();if(route.name==="project-review-detail")void load()},{immediate:true});
onUnmounted(()=>{mounted=false;generation+=1});
function stateLabel(v:string){return({DRAFT:"待开始",IN_REVIEW:"评审中",APPROVED:"已批准",RETURNED:"已退回",WITHDRAWN:"已撤回"} as Record<string,string>)[v]??"未知"}
</script>

<template><section class="review" aria-labelledby="review-title" :aria-busy="busy">
  <p class="section-kicker">项目治理 · 已知评审</p><h1 id="review-title">{{subjectLabel}}评审</h1>
  <p v-if="isHandover&&current"><RouterLink :to="{name:'project-handover-detail',params:{projectId:current.project_id,analysisId:current.subject_ref.resource_id}}">返回交接分析</RouterLink></p>
  <p v-else-if="isSurvey&&current?.active_round"><RouterLink :to="{name:'project-survey-detail',params:{projectId:current.project_id,surveyId:current.subject_ref.resource_id},query:{fixedVersionId:current.active_round.subject_version_ref}}">返回本轮固定调研版本</RouterLink></p>
  <p v-else-if="isSurvey&&current"><RouterLink :to="{name:'project-survey-detail',params:{projectId:current.project_id,surveyId:current.subject_ref.resource_id}}">返回调研定义</RouterLink></p>
  <p v-else><RouterLink :to="{name:'project-reviews',params:{projectId:route.params.projectId}}">返回评审待办与历史</RouterLink></p>
  <p class="warning">请从评审待办核对当前分配与固定版本。决定只代表本轮评审，不等于合同意义上的客户签署、实施完成或 UAT 通过。</p>
  <p v-if="!mayRead()" role="status">当前会话没有此项目的读取权限。</p>
  <template v-else><button type="button" :disabled="busy||deciding" @click="load">{{busy?'正在读取…':'刷新评审'}}</button>
    <p v-if="error" role="alert">{{error}}</p><p v-else-if="busy" role="status">正在读取评审…</p>
    <template v-else-if="current"><h2>状态：{{stateLabel(current.state)}}</h2>
      <dl><dt>评审编号</dt><dd>{{current.review_id}}</dd><dt>{{isSurvey?'调研定义':isHandover?'交接分析':isOutline?'大纲':isSection?'章节':'专项系列'}}</dt><dd>{{current.subject_ref.resource_id}}</dd><dt>策略</dt><dd>{{current.policy_code}}</dd><dt>版本</dt><dd>{{current.etag}}</dd></dl>
      <section v-if="current.active_round" aria-labelledby="round-title"><h3 id="round-title">当前活动轮次 {{current.active_round.round_no}}</h3>
        <p v-if="isHandover">本轮固定交接版本 ID：{{current.active_round.subject_version_ref}}。<RouterLink :to="{name:'project-handover-detail',params:{projectId:current.project_id,analysisId:current.subject_ref.resource_id},query:{fixedVersionId:current.active_round.subject_version_ref}}">打开本轮固定交接版本</RouterLink></p>
        <p v-else-if="isSection"><RouterLink :to="{name:'project-section-version-detail',params:{projectId:current.project_id,sectionId:current.subject_ref.resource_id,versionId:current.active_round.subject_version_ref}}">查看本轮固定章节版本</RouterLink></p>
        <p v-else-if="isOutline"><RouterLink :to="{name:'project-outline-version-detail',params:{projectId:current.project_id,outlineId:current.subject_ref.resource_id,versionId:current.active_round.subject_version_ref}}">查看本轮固定大纲版本</RouterLink></p>
        <p v-else-if="isSurvey"><RouterLink :to="{name:'project-survey-detail',params:{projectId:current.project_id,surveyId:current.subject_ref.resource_id},query:{fixedVersionId:current.active_round.subject_version_ref}}">查看本轮固定调研问题版本</RouterLink></p>
        <p v-else><RouterLink :to="{name:'project-structured-spec-detail',params:{projectId:current.project_id,specId:current.active_round.subject_version_ref}}">查看本轮固定专项版本</RouterLink></p>
        <ul><li v-for="item in current.active_round.assignments" :key="item.assignment_id">评审人 {{item.reviewer_id}}：{{item.state==='PENDING'?'待决定':`已${item.decision?.decision==='APPROVE'?'批准':'退回'}`}}<span v-if="item.decision?.comment">；意见：{{item.decision.comment}}</span></li></ul>
        <p v-if="!assignment" role="status">你不是本轮评审人，可查看状态但不能提交决定。</p><p v-else-if="assignment.state==='DECIDED'" role="status">你已完成本轮决定。</p>
        <template v-else-if="mayDecide"><div v-if="pending" class="pending" role="status">存在结果未知的原决定：{{pending.decision==='APPROVE'?'批准':'退回'}}<span v-if="pending.comment">，意见“{{pending.comment}}”</span>。请核对当前状态并保持原操作号。</div>
          <label v-if="pending"><input v-model="confirmRetry" type="checkbox" :disabled="deciding||locked"> 我已核对并确认按原决定、原意见和原操作号重试</label>
          <template v-else><label><input v-model="confirmApprove" type="checkbox" :disabled="deciding"> 我已核对固定{{subjectLabel}}版本与当前评审范围</label>
            <button type="button" :disabled="deciding||!confirmApprove" @click="decide('APPROVE')">批准本轮</button>
            <label>退回意见（必填）<textarea v-model="returnComment" :disabled="deciding" maxlength="4000" /></label>
            <button type="button" :disabled="deciding||!returnComment.trim()" @click="decide('RETURN')">退回修改</button></template>
          <button v-if="pending" type="button" :disabled="deciding||locked||!confirmRetry" @click="decide(pending.decision)">按原操作号重试决定</button>
        </template>
      </section><p v-else role="status">当前没有活动轮次；历史决定仍保留在服务端，本页不把历史轮伪装成待办。</p>
      <p v-if="decisionError" role="alert">{{decisionError}}</p><p v-if="receipt" role="status">决定已记录：{{receipt.decision==='APPROVE'?'批准':'退回'}}；当前聚合状态 {{stateLabel(receipt.state)}}。请以服务端评审记录核对，不等于合同签署或 UAT 通过。</p>
    </template>
  </template>
</section></template>

<style scoped>.review{max-width:58rem;margin:1rem auto;padding:1.5rem;background:#fff;border-radius:1rem}.review dl{display:grid;grid-template-columns:8rem 1fr;gap:.5rem 1rem}.review dd{margin:0;overflow-wrap:anywhere}.warning,.pending{padding:.8rem 1rem;border-left:.3rem solid #d29b42;background:#fff8e9}.review label{display:block;margin-block:.8rem}.review textarea{display:block;width:100%;min-height:7rem;margin-top:.35rem}.review button{margin:.35rem .6rem .35rem 0}.review [role=alert]{color:#a21d25}</style>
