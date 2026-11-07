# CR-EXEC-053：PLG-03-A06 PluginExecution RUNNING transition Owner

- 日期：2026-11-07
- 状态：实现与验收器已同步到功能分支；GitHub Hosted PG18/全量验收待完成，不标PASS
- 阶段/WBS：Phase 2 Platform Core / PLG-03-A06
- 基线：Gate 2冻结PluginExecution Schema/Migration 20261105_0231；PLG-03-A05 / CR-EXEC-051/052；Jobs/Audit Application contracts。
- 变更级别：在既有冻结状态模型内新增内部状态Owner，不改冻结Schema、Migration、API、默认组合或Worker/ProcessHost装配。

## 编码前检查

```text
当前Phase：Phase 2 Platform Core
当前WBS：PLG-03-A06 PluginExecution PENDING→RUNNING transition Owner
输入基线：冻结PluginExecution ORM/Migration 20261105_0231；A05 Admission Owner；JobLeaseService.check_output_claim_in_transaction；AuditService和append-only state event。
前置任务：PLG-03-A05 Hosted PG18专项PASS_SCOPE_LIMITED（run 42344966652），Backend与Wheel此前均通过。
涉及模块：Plugin application/infrastructure；Jobs/Audit仅复用调用方UoW。
涉及实体：Job/Lease claim、PluginExecution root、PluginExecutionStateEvent、Audit。
涉及API：无。
涉及权限：有效 OUTPUT_GENERATE / PROJECT / attempt 1 claim；校验Project、Job及当前worker fencing完全一致；Audit主体继续标记UNRESOLVED。
验收标准：当前lease证明、PluginExecution锁定、PENDING→RUNNING根记录、state event及Audit在同一事务；RUNNING重放无重复写；stale/mismatch/终态零写拒绝；Hosted真实PG18合成验收、后端全量及wheel通过。
风险：冻结Schema不记录execution启动时的fencing token；Owner以changed标记首个转换，changed=false不得触发执行。当前没有消费调用方，因此不接Worker/ProcessHost/实际插件；若证明当前模型不足，停止并另行记录。
```

## 实施方案、回滚和验证

- 按 Jobs lease proof → PluginExecution row lock 的顺序在同一UoW校验。仅已核实根记录与claim的job_id/project_id/attempt_no相同且状态PENDING时，短暂打开transaction-local owner GUC并将根记录转为RUNNING，更新started_at与lock_version，追加RUNNING状态事件和Audit。
- RUNNING精确重放返回changed=false且不重复写事件或Audit；终态及所有不匹配输入fail closed。
- 不增加状态、字段、Migration、API、Worker或ProcessHost接线；不生成或发布文件，不改变输出成功/失败结论。
- Hosted验收覆盖首次状态写、重放、错误/过期fencing、绑定不匹配、非PENDING拒绝、Audit失败完整回滚和DB owner guard。提交前Secret scan为0；Hosted Windows Server 2025 D盘运行合成数据。
- 回滚只删除新增Owner/Repository/测试/verifier/workflow步骤。无生产消费者及持久数据迁移，无需数据修复。

## 持续限制

真实Worker身份映射、fencing恢复/重试、SUCCEEDED/FAILED/CANCELLED终态、API、实际插件执行、正式信任及Pilot/Gate/Release均不在本WBS内，维持未完成。A08 packaged flow仍为独立阻塞，不因本任务变更或推定通过。

## 实现同步（2026-11-07）

- 新增 `execution_start.py` 事务Owner与 `execution_start_repository.py`，按Jobs租约→Execution行锁顺序校验；首次转换更新状态/started_at/lock_version，并在同一UoW追加状态事件和Audit。
- RUNNING重放返回`changed=false`，不重复事件或Audit；终态、不匹配/过期fencing与Audit异常走固定拒绝。
- 新增单元测试和 `tools/verify_plugin_execution_start_pg_cloud.py`，并新增Hosted Windows Server 2025 PG18验收Job。仅合成数据。
- 生产调用/Worker/ProcessHost均未接线；代码和新测试尚未由Hosted workflow执行，任务保持Incomplete直到取得结果。

## 实现复核发现：OutputRequest 与 Context 绑定（2026-11-07，修正前登记）

在首次 Hosted 验收开始前，单元/代码复核发现 start Repository 仅按 Job/Project/attempt 锁定 PluginExecution root；虽然生产 JobLease 会返回实际 Job claim，Owner仍应对 Execution 所保存的 OutputRequest 与 ContextSnapshot 执行显式精确绑定，避免依赖仅由 A05 建立的上游不变量。此为本 WBS 内的 fail-closed 加固，不改变冻结模型与任务边界。

- 修正：Start facts 承载并由 Owner 比对 OutputRequest/ContextSnapshot UUID；SQLAlchemy lock/update 查询均同时匹配这两个绑定；claim 必须具有且仅具有两个规范 UUID payload refs。
- 验收增加：绑定不匹配时在状态、事件及Audit写入前拒绝；PG18验收验证零状态/事件/Audit变化。
- 风险/回滚：无新增风险面及数据库变化；若新校验导致合法 A05 事实被拒绝，先根据固定错误与合成 PG18 行定位。回滚仅撤销新增绑定检查与测试。
- 该发现先记录于此，之后才修改实现；旧提交 558aad9 在该项修正/Hosted验收完成前不视为 A06 通过。

### 绑定复核修正已实施

按上述修正前记录，Owner command校验现在要求唯一且规范的OutputRequest/ContextSnapshot UUID payload refs；facts和SQL锁定/更新均再次核对两项绑定。新增单元负例与PG18零写拒绝断言。此修改与本项CR一致；尚待Hosted结果。
