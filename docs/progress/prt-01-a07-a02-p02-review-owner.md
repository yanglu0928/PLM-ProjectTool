# PRT-01-A07-A02-P02：Prototype Review Subject Owner

日期：2026-10-08。结论：`PRT_01_A07_A02_P02_REVIEW_OWNER_PASS`。下一项：
`PRT-01-A07-A03` 批准 Trace Owner 与反向来源闭包。

## 实施结果

- 新增 `PrototypeVersionCurrentValidator`，在送审和批准事务内重新证明固定 TemplateVersion、当前 Approved
  RequirementVersion、AVAILABLE DocumentVersion，并按Create同一规范重算聚合内容指纹；历史Validate报告
  不作为审批事实。
- 新增真实 `PRT-03 + PROTOTYPE_ALL_V1` PROJECT Subject Owner 与PostgreSQL仓储，复用统一Review
  create/start/decide/withdraw内核。只允许ACTIVE Prototype的最新DRAFT创建/开始评审，Reviewer逐人重证。
- START、APPROVED、RETURNED/WITHDRAWN经0132不可变结果闭包推进Root强版本。批准更新正式指针并
  SUPERSEDE旧批准版；退回/撤回映射RETURNED且保持旧指针。终态独立重读结果、指针和唯一APPROVED。
- Owner不提交调用方事务；每个终态写`PROTOTYPE_VERSION_<REVIEW_STATE>` Audit，失败由Review内核整体回滚。

## 验证与偏差

- Windows 11 / PostgreSQL 18.6真实统一Review链：v1批准，v2送审后Document失效时批准失败且不落决策，恢复
  后批准并SUPERSEDE v1，v3撤回且正式指针保持v2；Root lock=6、6条状态结果、3条终态Audit及drift均PASS。
- 单元首轮失败源于Python `Mock`默认保护`assert_*`属性，测试夹具未显式建立仓储断言方法；补齐Mock后重跑，
  产品实现和验收规则未变化。
- 定向26项/21 subtests；后端全量3144项通过、3项既有条件跳过、4684 subtests；compileall PASS。
- 开发wheel共1209项，SHA-256 `a30b16ca77c59d4359801f7358adcca96a9212f79eb44812dd41d97a0a827a33`。

## 兼容与边界

无新Migration、公开API、依赖、Secret或外发。停止注册Owner可关闭新Review入口，既有Review、Version、结果和
Audit必须保留。Server 2025未验证且不从Win11外推；Debian 13按指令跳过。批准Trace、原子业务送审、HTTP、
Windows生产组合、前端、Gate 3/UAT/正式发行仍待。
