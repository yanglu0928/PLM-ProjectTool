# CR-SOL-001：Solution Outline/Section 身份持久层增量

日期：2026-10-08；状态：依据 CR-EXEC-001 持续授权先记录后实施；Gate 2 冻结提交 `64cdf09` 保留。

## 来源、差异与选择

冻结 DM-05 定义 SolutionOutline、SolutionSection 逻辑身份及批准版本指针；SC-01/02 指定 `sol_outlines`、`sol_sections` 为 M-PRJ，并要求 Outline 内 `section_key` 唯一。当前运行代码及迁移没有 `sol_*` 表，无法为后续不可变章节版本建立真实项目身份。CR-SEQ-001 允许按依赖前置此最小 Owner 基础任务，而非提前宣称 Phase 8 或 Gate 3 通过。

方案一直接实现全部参考、目录、章节、专项及公开 API，会在缺少各自 Owner/Review/Evidence 证明时扩大单 WBS 风险；方案二先建立 Outline/Section 逻辑身份和项目同一性、锁版本、空批准指针，并使写入失败关闭，后续分别实现版本和受权命令。选择方案二。冻结资源、路径和业务含义不变；`ACTIVE/ARCHIVED` 状态、名称上限 500、`section_key` 上限 128 与初始拒写触发器是 SC-02 未逐列列明的实现细化，不追改原冻结文档。

## 影响、迁移、回滚与验证

- 增量 `20261008_0136` 新建两个空表及 ORM；无旧 Solution 数据可自动迁移，不触碰其他模块表、正式 `/api/v1`、权限或外发。跨项目 Section→Outline 使用复合 FK，`(outline_id,section_key)` 唯一；批准指针初始 NULL，版本表/正式化 Port 未就绪前不得填充。
- 升级须在空库与已有项目/用户数据的库上通过；降级只允许两表均为空，禁止覆盖历史。回滚代码/迁移时先停止尚未安装的 Solution Owner；一旦未来有业务记录，不得删除，必须专门制定保留数据的迁移。
- 验证 ORM/迁移约束一致性、真实 PostgreSQL 18 的空/有数据升降级、跨项目 FK/重复 key/未装配写入口与降级历史保护，后端回归与 Schema drift。任何失败不记 A02 PASS。

后续真实身份写服务需受权、幂等/Audit、同事务结果和可逆状态命令；本 CR 不授予直接 SQL 写正式业务数据或伪造客户批准。
