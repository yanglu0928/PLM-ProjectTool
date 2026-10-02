# CR-AI-013：Egress Preview/Authorization 正式授权聚合

日期：2026-10-03；状态：依 V1.1 持续授权登记，0068 已实施，0069 及应用切片待继续；关联冻结 API-03 `EGRESS_PREVIEW_CREATE/GET/AUTHORIZE/REVOKE`、DM-04、SC-01/02、CR-AI-011/012；原 Gate 2 冻结提交 `64cdf09` 不改。WBS `AI-04-A04-P01～P02`。

缺口与证据：冻结 API 要求每个逻辑外发操作先生成不发送数据的 EgressPreview，再由 ProjectManager/CustomerManager 且满足部署策略的主体显式授权，并支持撤销。当前仓库只有 AITask 内不可变消费快照，无 Preview/Authorization 权威根、来源明细、批准或撤销历史、首次幂等结果。SC-01 的 AI-04 物理映射也仅列 Task/Invocation owned tables。消费快照不能反向冒充批准来源。

方案比较：A 以一张可变表同时充当 Preview、Authorization 和 Task Snapshot，会改写历史并混淆权威源/消费证据，否决。B 仅在应用内存中授权，无法审计、重放或跨进程验证，否决。C 新增 AI-owned Preview Root+不可变 SourceRef，Authorization Root 引用 Preview 并保存批准事实，撤销以状态与不可变事件/首次结果记录；Task 创建由 Owner 锁定 Authorization 并复制最小快照，选择C。

聚合边界：Preview 存 purpose/operation type、Provider/Config/Model/region、数据类别、不可变源引用、最小正文/查询范围的受控策略引用、记录/字节/Token/重试上限、payload/source fingerprint、有效期和风险代码，不存正文/Key。Authorization 只能从未过期 Preview 创建，只能缩小不能扩大，首版一 Preview 最多一个 Authorization；核心批准事实不可变，状态仅 `AUTHORIZED→REVOKED`。历史快照保留，Worker 未开始/下一批次重读当前状态。

权限：Preview Create 允许 ProjectManager/ImplementationMember/CustomerManager，Get 允许同项目受权成员；Authorize 仅 ProjectManager/CustomerManager 并额外通过可注入部署策略；Revoke 仅原批准者或当前 ProjectManager/CustomerManager。这些Operation需加入Project授权矩阵，不以AI Task权限替代。

迁移/回滚：以0068建 Preview/SourceRef，0069建 Authorization/撤销历史/首次结果；均为增量表。空表可物理降级，有历史后拒绝降级并采用向前修复或受控备份恢复。公开路由持续保持404，直到生产策略与信任源组合验收。

验证与切片：P02 只实现0068 Preview/SourceRef Schema与PG18升降/历史/不可变/跨项目/指纹边界；P03 实现0069 Authorization/撤销历史；P04～P06 分别实现Preview内部创建/读取、Authorize/Revoke与Task Owner投影；之后再做可选HTTP和Windows显式组合。无客户数据外发。

P02结果：已实现ORM/Migration0068。Preview 与 SourceRef 不可改写，Provider/Config/Region 及 AVAILABLE Model 由 PostgreSQL 守卫核验，集合项和语义来源必须唯一，Scope/Project、UUID、指纹、定量上限和时间窗口均失败关闭。Win11/PG18.6 空库升降重升、drift、负例与非空拒降 PASS；后端2111运行/3跳过、wheel PASS。无生产迁移、HTTP或外发。
