import type { InjectionKey } from "vue";
import type { SessionClient } from "@/modules/auth/api/sessionClient";

export const sessionClientKey: InjectionKey<SessionClient> = Symbol("plm-session-client");
