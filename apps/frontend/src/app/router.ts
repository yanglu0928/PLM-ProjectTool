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
        path: "/:pathMatch(.*)*",
        name: "not-found",
        component: NotFoundView,
      },
    ],
    scrollBehavior: () => ({ top: 0 }),
  });
}
