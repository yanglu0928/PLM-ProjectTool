# SOL-03-A06-P02：OutlineVersion 现时验证事实与报告合同

日期/版本：2026-10-23 / `0.1.0-dev.0`。状态：纯合同独立验收通过；现时证明 Owner 尚未装配。

|项目|结论|
|---|---|
|当前 Phase / WBS|Phase 2 / `SOL-03-A06-P02`|
|输入基线|冻结 API-04 `SOL_OUTLINE_VERSION_VALIDATE` 的 order/source/coverage report、SOL-03-A06-P01 前置核查、既有 Section/StructuredSpec 验证合同|
|前置任务|OutlineVersion 固定历史 DTO、DRAFT 创建/读取和统一 Audit/幂等合同已存在；真实现时来源 Owner 尚未实现|
|涉及模块/实体|solution.application 纯合同与单元测试；不更改数据库或前端|
|API/权限|本片不挂载 HTTP；后续 Owner 负责 Session、CSRF、License、项目成员、Audit 和持久幂等|
|验收标准|命令身份/Key 校验、三维事实默认 UNAVAILABLE、报告结论失败关闭、固定版本摘要绑定、审计原因精确反读、历史报告不得冒充当前资格|
|风险|把未证明事实默认为 PASS、把 `valid` 与 `ready_for_review` 混淆、可变/客户正文落入 Audit 原因、旧结果被用于现时送审|

选择独立三维 `order/source/coverage`，对应冻结 API 的报告语义；本片只定义严格的数据合同和纯结论，不生成这些事实。现时证明 Owner 后续同事务生成事实；送审/批准时必须重新计算，不读取历史 VALIDATE 审计作资格。无冻结 API、Schema、权限、License、依赖变更。

## 独立验收

- 命令固定项目/Outline/版本与原幂等 Key，排除 Session/CSRF/Key 的日志表示；摘要绑定固定身份但不随 Trace 或操作号变化。
- 三维缺证明默认 `UNAVAILABLE`；任一 `FAIL/UNAVAILABLE` 均使 `valid=false` 和 `ready_for_review=false`；全部 `PASS` 也仅在 DRAFT 显示 ready，不代表已批准。
- 固定快照检查版本号、状态、32 字节摘要及章节/需求/参考数量；审计原因只含三维 P/F/U，不含正文，反读拒绝未知/截断/错类原因；手工伪造报告结论或无时区时间失败关闭。
- 定向合同及既有 Section 合同共 54 项通过；Windows 11 后端完整回归 `3875 passed, 3 skipped, 6023 subtests passed`，退出码 0；`git diff --check`通过。无数据库迁移或运行路由变化。

剩余：真实现时证明、授权/Audit/幂等持久 Owner、冻结 HTTP/Windows、Review 和实际 PG/浏览器均未在本片验收。
