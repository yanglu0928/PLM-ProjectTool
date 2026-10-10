import { config } from "@vue/test-utils";

config.global.stubs = {
  transition: false,
  "transition-group": false,
};

Object.defineProperty(window, "scrollTo", {
  configurable: true,
  value: () => undefined,
});
