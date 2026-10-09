# CR-SOL-017：OutlineVersion 创建首响与受限写 Guard

日期：2026-10-09。状态：实施前登记；依据 `CR-EXEC-001` 持续授权执行，Gate2 冻结提交 `64cdf09` 不回写。TraceLink：Gate2 DM-05/API-04 → CR-SOL-002/0154 → SOL-03-A04 现时证明 → 本 CR → OutlineVersion Owner/Guard → Gate3。

## 来源、冲突与证据

冻结 `SOL_OUTLINE_VERSION_CREATE` 要求本项目 ProjectManager/ImplementationMember 对有序稳定 Section、当前批准 RequirementVersion、当前 ELIGIBLE ReferenceVersion 以及缺失/冲突声明创建 201 DRAFT。现有 `0137/0154` 四张表的行级 Guard 无条件拒绝所有 DML，尚无不可变首次创建响应；仅靠通用幂等收据重读可变版本行，不能保证重放返回首次 201。直接去掉 Guard 会让数据库用户插入不完整/伪批准历史，不能证明引用计数闭合或防止重写。Section/Requirement/Reference 现时证明端口已于 `SOL-03-A04-P02/P03-P02` 完成，但未接 Owner。

## 方案比较与选择

- 不选直接删除触发器、生产使用 `session_replication_role=replica` 或客户端可设置的自定义 GUC：会使绕过入口不可审计，无法保证闭合。
- 不选只存通用幂等收据、从当前版本行重建首次响应：版本状态/后续 Review 会变，重放不是原 201。
- 选择分两步：先线性迁移新增不可变 `sol_outline_version_create_results`，以同 Outline/Project/Version 复合 FK、字段/计数与时间约束保存首次 DRAFT 响应，默认 Guard 全拒、无公开写；再由独立 Owner/Guard 任务改为 INSERT-only 受限写，SQL 验根 ACTIVE、版本号/前驱、四张表有序计数/固定身份与结果闭合，UPDATE/DELETE/TRUNCATE 永拒。Owner 在同事务先授权、锁当前输入、持久收据，再插版本/关联/结果/Audit 并提交；失败全部回滚。确认 `0154` 的 PROJECT/GLOBAL 来源复合约束保持不变。

## 差异、影响、迁移/回滚与验证计划

相对冻结 SC-01/02，这是正式创建协议所需的后续增量实现，不改 `/api/v1` 路径/角色、Scope、数据含义或既有历史。`0155` 仅加空首响表/ORM/封闭 Guard，既有库无需回填；历史 `0137/0154` 仍保留。空库与有 Project/Section/Reference/Requirement 身份的库均验证 up/down/re-up 和 Alembic drift，直接 INSERT/UPDATE/DELETE/TRUNCATE 拒绝，跨 Outline/Project 外键及摘要/计数负例。若新表有行，down 拒降；不丢历史。后续开放 Guard 的迁移必须另证插入链、首响闭合、直接伪造/不完整集合、并发同 Key、资格撤回、Audit 故障回滚、权限/License 与全量回归；有历史时不得降级删除。

回滚优先保持或恢复写入口关闭；未写数据时可降级独立迁移。客户数据、Secret、真实外部 AI 不参与此 CR。首响 Schema 完成不等于 Owner 或 API PASS，Gate3 继续 BLOCKED。

## P03-P03-P01 实施记录

2026-10-09 线性 `0155` 已新增首响 ORM/表、复合 FK/字段约束及独立全拒 Guard，不开放四张版本/引用表写。Win11 隔离 PG18.6 空库与已有身份库升降重升、drift、直接写、约束负例及历史拒降退出 0；后端全量最终结果见版本说明。后续必须先有 Owner 命令合同、原子持久/收据/Audit 和受限 Guard 的独立证据，不能借此宣称目录版本可创建。
