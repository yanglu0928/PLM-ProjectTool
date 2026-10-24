# SOL-01-A13-P01：GLOBAL Reference Revise 人工脱敏确认整合前置核查

日期：2026-10-09。结果：`SOL_01_A13_P01_GLOBAL_REVISE_PRECHECK_PASS`；仅静态合同/现有前端流程对账，GLOBAL 修订页面未实现。

## 编码前检查

- Phase/WBS：Phase 2 Platform Core / SOL-01-A13-P01；输入冻结 API-04、CR-SOL-013/015、A07～A12-P03。GLOBAL Revise 后端 Owner/HTTP/Windows 与 A11 客户端已有合成 PG 证据；前端需人工脱敏确认。
- 模块/实体/API/权限：GLOBAL Reference 当前详情/修订；现有 `GlobalReferenceSourcePickerView` 的多证据来源、预览、逐项原文核查、人工确认和可选撤回；仅 DeploymentAdmin。无 Schema/Migration、后端、依赖或冻结 API 变化。
- 验收：修订入口有明确目标 ID/当前版本/ETag；新来源由管理员重新选择、预览并逐项打开/确认，确认指纹与当前输入一致且未过期，写前重核当前根与来源；原 body/If-Match/Key 锁定恢复；历史 201 与当前 GET 分离；测试/Edge/隔离 PG 另片验证。
- 风险：现有选择器只面向新建，全局 `createPendingKey` 与创建结果不能当修订记录；旧确认可能已撤回或来源改变，不能把它当当前事实。服务端虽在写事务重新证明确认，UI 仍必须显式区分“新建”与“修订”并避免跨目标恢复。

## 方案与顺序

现有 GLOBAL Source Picker 已实现“至少两条 Evidence→固定 DocumentVersion 集合→预览指纹→每项打开原文并勾选→本人确认→写前重新读取 viewer/当前资格及 preview 指纹”。为修订新增目标绑定路由与独立 pending storage（Actor+ReferenceId+原 body/ETag/Key）；先 GET 当前 GLOBAL Reference，页面独立显示基准版本与新选来源，确认成功后仅以新选择/新确认调用 A11 `ReferenceReviseClient`。不把创建名称/创建 pending key 混入修订；保留现有新建流程语义。若服务端返回历史首次 201，必须再 GET 当前根后分栏展示，不自动认为旧 ETag 仍当前。

A13-P02 实施页面/路由与合同测试；A13-P03 Win11 Edge/隔离 PG 验收；A14 汇总双 Scope 权限/来源/回执边界。此项静态核查不关闭 GLOBAL UI、浏览器、正式目标账户/20 并发/Server2025、Gate3/UAT/发行；Debian13 实机依用户指令暂跳过。
