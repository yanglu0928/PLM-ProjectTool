# Schema0092：Capability Draft Version Owner 增量

日期：2026-10-05

Revision：`20261005_0092`；前序：`20261005_0091`

## 目的

为冻结`CAP_VERSION_CREATE`的条件写控制开放最小数据库边界。Schema0091原守卫禁止Baseline任何UPDATE，导致创建子Version无法推进Baseline ETag；若继续接受永久`v0`会虚假满足并发控制。0092只允许在Baseline所有业务元数据、状态、来源集合、正式指针和创建事实完全不变时，将`lock_version`精确加一并记录`updated_by/updated_at`。

BaselineVersion仍只允许无Review引用的DRAFT INSERT；Version、Item、DocumentRef、EvidenceRef继续禁止UPDATE/DELETE/TRUNCATE。APPROVED、Review、正式指针、Baseline状态和来源集合转换均未开放。

## 升级、降级与回滚

升级仅替换`plm.guard_capability_foundation()`，无列、表、索引、数据或公开API变化。应用Owner在同一事务锁定Baseline、校验预期ETag、写完整不可变Version聚合并推进一次锁版本；Schema0091 deferred完整性验证继续执行。

没有发生锁版本推进时可在线降回0091；存在`lock_version<>0`或`updated_by`的Capability历史时拒绝降级并要求向前修复。离线降级始终关闭。应用回滚可停止新Version Owner，但不得删除Version、Item、来源、Audit或收据历史。
