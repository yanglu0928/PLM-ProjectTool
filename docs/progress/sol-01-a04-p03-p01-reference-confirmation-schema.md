# SOL-01-A04-P03-P01：ReferenceVersion 来源与人工确认 Schema 绑定

日期：2026-10-08；结果：`REFERENCE_CONFIRMATION_BINDING_SCHEMA_PASS`，仅 Schema，不开放 Reference Owner。

```text
当前 Phase：Phase 2
当前 WBS：SOL-01-A04-P03-P01
输入基线：冻结 DM-05/API-04、CR-SOL-004/005/006/007，0139/0140～0142
前置：来源资格、GLOBAL 人工确认记录/Proof/撤销及内部 PG 文件组合通过
涉及模块/实体：Solution ReferenceVersion 与确认账本 ORM/迁移
API/权限：无公开 API 或角色变更；0139 四表 Owner 仍拒写
验收：来源指纹与确认复合 FK、Scope 不变量、空/有数据升降策略、drift 与全量回归
风险：Schema 只保证静态绑定，当前来源/确认有效性必须由后续 Owner 复验
```

版本正文摘要 `content_fingerprint` 不等于固定来源集合摘要。0143 为 ReferenceVersion 另加非空 32 字节 `source_fingerprint` 和仅 GLOBAL 必填的 `deidentification_confirmation_id`；`(确认 ID, 来源指纹)` 复合 FK 阻止指向不同来源的人工确认。PROJECT 版本必须无确认 ID，但同样固定其来源指纹。确认表唯一键不改变既有确认历史。

旧 ReferenceVersion 缺可信来源指纹，迁移前若有任何该表行则拒升且原行保留，不伪造填充；其他已有项目/文档数据可升级。空 ReferenceVersion 表可降至0142并重升；非空拒降以防绑定丢失。离线 SQL 同样生成数据库执行时历史守卫。Windows11 隔离 PG18.6 历史迁移回归、正确 GLOBAL/PROJECT、错指纹/NULL/跨 Scope/长度拒绝、已填版本拒降、旧版本拒升、重升与 Alembic drift 通过；后端全量3298通过、3跳过、4824子例。

无公开 API、自动人工确认或客户数据迁移。0139 的 Reference 表写入仍关闭；正式 Owner 必须同事务复验固定 Document/Evidence、当前管理员/项目角色、确认未过期/撤销和 Audit/幂等后才可写。TraceLink：CR-SOL-007 → DEC-20261008-1110 → ORM/0143 → 隔离 PG 证据 → 后续 Reference Owner。
