# CR-AUD-005：后台候选竞争与异常来源隔离

日期：2026-09-27；状态：IN_PROGRESS / P02_LOCK_SKIP_INTERNAL_PASS / P03_SOURCE_ISOLATION_PENDING；持续授权：AI自主执行规则V1.1，用户最新允许兼容偏差先记录后实施，不待逐项批准。来源：P06-P13-P01真实PG证据，原冻结64cdf09与CR-AUD-004历史保留，Gate未通过。

## 冲突/证据

原无锁单hint→Audit Root锁→Jobs完整pair锁→claim_target SKIP LOCKED。完整pair已FOR UPDATE等待队首，因此后置SKIP LOCKED不能避开竞争。真实临时PG锁优先队首使55P03中止，六表无写，正常第二任务仍PENDING。合成队首payload损坏同样中止/六表无写；恢复后原组合能发布双方。验收脚本validation/aud-p06-p13-queue-isolation/verify.py只证明缺陷，不是公平验收。

## 比较与选择

- 不选：增加超时/无限重试，同一队首依旧阻塞；单过滤UUID，也不能处理Root/pair不一致。
- 不选：自动删除、标FAILED或重写坏来源，缺原授权链不可猜终态；新增消息队列/缓存违背栈。
- 选择最小分段实施：P13-P02新增Jobs专属**只锁不写**候选reservation，SKIP LOCKED在Audit/完整pair核验前发生，保原get_created/get_accepted/find_export/identity及最终claim核验、同UOWcommit和确认丢失恢复。候选锁不授正文或mutation权限。普通无锁peek兼容保留，不静默改其语义。
- P13-P03另做有界候选游标/明确SOURCE_REJECTED分类隔离：完整Root不存在/确定不一致与DB断线、SystemActor失效、死锁、commit确认异常分开；后者必须失败关闭/原恢复，不可吞掉。对坏源不改变Job/Lease/Audit或重写权威源，仅技术调度向后推进，提供最小安全诊断。不得依靠无限增长本地排除集、静默改变业务优先级或把IDLE称全队列空。游标和错误DTO具体边界须先记录后实施。

## 差异、风险、迁移/回滚

候选reservation改变内部锁顺序，可能与既有Audit→Jobs路径产生死锁；保真实40P01有界重试，并验证独立Supervisor并发、不重复Claim、锁超时/断线不可猜成功。所有业务权限/来源签名/结果证明/既有API与Scope不变，不在本CR改Schema或依赖。若后续需持久隔离字段/API，另登记Schema/API影响及Migration计划后实施。

无生产Migration；回滚撤新增内部Port/调度扩展，保历史提交与原坏源，不以回滚恢复作为已修复。新旧并发的事务互斥与死锁恢复要实际验证；候选锁事务使用现有Worker lock/statement/transaction limits，文件I/O仍在UOW外。

## 验收计划/尚未完成

锁住队首时第二任务仍能被另一实际Worker领取/发布且队首无Attempt；释放后队首发布；双Scope、两Worker竞争、真实deadlock/rollback/commit丢失恢复回归。坏payload/缺Root/错pair/正常任务混排、持续循环/有界内存/不隐瞒故障与停止行为验证。全局公平不凭局部测试声称，需明确负载/优先级语义。P13-P02/P03均未实施，完整Scope/Gate/正式材料/发行仍待。

P13-P02更新：已先记录后增加独立reserve_next，旧peek无锁保留；真实双Scope锁住优先head时后续正常发布/首无Attempt，两个只锁UOW候选不同且六表无写；1116通过/2跳过、原双Scope单claim竞争/到期/回滚/确认恢复及wheel通过。新版反向锁序真实40P01未制造，P03坏源、全局公平仍待，CR不关闭，前文未实施为原计划历史状态。
