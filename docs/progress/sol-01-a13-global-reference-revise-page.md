# SOL-01-A13-P02：GLOBAL Reference Revise 页面

日期：2026-10-09。结果：`SOL_01_A13_P02_GLOBAL_REVISE_FRONTEND_PASS`。

## 编码前检查

- Phase/WBS：Phase 2 Platform Core / SOL-01-A13-P02。依据冻结 API-04、CR-SOL-013/015、A11 修订客户端、A13-P01 前置核查和 DEC-20261009-1132；前置已满足。
- 单一问题：在既有 GLOBAL 多来源人工脱敏确认流程中接入明确的参考方案修订目标与安全恢复。实体仅 GLOBAL Reference；部署管理员；不改后端、DB Schema、Migration、API 合同、依赖或权限。
- 验收：详情页有修订入口；修订页先读取当前目标/版本/ETag，新来源重新选择、预览、逐项打开原文和本人确认，写前重读目标、Evidence 当前资格与预览指纹；原正文/ETag/Key 按账户与目标独立保存；未知结果仅同号恢复；历史回执和当前 GET 分离。创建页面行为保持。

## 实施与验证

- 复用现有 `GlobalReferenceSourcePickerView` 多来源流程，新增修订路由 `/admin/reference-solutions/:referenceId/revise` 和管理员详情入口。修订模式隐藏创建名称/创建提交，独立保存修订待核对记录，并在目标变化时清空页面状态。确认有效期、指纹、逐项核查与服务端最终证明共同约束修订。
- 提交前重读目标当前 `reference_version_id`/ETag、所选 Evidence Viewer 与当前资格，再重算有序文档/Evidence 预览指纹。首次请求前持久化原正文、If-Match 与操作号；未知结果不生成新号，显式同号重试；本地记录损坏时关闭新提交。201 只显示历史回执，另 GET 当前详情确认是否仍指向该版本。
- 合同测试新增未知首次响应→同号恢复、独立待核对存储及损坏记录关闭；既有创建流程回归。Windows 11 前端 119 文件/1694 测试、typecheck、生产构建通过。构建有既有主包 >500 kB 提示，未作为性能通过证明。

## 边界与下一项

本项仅验证前端合同，非真实浏览器/PG 端到端或真人脱敏判断。当前 GLOBAL 候选选择器沿用至少两条 Evidence 的多来源 UI；服务端允许的文档-only 来源尚未在此 UI 开放，不能宣称覆盖所有合法来源集合。A13-P03 需在 Windows 11 Edge/隔离 PostgreSQL 验证真实 Session、写入、同号恢复、角色拒绝和单一版本/审计；随后 A14 汇总双 Scope 边界。正式目标账户/信任源、20 并发、Server 2025、Gate 3/UAT/发行均未通过；Debian 13 实机按用户指令暂跳过。

回滚：撤下修订路由和详情入口可关闭新 UI；已有创建流程、冻结 API 与历史版本不变。回滚前需人工核对任何未决操作号，不得丢弃未知结果。
