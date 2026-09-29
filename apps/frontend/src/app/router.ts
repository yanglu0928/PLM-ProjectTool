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
