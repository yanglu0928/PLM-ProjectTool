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
