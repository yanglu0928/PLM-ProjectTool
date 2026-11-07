# CR-EXEC-051：PLG-03-A05 PluginExecution 首次 Admission Owner

- 日期：2026-11-07
- Phase/WBS：Phase 2 Platform Core / PLG-03-A05
- 状态：编码前检查完成，待实现与 Hosted PG18 验收
- 基线：ADR-005、CR-PLG-014、CR-EXEC-046/048/049/050；冻结 Jobs/Output/Plugin/Audit Application Contract。
- 类型：在冻结 PluginExecution Schema 上增加内部 Owner；不改外部 API、Schema、Migration 或生产 composition。

## 编码前检查

```text
当前Phase：Phase 2 Platform Core
当前WBS：PLG-03-A05 PluginExecution 首次 Admission Owner
输入基线：CR-PLG-014 PluginExecution schema；JobLeaseService与OutputJobExecutionAdmissionOwner transaction-scoped入口（CR-EXEC-050）；PluginOperationCapabilityReader；AuditService
前置任务：PLG-03-A01/A02 PASS_SCOPE_LIMITED；A03 PASS_WITH_LIMITATION；A04 PASS_SCOPE_LIMITED（Backend 4,099 tests/wheel）
涉及模块：Plugin application/infrastructure；Jobs/Output/Audit Application interfaces；现有PluginExecution ORM/Migration。
涉及实体：PluginExecution root、state event、Job/OutputRequest/ContextSnapshot、PluginInstallation/Package/Manifest Operation。
涉及API：无。
涉及权限：当前Job worker_ref/fencing、Output QUEUED/Project绑定与trusted/enabled capability必须在同一事务复核；DB guard仅经owner GUC打开；无默认Worker挂载。
验收标准：仅创建初始PENDING记录；相同同一Job重放幂等；过期/错误fencing、错误Project/Job/Context、非Output Job、缺失/未启用/不可信插件均拒绝且零持久化；Execution root、初态事件、Audit同事务；无API/Schema/Migration、ProcessHost调用或生产Worker接线；Hosted Windows D盘合成PG18验证和后端全量/wheel通过。
风险：重复执行/重试尝试语义需要Jobs owner证明；不可猜测系统账号或测试签名。正式Publisher keyring为空，真实Production执行仍关闭。
```

## 证据与决定

- Jobs Repository 已提供带行锁的 `check_output_claim(transaction,...)`；CR-EXEC-050 新增的 Jobs/Application 与 Output/Application transaction-scoped 入口可在一项 UoW 内复用，无需跨模块直调 Repository。
- Output admission 重验请求/上下文指纹及当前 Plugin capability。Plugin capability 目前只对 Output 暴露最小结果；PluginExecution 写入必须同时固定安装ID、包ID和插件ID，故 A05 增加Plugin内部 target identity投影并与当前 capability检查使用同一事务/安装行锁。
- Migration 已有 `plm.plugin_execution_owner_write` transaction-local GUC；A05 由单一 Plugin repository 在同一事务打开、插入 PENDING root/event。Append-only trigger 保持关闭DELETE/UPDATE child。
- 审计上下文没有已验证的受控Worker主体映射；A05使用Audit schema允许的 `UNRESOLVED` actor明示缺失主体，不伪造服务账号。以后有正式Worker身份来源时由单独WBS替换。
- `plg_executions` 对 Job 有唯一约束；为避免错误假定重试恢复，本WBS只接受首次 attempt_no=1，并以 Job ID 做幂等键。attempt>1拒绝，重试恢复单独登记后续WBS。当前未挂Worker，因此不改变现有运行行为。

## 方案、回滚与验证

1. 同一UoW先用 transaction-scoped Job check锁定当前 fencing；调用 Output admission；在相同 transaction取得并锁定 Plugin target identity；校验命令全部绑定后再由 Plugin repo打开owner GUC并创建 root、PENDING event及Audit。
2. 对同Job replay锁定并比较不可变绑定；完全相同则返回既有结果且不重复Audit/事件；不一致拒绝。
3. 仅合成PG18数据。回滚为删除Owner/Repository和测试代码，不改Schema数据；当前无生产调用者。
4. 验收包括 Hosted PG18 正/反/幂等/Audit rollback/owner guard以及后端全量/wheel。所有拟提交内容提交前 Secret scan 0命中。
5. 正式信任为空期间不运行实际插件，不接 Production Output/Worker；Gate/Pilot/Release不因本WBS改变。

## 实施前发现的低风险文档偏差

CR-EXEC-050代码提交后复核发现 `JobLeaseService` 类级 docstring 仍写“每个方法均自行拥有事务”，与新加 `check_output_claim_in_transaction` 不一致。没有行为影响；将在A05同一提交组把描述改为“事务包装/transaction-scoped两类接口”，由 Hosted 全量回归覆盖。
