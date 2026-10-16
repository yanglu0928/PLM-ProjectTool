# Schema0095：Capability 状态与元数据 Owner 增量

日期：2026-10-05；WBS：`CAP-01-A05-A03`；依据：CR-CAP-002、DEC-840/842。

Schema0095不追写0094，也不增加字段或Root。Baseline守卫新增两条冻结命令路径：ACTIVE状态下名称/说明单次修改，以及ACTIVE→ARCHIVED；两者均要求`updated_by`、时间和`lock_version+1`，编码、来源、创建事实与正式指针不可借机改写。既有Version创建/Review正式化所需的锁推进和正式指针切换保持兼容。

Version守卫在既有Review状态机之外只开放`DRAFT/APPROVED/RETURNED/SUPERSEDED -> RESTRICTED`，IN_REVIEW必须先撤回或退回。延迟完整性改为精确校验每个Baseline的APPROVED数量与正式指针：零APPROVED必须无指针，一个APPROVED必须由指针精确引用。限制当前APPROVED时，Version转RESTRICTED、指针清空和Baseline锁推进必须同事务；历史项目精确引用不删除。

限制原因写入不可变Capability Audit的受控reason code，不向冻结Version增加可变字段。ARCHIVED是Baseline终态写栅栏，后续Version限制也拒绝，避免推进Baseline锁而破坏Archive首次响应；需限制的Version先处理再归档。Archive/Restrict的应用收据固定首次成功并阻止重复Audit；Patch以强ETag串行化且拒绝无变化写入。

无状态Owner历史时可恢复0094函数并重升；存在ARCHIVED/RESTRICTED或三个新Audit动作时拒绝物理降级，采用停止新命令、向前修复或受控备份恢复。无依赖、网络、Secret、外发或客户数据变化。
