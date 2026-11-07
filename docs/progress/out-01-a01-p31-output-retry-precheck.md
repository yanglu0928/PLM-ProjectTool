# OUT-01-A01-P31 编码前检查：Output 可重试失败的原子回队

- 日期：2026-11-05
- Phase/WBS：Phase 2 Platform Core / OUT-01-A01-P31
- Change Request：CR-OUT-027
- 检查结论：PASS_WITH_LIMITATION，可编码

## 编码前检查

- P30已证明不可重试失败流程、Output→Jobs锁序、共享UOW与Audit rollback。
- Jobs.retry_or_fail支持固定error_code、retryable及delay_seconds并返回RETRY_WAIT或FAILED；必须由OutputOwner在同一事务中映射状态，不能留下Generating。
- OutputRequest现有QUEUED/GENERATING/FAILED/current_execution_ref/completed_at/lock_version即可表达重试生命周期，无Schema变化。
- 新任务仅处理活动Output claim上的固定瞬时错误：固定30秒退避；Job重试时Output回QUEUED、清除execution ref且不设completed_at；attempt耗尽则Job和Output共同FAILED。
- Worker不得控制retryable或delay，不保存自由错误正文；错绑定、旧token、错worker及Audit失败都无部分写入。
- 不执行插件/渲染/文件/HTTP，不改默认平台组合及信任根。
- hosted PG18 verifier运行于已通过的同run父包PG smoke路径；覆盖重试与耗尽两个分支及Audit rollback，随后跑后端全量/wheel及云端全链。只在GitHub hosted D盘，不运行用户本机/C盘。
