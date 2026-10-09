# SOL-01-A12-P01：PROJECT Reference Revise 来源选择前置核查

日期：2026-10-09。结果：`SOL_01_A12_P01_PROJECT_REVISE_UI_PRECHECK_PASS`；仅静态合同/现有客户端对账，页面未实现。

## 编码前检查

- Phase/WBS：Phase 2 Platform Core / SOL-01-A12-P01；Gate2 API-04、CR-SOL-013/015、A07～A11 客户端已就绪。
- 模块/实体/API/权限：PROJECT Reference 当前详情、Document 列表/版本、Evidence 列表/详情及资格、Revise 前端页；PROJECT_MANAGER 或 IMPLEMENTATION_MEMBER 才提交，其他成员只读。冻结五字段 POST 不变，无 Schema/Migration/依赖变化。
- 验收：有明确名称与固定版本的文档候选，证据可选且归属同项目；重核当前根 ETag 和已选来源；首次/历史结果与当前详情分离；未知结果锁定原 body/If-Match/Key；路由/页面/全量测试及 Win11 Edge/隔离 PG 独立验收。
- 风险：PROJECT 服务端 `prove_sources` 要求 1～100 个文档版本、0～500 条证据；仅复用 GLOBAL 至少两条 Evidence 的选择器会漏掉合法无 Evidence 的场景。Document 的最新指针和 Evidence 的列表资格均不是提交时证明，实际服务端仍必须重新证明来源。

## 方案与顺序

现有 `DocumentReadClient.list/listVersions/getVersion` 可提供受权固定文档候选，限定活动文档及允许的四类；`EvidenceListClient`、`EvidenceViewerClient`、`EvidenceEligibilityClient.current` 提供可选证据和原文定位，选择时须核对同项目文档/版本。选择顺序进入冻结五字段请求；不暴露自由 UUID 输入。页面从新的 Reference GET 读取当前强 ETag，提交前再次 GET 并核对根/版本/ETag，业务来源差异由用户界面清楚展示。未知结果仅保留原操作并阻止新键，不能依据历史 201 宣称当前状态。

A12-P02 实施候选选择/受控修订页面与测试；A12-P03 做 Win11 Edge/隔离 PG PROJECT 验收；A13 接 GLOBAL 新脱敏确认，A14 汇总双 Scope 边界。此项静态核查不关闭 UI、浏览器、正式目标账户/20 并发/Server2025、Gate3/UAT/发行；Debian13 实机依用户指令暂跳过。
