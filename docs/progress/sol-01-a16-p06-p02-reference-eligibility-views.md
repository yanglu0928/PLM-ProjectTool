# SOL-01-A16-P06-P02：Reference Eligibility 双详情人工决定页

日期：2026-10-09。结果：`SOL_01_A16_P06_P02_REFERENCE_ELIGIBILITY_VIEWS_PASS`（组件/前端合同；真实浏览器/PG 下一项）。

## 编码前检查

- 当前 Phase/WBS：Phase 2 / SOL-01-A16-P06-P02；输入为冻结 API-04、CR-SOL-014、A16-P05 Windows 写组合和 A16-P06-P01 安全请求桥；前置满足。
- 单一问题：PROJECT/GLOBAL 当前详情页提供人工资格决定、理由和二次确认；不改变业务 Owner、DB、HTTP 合同或其他页面。
- 涉及实体/API/权限：现时 Reference GET 与 `:set-eligibility`；PROJECT Manager、GLOBAL DeploymentAdmin。权限/来源以服务端实时复验为准，UI 提前隐藏不构成安全边界。
- 验收：必须从当前 GET 的锁版本发起，理由 1～2000 字，合法状态转换及 REVOKED 终态；确认前零写；结果不确定保留原操作号；成功后单独显示历史回执并重新 GET 当前态，不把历史回执冒充当前资格。
- 风险：组件测试不等于真实人工确认或完整 Edge/PG 验收；后续 P03 单独取证。

## Changed / Files / Migration / API

- 新增共用 `ReferenceEligibilityPanel.vue`：状态/角色约束、理由输入、确认摘要、不可变事件提示、原号重试；Vue 组件内对 `SessionClient` 使用原始实例以保持私有安全状态。
- PROJECT/GLOBAL 详情页接入组件，成功回执独立提示并触发现时详情重新读取；路由变更清理旧回执。
- 文件：`apps/frontend/src/modules/solution/views/{ReferenceEligibilityPanel.vue,ReferenceEligibilityPanel.spec.ts,ProjectReferenceDetailView.vue,GlobalReferenceDetailView.vue}`、本进度、状态、版本说明。Migration：无。API：无变更。

## Tests / Result

- 组件定向 3 项：理由和二次确认前零写、成功事件、结果不确定保留原操作号及重试、非经理/已撤销隐藏写入口。
- PROJECT/GLOBAL 旧详情定向回归通过；前端全量 121 文件/1706 项通过，typecheck/build 通过。现有主 chunk 大于 500 kB 的构建提醒仍在。

## Known Issues / Next

无新依赖/Secret/客户数据外发。回滚为撤详情页组件接线并重建前端，资格后端和历史不回滚。下一项 P06-P03：Windows 11 Edge/隔离 PG 真实浏览器双 Scope、提交后当前态/SQL 及清理验收。真人判断、正式目标账户/HTTPS/License、Server2025、20 并发、Gate3/UAT/发行未验；Debian13 实机依用户指令跳过。

TraceLink：Gate2 API-04 → CR-SOL-014 → A16-P01～P05 → P06-P01 → 本 P02 → P03 → Gate3。
