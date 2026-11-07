# OUT-01-A01-P29 编码前检查：Output 原子启动状态推进

- 日期：2026-11-05
- Phase/WBS：Phase 2 Platform Core / OUT-01-A01-P29
- 结果：PASS_WITH_LIMITATION，可编码；不接入实际Worker
- Change Request：CR-OUT-025

## 检查项

- 已确认Output模型具有GENERATING/current_execution_ref/lock_version，OutputRequest取消路径证明Output与Jobs可共享同一UnitOfWork。
- P28 JobLeaseRepository提供事务内check_output_claim；本任务调用Repository proof port，不调用会自开事务的JobLeaseService，防止check与状态写入被拆开。
- Audit SYSTEM事件需要独立actor_id及original_actor_id。实现将要求调用组合提供非HTTP输入的system_actor_id，并以请求者为original_actor_id；不会把请求者标成worker。真实受控服务账号仍属后续装配前置。
- 本WBS只在lease当前有效、Output Job精确匹配、请求仍QUEUED、snapshot/request/project绑定一致时，同事务写GENERATING和execution ref/lock_version并写Audit；失败完整回滚。提交后不产生副作用、不启动worker。
- 幂等仅允许同一Job/current_execution_ref的重复启动回执；其他执行或旧fencing token拒绝。
- 无Schema/API/Migration/default app挂载；不执行插件/渲染或生成文件。
- 验证计划：Unit正负用例；GitHub hosted D盘PG18正向、错worker/token、冲突和Audit失败回滚；后端回归。P25真实HTTP/Edge的0xC0000135保持独立阻塞。
- 结论：范围、事务、身份归属、回滚和云端验收已明确，可编码，范围仅内部状态Owner。

