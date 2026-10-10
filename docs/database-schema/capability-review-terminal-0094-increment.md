# Schema0094：Capability Review 终态正式化增量

日期：2026-10-05；WBS：`CAP-01-A04-A04`；依据：CR-CAP-001、CR-RVW-003、DEC-838/839。

Schema0094不追写0091～0093。它将Capability守卫开放为以下唯一状态路径：`DRAFT -> IN_REVIEW`、`IN_REVIEW -> APPROVED/RETURNED`、`APPROVED -> SUPERSEDED`。Review撤回在Version上收敛为`RETURNED`，精确`WITHDRAWN`事实继续由不可变Review/Round/Event历史保留。

新增每个Baseline最多一个`APPROVED` Version的部分唯一索引，以及延迟终态约束触发器。提交时必须满足GLOBAL/CAP-01 Review与Round均已终态、固定Subject Version一致；APPROVED必须成为Baseline正式指针，旧APPROVED必须在同事务变为SUPERSEDED；RETURNED/WITHDRAWN不得改变既有正式指针。Baseline每次正式化只推进一次锁版本，内容及来源字段仍不可变。

首次批准后，Version创建Owner不再要求正式指针为空，但仍要求ACTIVE Baseline、强ETag且不存在IN_REVIEW Version。因此可以保留旧正式版本的同时创建替代Draft，不能在评审期间绕过身份锁。

空终态历史可降回0093并重升；存在APPROVED/RETURNED/SUPERSEDED或正式指针时拒绝物理降级，采用向前修复或受控备份恢复。无公开API、依赖、网络或数据自动导入变化。
