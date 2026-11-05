# CR-OUT-025：Output 生成启动的原子状态推进与审计

- 日期：2026-11-05
- 来源：P28活动lease proof完成后，补齐Output Worker真正开始副作用前的队列状态推进
- 阶段/WBS：Phase 2 Platform Core / OUT-01-A01-P29
- 类型：Output内部Owner + Jobs当前lease proof同事务组合；不改Schema/Migration/API/default composition
- 状态：编码前检查 PASS_WITH_LIMITATION，可实施

## 现状/决策

- OutputRequest已有QUEUED、GENERATING状态、job_ref、context_snapshot_id、current_execution_ref和lock_version；没有启动生成的Owner。
- P28 JobLeaseRepository.check_output_claim只读核验活动Output lease，在同一transaction里可直接被调用；JobLeaseService包装会开自己的UOW，不能用于本次跨Owner原子动作。
- 取消Owner已示范Output与Jobs共享一个caller UOW。P29采用相同形状：Output Owner在单一UOW中先由Jobs专属proof Port核验job/worker/fencing/attempt/DB到期，再锁定并核对OutputRequest绑定与QUEUED状态，写GENERATING/current_execution_ref/lock_version并追加AuditEvent；任一失败整体回滚。
- AuditEvent对SYSTEM要求actor_id和original_actor_id。Owner将要求服务组合显式注入server-controlled system_actor_id，original_actor_id取已存requester；不接受HTTP/作业payload指定Actor，不以requester冒充worker。当前没有真实Output Worker/受控服务账户，故Owner只作为内部能力，不自动挂载或执行副作用。
- 命令携带排队request与snapshot refs，须精确匹配Job payload、request绑定和当前claim；相同execution idempotent replay返回当前GENERATING结果，错token/错request拒绝。完成文件输出与最终SUCCEEDED状态不在本WBS。
- 不得生成文件、启动插件、运行外部调用；不改正式服务账户/Vault、Publisher信任或安装包。

## 风险/恢复/验证

- 风险：UOW提交后实际Worker副作用仍可能因租约过期/撤销而不能开始；副作用边界必须再次proof/fencing，不能把GENERATING状态视为授权。
- 回滚：撤回新Owner/Repository/测试即可；事务回滚保证无部分Job/Output状态。
- 验证：定向unittest；Hosted PG18验证正确绑定原子转GENERATING、系统审计原子写入，错worker/token/已变更状态无写入，audit注入失败Job/Output两边回滚；D盘全量云端验收。
- 用户本机/C盘不运行代码；无客户数据或正式密钥外发。
