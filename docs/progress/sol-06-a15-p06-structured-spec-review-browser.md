# SOL-06-A15-P06：结构化专项 Reviewer Windows Edge 真实链

日期/版本：2026-10-19 / `0.1.0-dev.0`。状态：`STRUCTURED_SPEC_REVIEW_EDGE_PASS`；证明 Windows 11 上已知 Review ID 的真实浏览器决定闭环，不表示 REVIEW_LIST、正式信任、Gate 3、Pilot 或正式发行已通过。

## 编码前检查

|项目|结论|
|---|---|
|当前 Phase / WBS|Phase 2 / `SOL-06-A15-P06`|
|输入基线|A14-P09 真实送审链、A15-P04 Windows REVIEW_GET/DECIDE、A15-P05 known-ID Reviewer 页面|
|前置状态|产品代码、生产 Vue 构建和 Win11 后端链已分别通过；尚缺同一实际 Edge 会话的决定与未知结果恢复证据|
|涉及范围|一次性 loopback 验收脚本、实际 Microsoft Edge、FastAPI/Uvicorn、可弃 PostgreSQL 18.6；不修改产品代码|
|验收标准|真实送审回执；assigned reviewer；断网未知结果保留原决定/意见/Key；恢复后精确重试；终态回读；跨项目清屏；数据库唯一事实|
|风险|把 DevTools 驱动误写成内置浏览器；离线尝试换 Key；重复决定；历史同系列事实污染本次计数；把批准描述成客户确认或 UAT|

## 实施结果

- 复用 A14-P09 夹具先由实际 Edge 155 完成负责人送审并产生可追溯 Review/Round，再以独立评审人 Session 打开生产 Reviewer 页面；没有手工构造 Review 业务事实。
- 通过 Edge 网络仿真在“批准本轮”时断网，页面进入结果未知状态；`sessionStorage` 中的 Actor、Project、Review、Round、Decision、Comment 与 Idempotency-Key 均保持原值。恢复网络并明确勾选后，使用原正文和原 Key 重试，服务端只接受一次 200 决定。
- 成功后页面重新 GET，显示 APPROVED 且 `active_round=null`；切换到无权项目后旧 Review 内容清除并显示拒绝提示。
- 数据库按本次 Review/Round/Version 精确限定，确认一条 APPROVE Decision、一个对应决定回执、START/APPROVED 两条专项状态事实，以及各一条 Review 决定和专项批准 Audit。首轮因回执/Audit 查询未限定本次事实而在页面链通过后断言失败；已修正验证口径并完整重跑，不把失败尝试计为通过。

## 验证证据

- Python 与 Node 验收脚本静态检查通过。
- Windows 11 实际 Microsoft Edge `155.0.4283.62`、production Vue、FastAPI/Uvicorn、PostgreSQL `18.6` 整链退出码 0。
- `STRUCTURED_SPEC_SUBMIT_EDGE PASS`：负责人送审、201/精确重放、跨项目清屏和生产页面渲染通过。
- `STRUCTURED_SPEC_REVIEW_EDGE PASS`：assigned reviewer、断网原操作重试、APPROVED 终态回读、跨项目清屏和页面渲染通过。
- `SOL_06_A15_P06_REVIEW_BROWSER_PASS`：本次决定、幂等回执、状态结果与审计唯一事实通过；同次上游仓储、Review、Trace、来源 Owner 回放均退出 0。

## 兼容、回滚与未完成项

- 仅新增可弃验收夹具和记录；无产品代码、Migration、冻结 API、角色、License、依赖或旧数据变化。删除本夹具即可回滚，临时 Edge profile 与可弃数据库由脚本清理。
- 验收使用本机已安装的真实 Edge 引擎及 loopback 合成数据，不等同于目标服务账户、正式 CA/Vault/公钥或生产部署信任。
- 当前入口仍依赖已知 Review 回执；正式 Reviewer Inbox/任务发现需要独立 REVIEW_LIST 合同，不能以浏览器存储或手工 UUID 替代。
- 批准只证明专项评审终态，不代表实施完成、客户确认、UAT、Gate 3、Pilot 或 Release。

Next：`SOL-06-A16-P01` 对 Review Inbox/任务发现进行编码前检查，核对冻结合同、权限、分页、主题显示与现有后端能力；若需要新增或变更冻结 API，先记录 Change Request 再实施。
