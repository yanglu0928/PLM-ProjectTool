# SOL-01-A02：Solution 逻辑身份 Schema 0136 增量

日期：2026-10-08；来源：冻结 DM-05/SC-01/02、CR-SEQ-001、CR-SOL-001。原 Gate 2 冻结内容不改写。

|冻结资源|表|核心约束|
|---|---|---|
|SOL-02 SolutionOutline|`plm.sol_outlines`|项目 FK、创建者 FK、`(id,project)` 唯一、名称 1..500、`ACTIVE/ARCHIVED`、非负锁版本、初始批准指针 NULL|
|SOL-04 SolutionSection|`plm.sol_sections`|`(outline_id,project_id)` 复合 FK、创建者 FK、`(outline_id,section_key)` 唯一、key 1..128、`ACTIVE/ARCHIVED`、非负锁版本、初始批准指针 NULL|

迁移 `20261008_0136` 和 ORM 同构。两表带未装配 Owner 的 DML 拒绝触发器及独立 TRUNCATE 拒绝；因此它们现在仅是结构基础，不提供用户可写业务对象，也不表示任何 ApprovedVersion。后续版本表与批准指针复合 FK 尚未建立，不能绕过触发器写入正式事实。

升级在空库和含两个既有项目/用户的库上验证；空表可降级并重升；已有 Solution 记录时降级失败关闭，历史需单独迁移而不可删除。隔离测试中仅为了验证数据库自身 FK/唯一/Check，临时禁用这两个 Owner 触发器，测试后恢复；该做法不属于生产命令。Alembic `check` 三次均无新操作；全量后端 `3261 passed, 3 skipped, 4815 subtests passed`。已有 pgvector 索引表达式及生成列默认值比较警告不属于本增量，未把警告写成全局 Schema 质量结论。

无公开 API、权限、AI 外发或客户数据变化。兼容性：旧运行接口不变；升级须按正常 Alembic 线性版本执行。回滚仅在两表均为空时允许。开发 wheel 本项因当前 Python 构建环境缺组件未验，不替代未来发行包测试。后续 A03 负责真实不可变版本持久层，身份写/读及 Review、Trace、Workflow 另项验收。Gate 3 和 Solution Owner 保持未完成。
