import {
  createRouter,
  createWebHistory,
  type Router,
  type RouterHistory,
} from "vue-router";

import HomeView from "@/app/views/HomeView.vue";
import NotFoundView from "@/app/views/NotFoundView.vue";
import LoginView from "@/modules/auth/views/LoginView.vue";
import ProjectListView from "@/modules/project/views/ProjectListView.vue";
import ProjectDetailView from "@/modules/project/views/ProjectDetailView.vue";
import ProjectCreateView from "@/modules/project/views/ProjectCreateView.vue";
import ProjectMemberListView from "@/modules/project/views/ProjectMemberListView.vue";
import ProjectMemberCreateView from "@/modules/project/views/ProjectMemberCreateView.vue";
import ProjectDepartmentListView from "@/modules/project/views/ProjectDepartmentListView.vue";
import ProjectDepartmentCreateView from "@/modules/project/views/ProjectDepartmentCreateView.vue";
import AdminUserCreateView from "@/modules/auth/views/AdminUserCreateView.vue";
import AdminUserListView from "@/modules/auth/views/AdminUserListView.vue";
import AdminUserDetailView from "@/modules/auth/views/AdminUserDetailView.vue";
import AdminUserNameView from "@/modules/auth/views/AdminUserNameView.vue";
import ProjectDocumentListView from "@/modules/document/views/ProjectDocumentListView.vue";
import ProjectDocumentDetailView from "@/modules/document/views/ProjectDocumentDetailView.vue";
import ProjectDocumentUploadView from "@/modules/document/views/ProjectDocumentUploadView.vue";
import ProjectEvidenceListView from "@/modules/evidence/views/ProjectEvidenceListView.vue";
import GlobalEvidenceListView from "@/modules/evidence/views/GlobalEvidenceListView.vue";
import ProjectJobListView from "@/modules/jobs/views/ProjectJobListView.vue";
import AdminJobListView from "@/modules/jobs/views/AdminJobListView.vue";
import ProjectJobDetailView from "@/modules/jobs/views/ProjectJobDetailView.vue";
import AdminJobDetailView from "@/modules/jobs/views/AdminJobDetailView.vue";
import ProjectWorkflowView from "@/modules/workflow/views/ProjectWorkflowView.vue";
import ProjectAIWorkbenchView from "@/modules/ai/views/ProjectAIWorkbenchView.vue";
import ProjectAITaskDetailView from "@/modules/ai/views/ProjectAITaskDetailView.vue";
import ProjectAISuggestionView from "@/modules/ai/views/ProjectAISuggestionView.vue";
import ProjectAISubmitView from "@/modules/ai/views/ProjectAISubmitView.vue";
import ProjectRetrievalView from "@/modules/rag/views/ProjectRetrievalView.vue";
import ProjectHandoverListView from "@/modules/handover/views/ProjectHandoverListView.vue";
import ProjectHandoverDetailView from "@/modules/handover/views/ProjectHandoverDetailView.vue";
import ProjectHandoverActionView from "@/modules/handover/views/ProjectHandoverActionView.vue";
import ProjectSurveyListView from "@/modules/survey/views/ProjectSurveyListView.vue";
import ProjectSurveyDetailView from "@/modules/survey/views/ProjectSurveyDetailView.vue";
import ProjectSurveyRoundView from "@/modules/survey/views/ProjectSurveyRoundView.vue";
import ProjectSurveyAssignmentView from "@/modules/survey/views/ProjectSurveyAssignmentView.vue";
import ProjectSurveyConclusionView from "@/modules/survey/views/ProjectSurveyConclusionView.vue";
import ProjectRequirementListView from "@/modules/requirement/views/ProjectRequirementListView.vue";
import ProjectRequirementDetailView from "@/modules/requirement/views/ProjectRequirementDetailView.vue";
import ProjectRequirementDraftView from "@/modules/requirement/views/ProjectRequirementDraftView.vue";

const GlobalPrototypeTemplateView = () => import("@/modules/prototype/views/GlobalPrototypeTemplateView.vue");
const ProjectPrototypeDetailView = () => import("@/modules/prototype/views/ProjectPrototypeDetailView.vue");
const ProjectPrototypeLinkView = () => import("@/modules/prototype/views/ProjectPrototypeLinkView.vue");
const ProjectPrototypeListView = () => import("@/modules/prototype/views/ProjectPrototypeListView.vue");
const ProjectPrototypePackageView = () => import("@/modules/prototype/views/ProjectPrototypePackageView.vue");
const ProjectPrototypeTemplateView = () => import("@/modules/prototype/views/ProjectPrototypeTemplateView.vue");
const ProjectPrototypeVersionView = () => import("@/modules/prototype/views/ProjectPrototypeVersionView.vue");
const ProjectReferenceListView = () => import("@/modules/solution/views/ProjectReferenceListView.vue");
const ProjectReferenceDetailView = () => import("@/modules/solution/views/ProjectReferenceDetailView.vue");
const ProjectOutlineListView = () => import("@/modules/solution/views/ProjectOutlineListView.vue");
const ProjectOutlineDetailView = () => import("@/modules/solution/views/ProjectOutlineDetailView.vue");
const GlobalReferenceDeidentificationView = () => import("@/modules/solution/views/GlobalReferenceDeidentificationView.vue");
const GlobalReferenceSourcePickerView = () => import("@/modules/solution/views/GlobalReferenceSourcePickerView.vue");
const GlobalReferenceListView = () => import("@/modules/solution/views/GlobalReferenceListView.vue");
const GlobalReferenceDetailView = () => import("@/modules/solution/views/GlobalReferenceDetailView.vue");

export function createAppRouter(
  history: RouterHistory = createWebHistory(),
): Router {
  return createRouter({
    history,
    routes: [
      {
        path: "/",
        name: "home",
        component: HomeView,
      },
      {
        path: "/login",
        name: "login",
        component: LoginView,
      },
      {
        path: "/projects",
        name: "projects",
        component: ProjectListView,
      },
      {
        path: "/projects/new",
        name: "project-create",
        component: ProjectCreateView,
      },
      {
        path: "/admin/users",
        name: "admin-users",
        component: AdminUserListView,
      },
      {
        path: "/admin/users/new",
        name: "admin-user-create",
        component: AdminUserCreateView,
      },
      {
        path: "/admin/users/:userId",
        name: "admin-user-detail",
        component: AdminUserDetailView,
      },
      {
        path: "/admin/users/:userId/name",
        name: "admin-user-name",
        component: AdminUserNameView,
      },
      {
        path: "/projects/:projectId/ai/new",
        name: "project-ai-submit",
        component: ProjectAISubmitView,
      },
      {
        path: "/projects/:projectId/retrievals/new",
        name: "project-retrieval-new",
        component: ProjectRetrievalView,
      },
      {
        path: "/projects/:projectId/retrievals/:runId",
        name: "project-retrieval-detail",
        component: ProjectRetrievalView,
      },
      {
        path: "/projects/:projectId/ai/:taskId/suggestion",
        name: "project-ai-suggestion",
        component: ProjectAISuggestionView,
      },
      {
        path: "/projects/:projectId/ai/:taskId",
        name: "project-ai-task-detail",
        component: ProjectAITaskDetailView,
      },
      {
        path: "/projects/:projectId/ai",
        name: "project-ai-workbench",
        component: ProjectAIWorkbenchView,
      },
      {
        path: "/projects/:projectId/handover-actions",
        name: "project-handover-actions",
        component: ProjectHandoverActionView,
      },
      {
        path: "/projects/:projectId/handover",
        name: "project-handover",
        component: ProjectHandoverListView,
      },
      {
        path: "/projects/:projectId/handover/:analysisId",
        name: "project-handover-detail",
        component: ProjectHandoverDetailView,
      },
      {
        path: "/projects/:projectId/survey-conclusions",
        name: "project-survey-conclusions",
        component: ProjectSurveyConclusionView,
      },
      {
        path: "/projects/:projectId/survey-rounds/:roundId/assignments",
        name: "project-survey-assignments",
        component: ProjectSurveyAssignmentView,
      },
      {
        path: "/projects/:projectId/survey-rounds",
        name: "project-survey-rounds",
        component: ProjectSurveyRoundView,
      },
      {
        path: "/projects/:projectId/surveys",
        name: "project-surveys",
        component: ProjectSurveyListView,
      },
      {
        path: "/projects/:projectId/surveys/:surveyId",
        name: "project-survey-detail",
        component: ProjectSurveyDetailView,
      },
      {
        path: "/projects/:projectId/requirements",
        name: "project-requirements",
        component: ProjectRequirementListView,
      },
      {
        path: "/projects/:projectId/requirements/:requirementId",
        name: "project-requirement-detail",
        component: ProjectRequirementDetailView,
      },
      {
        path: "/projects/:projectId/requirements/:requirementId/draft",
        name: "project-requirement-draft",
        component: ProjectRequirementDraftView,
      },
      {
        path: "/projects/:projectId/workflow",
        name: "project-workflow",
        component: ProjectWorkflowView,
      },
      {
        path: "/projects/:projectId/evidence",
        name: "project-evidence",
        component: ProjectEvidenceListView,
      },
      {
        path: "/projects/:projectId/jobs/:jobId",
        name: "project-job-detail",
        component: ProjectJobDetailView,
      },
      {
        path: "/projects/:projectId/jobs",
        name: "project-jobs",
        component: ProjectJobListView,
      },
      {
        path: "/admin/evidence",
        name: "global-evidence",
        component: GlobalEvidenceListView,
      },
      {
        path: "/admin/reference-deidentification",
        name: "global-reference-source-picker",
        component: GlobalReferenceSourcePickerView,
      },
      {
        path: "/admin/reference-solutions/:referenceId",
        name: "global-reference-detail",
        component: GlobalReferenceDetailView,
      },
      {
        path: "/admin/reference-solutions",
        name: "global-references",
        component: GlobalReferenceListView,
      },
      {
        path: "/admin/reference-deidentification/:evidenceId",
        name: "global-reference-deidentification",
        component: GlobalReferenceDeidentificationView,
      },
      {
        path: "/admin/jobs/:jobId",
        name: "admin-job-detail",
        component: AdminJobDetailView,
      },
      {
        path: "/admin/jobs",
        name: "admin-jobs",
        component: AdminJobListView,
      },
      {
        path: "/admin/prototype-templates",
        name: "global-prototype-templates",
        component: GlobalPrototypeTemplateView,
      },
      {
        path: "/projects/:projectId/documents/new",
        name: "project-document-upload",
        component: ProjectDocumentUploadView,
      },
      {
        path: "/projects/:projectId/documents/:documentId/upload",
        name: "project-document-version-upload",
        component: ProjectDocumentUploadView,
      },
      {
        path: "/projects/:projectId/documents/:documentId",
        name: "project-document-detail",
        component: ProjectDocumentDetailView,
      },
      {
        path: "/projects/:projectId/documents",
        name: "project-documents",
        component: ProjectDocumentListView,
      },
      {
        path: "/projects/:projectId/departments/new",
        name: "project-department-create",
        component: ProjectDepartmentCreateView,
      },
      {
        path: "/projects/:projectId/departments",
        name: "project-departments",
        component: ProjectDepartmentListView,
      },
      {
        path: "/projects/:projectId/members/new",
        name: "project-member-create",
        component: ProjectMemberCreateView,
      },
      {
        path: "/projects/:projectId/members",
        name: "project-members",
        component: ProjectMemberListView,
      },
      {
        path: "/projects/:projectId/prototype-packages",
        name: "project-prototype-packages",
        component: ProjectPrototypePackageView,
      },
      {
        path: "/projects/:projectId/prototype-templates",
        name: "project-prototype-templates",
        component: ProjectPrototypeTemplateView,
      },
      {
        path: "/projects/:projectId/prototype-links",
        name: "project-prototype-links",
        component: ProjectPrototypeLinkView,
      },
      {
        path: "/projects/:projectId/prototypes/:prototypeId/versions/:versionId",
        name: "project-prototype-version-detail",
        component: ProjectPrototypeVersionView,
      },
      {
        path: "/projects/:projectId/prototypes/:prototypeId/versions",
        name: "project-prototype-versions",
        component: ProjectPrototypeVersionView,
      },
      {
        path: "/projects/:projectId/prototypes/:prototypeId",
        name: "project-prototype-detail",
        component: ProjectPrototypeDetailView,
      },
      {
        path: "/projects/:projectId/prototypes",
        name: "project-prototypes",
        component: ProjectPrototypeListView,
      },
      {
        path: "/projects/:projectId/solution-outlines/:outlineId",
        name: "project-outline-detail",
        component: ProjectOutlineDetailView,
      },
      {
        path: "/projects/:projectId/solution-outlines",
        name: "project-outlines",
        component: ProjectOutlineListView,
      },
      {
        path: "/projects/:projectId/reference-solutions/:referenceId",
        name: "project-reference-detail",
        component: ProjectReferenceDetailView,
      },
      {
        path: "/projects/:projectId/reference-solutions",
        name: "project-references",
        component: ProjectReferenceListView,
      },
      {
        path: "/projects/:projectId",
        name: "project-detail",
        component: ProjectDetailView,
      },
      {
        path: "/:pathMatch(.*)*",
        name: "not-found",
        component: NotFoundView,
      },
    ],
    scrollBehavior: () => ({ top: 0 }),
  });
}
