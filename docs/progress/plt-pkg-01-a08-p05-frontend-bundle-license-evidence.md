# PLT-PKG-01-A08-P05：前端冻结 bundle 来源与许可材料核查

## 编码前检查

- 当前 Phase：Phase 2 Platform Core；非发行证据。
- 当前 WBS：PLT-PKG-01-A08-P05；仅核查 A02 冻结前端交付物，不处理原生/系统组件。
- 输入基线：A02 源提交 `944bc7b2053b70d8704d9409bdc4eb4988288602`、锁 Hash `96ab30bab617bb1349eaf81a4143b22e57a6c3fc8500a06306c81e20c19fb468`、3 个 dist SHA-256；A08-P03 非发行候选。
- 前置任务：A02 dist/离线构建验证通过；正式发行合规未通过。
- 涉及模块：本地前端审计工具和 Git 忽略的 sourcemap 审计构建；无业务代码、实体、API、权限、Schema 或 Migration。
- 验收标准：审计构建与 A02 冻结 dist 字节对照、sourcemap 源文件与精确安装包源码对照、声明/许可文件 Hash 留证；区分直接依赖、打入 bundle 的包与构建依赖。
- 风险：sourcemap 不一定覆盖生成代码/CSS；包内声明不等于最终分发义务已履行。原 dist 不修改；新审计构建及 JSON 在忽略目录，可撤回。

## Windows 11 验证

- A02 隔离源码使用 `pnpm exec vite build --sourcemap --outDir dist-license-audit`：101 模块 transform，输出 HTML、JS、CSS 与一份 JS map。原 A02 dist 仍为 3 文件，Hash 与冻结清单一致；审计 HTML/CSS 与原件逐字节相同，审计 JS 仅追加一行 sourcemap 注释，前段 306,817 字节与原件逐字节相同。
- map 共 73 个源条目，其中 7 个第三方 JS 源文件与本机精确包源码逐字节一致，归属于 `@vue/shared`、`@vue/reactivity`、`@vue/runtime-core`、`@vue/runtime-dom`（均 3.5.43）及 `vue-router`（5.3.1）五个包。直接依赖另有 `vue` 3.5.43 入口包（自身未单独映射）；`vue-router` 同时是直接依赖。六包 package.json 均声明 MIT，均找到本机 `LICENSE` 文件并记录 Hash。上游 [Vue 核心](https://github.com/vuejs/core/blob/main/LICENSE)和 [Vue Router](https://github.com/vuejs/router/blob/main/LICENSE)也公开标示 MIT；精确交付证据以本地固定版本包为准。
- 原冻结 JS 中未找到 `MIT License`、`Permission is hereby granted` 或 `Copyright (c)` 文本，dist 也没有单独的许可文件。不能把 `node_modules` 存在的 LICENSE 当作已随客户端分发；下一项必须把这些精确版本许可材料保全并纳入新候选。
- `tools/audit_frontend_bundle_licenses.py` 输出 Git 忽略的 `artifacts/package-prep/windows11/frontend-20260930-232337-333c6e42/frontend-bundle-license-evidence.json`，固定 dist/lock/map Hash、每个映射模块源码 Hash、许可文件 Hash 与范围限制；3/3 合成测试 PASS，含审计 bundle 和源文件差异拒绝。

## 结论和下一项

`FRONTEND_MAPPED_SOURCE_EVIDENCE_PASS / LICENSE_REVIEW_REQUIRED / RELEASE_BLOCKED`。该结果不代表完整前端 SBOM 或法律批准；未覆盖全部构建工具、未映射生成代码、CSS 许可内容及系统/原生组件。下一项 `PLT-PKG-01-A08-P06` 保存并并入六个前端包的精确 LICENSE 文本，随后继续原生/系统组件清单。A08 与 Release 仍未完成，`release_eligible=false`。
