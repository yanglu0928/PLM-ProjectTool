# PLT-PKG-01-A08-P06：前端精确版本许可文件补充归档

## 编码前检查

- 当前 Phase：Phase 2 Platform Core；非发行准备。
- 当前 WBS：PLT-PKG-01-A08-P06。
- 输入基线：A02 冻结前端 dist/lock、A08-P05 映射与直接依赖许可证据。
- 前置任务：A08-P05 本机核对通过；法律审查与 Release Gate 未通过。
- 涉及模块：本地许可补充归档工具和 Git 忽略产物；无实体、API、权限、Schema、Migration 或正式安装变化。
- 验收标准：重新核对 A02 dist/lock/映射源码后，将六个精确包的 LICENSE 原文字节保全、逐件 Hash/ZIP 回读；缺文件或篡改失败关闭，禁止覆盖现存归档。
- 风险：补充 ZIP 尚未并入正式候选；许可材料存在不等于完整义务审核。可撤独立工具及经路径核对的忽略归档回滚，原 A02 dist/A08-P03 ZIP 保持不变。

## 执行结果

- 为 A08-P05 本地证据增加包目录的相对路径，仍要求目录在隔离 `node_modules` 内；当前重跑冻结 dist/lock/映射源码核对 PASS。
- 新工具将 `@vue/reactivity`、`@vue/runtime-core`、`@vue/runtime-dom`、`@vue/shared`、`vue`（均 3.5.43）与 `vue-router` 5.3.1 的精确本机 LICENSE 文件逐件 Hash 重核，生成 Git 忽略的 `artifacts/package-prep/windows11/frontend-20260930-232337-333c6e42/NOT-FOR-RELEASE-frontend-license-sidecar.zip`。共 6 文件/6 包，ZIP 5,585 字节、SHA-256 `024bfc1048f5468d2d52d79c13f533a67983a4b80d0e5ed720338ac52879e956`；逐件回读/manifest PASS。五个 Vue 包 LICENSE Hash 相同，Router 不同，均保留独立来源对应关系。
- `py -3.13 -m unittest tools.tests.test_audit_frontend_bundle_licenses tools.tests.test_build_frontend_license_sidecar`：5/5 PASS，覆盖冻结 bundle/源码差异、缺 LICENSE 与禁止覆盖。

## 结论与后续

`FRONTEND_LICENSE_SIDECAR_INTEGRITY_PASS / RELEASE_BLOCKED`。下一项 `PLT-PKG-01-A08-P07` 把六份材料加入新非发行候选并重做整包/全新解包验证；随后核查原生/系统组件、Ghostscript、模型等。法律审查、本产品许可、Gate 仍待，`release_eligible=false`。
