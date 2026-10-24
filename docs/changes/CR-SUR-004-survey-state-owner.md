# CR-SUR-004：Survey metadata 与归档状态 Owner

日期：2026-10-06。状态：依据 `CR-EXEC-001` 持续授权批准实施。Gate 2 原冻结提交 `64cdf09` 与 Migration 0105 保留，不追写历史。

## 来源与冲突

冻结 API-04 已定义 `SURVEY_PATCH` 与 `SURVEY_ARCHIVE`，但当前 Migration 0105 的 `guard_survey_definition_foundation` 只允许 Review Owner 推进正式指针和 Version 状态；任何名称变化或 `ACTIVE -> ARCHIVED` 都会被数据库拒绝。直接只写应用 Service 会形成不可执行合同，放宽通用 UPDATE 又会破坏不可变身份、Review 终态和历史保护。

## 方案比较与选择

- 方案 A：维持 0105，推迟 PATCH/ARCHIVE。冻结 Operation 无法交付，拒绝。
- 方案 B：应用绕过触发器或使用复制角色。破坏数据库最终防御，拒绝。
- 方案 C（选择）：新增向前 Migration 0106，仅开放 ACTIVE Survey 的名称单字段修改与 `ACTIVE -> ARCHIVED`；要求身份/Project/创建信息、正式指针不变，`lock_version + 1`、操作者和更新时间有效，并在数据库与仓储双层拒绝任何 IN_REVIEW Version。既有 Review Owner 路径原样保留。

## 影响、迁移与回滚

不增加表列，不修改冻结 URL/DTO、技术栈、依赖、Secret、网络或外发范围。PATCH 允许 ProjectManager/ImplementationMember，ARCHIVE 仅 ProjectManager；归档是单向历史状态，不恢复 ACTIVE、不删除 Version/Review/Audit。

0106 升级只替换共享守卫函数。无归档或 PATCH/ARCHIVE Audit 历史时可降级并恢复 0105 守卫；存在上述历史则拒绝降级，只允许向前修复或从备份恢复。应用回滚可停止装配状态 Owner，但必须保留既有业务历史。

## 验证计划

- Migration：空库 `0105 -> 0106 -> 0105 -> head`、有数据升级、Alembic drift、历史拒降。
- 数据库：合法名称修改/归档，身份、正式指针、锁版本、在审、归档后二次写与非法恢复负例。
- 应用：Session/CSRF、License、角色、Project 隔离、强 ETag、无变化、归档精确重放、Audit 失败全事务回滚。
- 回归：定向单元、Windows 11/PostgreSQL 18.6、后端全量与 wheel 内容检查。

## 实施结果

已按方案C完成Migration0106、内部状态Service/Repository、双角色PATCH/仅PM ARCHIVE授权、Audit与归档持久幂等。Windows 11/PostgreSQL 18.6完成空库升降重升、drift、有历史正反例及历史拒降；定向17项、后端2829项通过/3项跳过，wheel 1045 entries，SHA-256 `26980b48d6ede0efb24621d278ec8200c6ca903b372a8672ef853ce826996443`。首次全量发现Migration head测试仍固定0105，作为配套合同更正至0106后重新全量通过。
