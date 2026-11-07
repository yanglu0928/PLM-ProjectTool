# CR-EXEC-050：PLG-03-A04 共享事务内的 Jobs/Output Admission 入口

- 日期：2026-11-07
- Phase/WBS：Phase 2 Platform Core / PLG-03-A04
- 状态：PASS_SCOPE_LIMITED；实现与后端Hosted全量/wheel验收完成，整条workflow仍有独立集成项运行中
- 基线：冻结 Jobs Lease 与 Output Request application contracts；CR-EXEC-049；CR-PLG-014；ADR-005。
- 类型：内部 Application Interface 可组合性调整；无外部 API、DB Schema、Migration 或信任策略变更。

## 编码前检查

```text
当前Phase：Phase 2 Platform Core
当前WBS：PLG-03-A04，共享事务内 Jobs/Output admission application入口
输入基线：JobLeaseService/JobLeaseRepositoryPort；OutputJobExecutionAdmissionOwner/RepositoryPort；CR-EXEC-049；PLG-03 execution schema
前置任务：PLG-03-A01/A02 PASS_SCOPE_LIMITED；A03 派发边界检查 PASS_WITH_LIMITATION；正式 Publisher trust 为空。
涉及模块：Jobs application；Output application；对应单元测试。
涉及实体：不改变实体。仅读取现存 Job lease、OutputRequest、OutputContext 与 Plugin capability。
涉及API：无。
涉及权限：现存 worker_ref + fencing token 与 Output owner 的拒绝规则不变；不创建 capability。
验收标准：保留现有各自管理 UnitOfWork 的公开调用；新增显式 transaction-scoped 入口，不创建/提交/回滚嵌套事务；输入/业务拒绝与后端不可用仍 fail closed；新增测试证明同一 transaction 被传入 Job repository、Output repository 与 capability reader；既有后端全量/wheel Hosted通过。
风险：若入口错误地自行 commit 或允许跨 transaction 混用，会破坏未来 Execution admission 的租约/权限原子性。故接口文档要求调用者只在传入活动事务生命周期内消费结果。
```

## 源码证据与最小调整

- `JobLeaseRepositoryPort.check_output_claim(transaction, ...)` 已支持从调用方事务检查 job id、fencing token、worker_ref 与有效租约；但 `JobLeaseService.check_output_claim(...)` 自行开启/提交 UnitOfWork，当前执行 Owner 无法通过 Jobs Application Interface 在同一事务复用该检查。
- `SqlAlchemyOutputJobAdmissionRepository.load(transaction, ...)` 和 Plugin capability reader 均接受调用方现有事务；但 `OutputJobExecutionAdmissionOwner.admit(claim)` 自行开启 UoW，所以无法在同一事务内与 Jobs 检查及未来 Execution persistence 串联。
- 该缺口可通过新增显式 `*_in_transaction` application 方法修复；原服务方法继续管理自己的事务并委托新方法，既有 API 和行为不变。此方式不跨模块直调 Repository，满足 Application Interface 边界。
- 实施顺序：先验证 transaction 类型/活动状态由下游 ports按既有方式执行；将原有核心检查搬入 transaction-scoped 方法；既有包装方法继续创建 UoW 并调用新方法；补“事务未创建/未提交、调用方 transaction 对象被原样传递、旧调用兼容、缺少/错误租约 fail-closed”单测。
- 本 WBS 不实现 PluginExecution 数据写入或状态 Owner，也不接入 ProcessHost/Production Output/Worker；这些作为下一项 PLG-03-A05 单独 precheck/实现。

## 风险、迁移/回滚、验证

- 这是只增内部应用方法和重构既有函数体的可逆变更；无需数据迁移。回滚为恢复两个原实现并删除新单测。
- 代码及单测先在拟提交整体内容上做 Secret scan，0 命中后提交。
- 仅 GitHub Hosted Windows Server 2025 D 盘验收；不在本机/C盘运行。用合成值，不执行插件或外部 API。
- 验收失败则先记录实际失败，再作最小修复；不将未通过结果标 PASS。
- 当前 Production Output/Worker、Publisher trust、Gate 3、Pilot、Release 和 Windows 11 实机结论均不改变。

## 实施与Hosted验收（2026-11-07）

- 代码提交：`b2d77789cf308e4a21aa16abea8b497a38d840c6`。
- `JobLeaseService.check_output_claim_in_transaction(transaction,...)` 执行现有 worker、job id、fencing token 校验，并把原样 transaction 传给 Jobs repository；原有 `check_output_claim(...)` 保留自有 UoW/commit 行为并委托新入口。
- `OutputJobExecutionAdmissionOwner.admit_in_transaction(transaction, claim)` 保留原绑定/指纹/capability/错误处理，完全复用调用方事务；原 `admit(claim)` 保留自有 UoW 包装并委托新入口。
- 新增测试覆盖同一 transaction 对象传递、无嵌套 UoW、非法租约和缺少 transaction 拒绝。无 DB/API/Migration 变化。
- GitHub Hosted run [42324011767](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42324011767)：Backend 4,099 tests、wheel、Frontend/build、PG18 sidecar、parent assembly、A17 candidate 与 A35 成功。记录本 CR 时 P25/A08/A17集成 job仍在运行，故整条run尚未判定。测试在Hosted环境，不在用户本机或C盘执行。
- 结论仅限内部 transaction-scoped application 接口组合性；不表示PluginExecution Owner、签名信任、Production Output/Worker、Gate、Pilot、Windows 11或Release已通过。
