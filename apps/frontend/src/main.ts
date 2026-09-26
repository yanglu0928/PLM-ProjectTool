import { createApp } from "vue";

import AppShell from "@/app/AppShell.vue";
import { createAppRouter } from "@/app/router";
import "@/styles/main.css";

const app = createApp(AppShell);
app.use(createAppRouter());
app.mount("#app");
