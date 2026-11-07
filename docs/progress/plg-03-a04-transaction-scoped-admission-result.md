# PLG-03-A04 Jobs/Output transaction-scoped Admission 验收结果

- 日期：2026-11-07
- 结论：PASS_SCOPE_LIMITED
- Change Request：[CR-EXEC-050](../changes/CR-EXEC-050-transaction-scoped-plugin-admission.md)
- 代码提交：`b2d77789cf308e4a21aa16abea8b497a38d840c6`
- Hosted workflow：[42324011767](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42324011767)

## 变更

- Jobs Lease 新增 `check_output_claim_in_transaction`，在调用方事务内执行现有 worker/job/fencing-token 检查；既有 `check_output_claim` 仍自有 UnitOfWork 并 commit。
- Output Admission 新增 `admit_in_transaction`，在调用方事务内执行既有 OutputRequest/Context/Plugin capability 校验；既有 `admit` 保留自有 UnitOfWork 包装。
- 两个新方法均不提交/关闭调用方事务。无 API、Schema、Migration、权限、Plugin Host 或默认 Worker 变化。

## 验收

Hosted Backend 全量 4,099 tests 与开发 wheel 成功；新增单测确认同一 transaction 对象被传给各 repository/capability port，且不打开嵌套 UnitOfWork；错误输入 fail closed。Frontend/build、PG18 sidecar、parent assembly、A17 candidate、A35 job通过。

记录本结果时全链 workflow 的 P25/A08/A17集成仍运行中，因此本结果只界定 A04 自身范围，不声称 workflow 全绿。代码仅在 GitHub Hosted Windows runner 执行；本机/C盘未运行。

## 限制与下一步

本项为只读 admission application 接口重用，未持久化 PluginExecution，也未执行插件。下一项 PLG-03-A05 将先核对 PluginExecution admission owner 的单事务实现和 Hosted PG18 synthetic验收；正式 Publisher trust 为空期间继续保持 Production Output/Worker fail-closed。
