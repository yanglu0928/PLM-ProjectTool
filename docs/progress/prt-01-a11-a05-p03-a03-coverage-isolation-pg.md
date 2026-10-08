# PRT-01-A11-A05-P03-A03-P01/P02：Coverage与项目隔离负例

日期：2026-10-08。状态：`PRT_01_A11_A05_P03_A03_PARTIAL_COVERAGE_HTTP_PG_PASS`、`PRT_01_A11_A05_P03_A03_ILLUSTRATES_COVERAGE_HTTP_PG_PASS`、`PRT_01_A11_A05_P03_A03_ISOLATION_HTTP_PG_PASS`。范围为Windows11隔离PG18.6/pgvector及合成Project/Actor/文件，不代表A05或Gate3整体完成。

编码前检查：Phase 2与Gate 2冻结合同不变；A05-P01/P02/P03-A01/A02已证明物理文件、全NOT_REQUIRED、批准原型单需求及混合范围。当前只验证Link目的/覆盖和跨项目/授权失效，不改变正式Owner、Schema、API或生产入口。依据`DEC-20261008-1077`，完整覆盖修正经正式Link服务，不手工回填状态；跨项目测试各用独立合成PM，暂停PM仅限本轮随机库。

- 部分Coverage：一条已批准Requirement包含两项验收标准；VALIDATES Link覆盖第一项，第二项注明未覆盖理由。Scope资格200但Coverage资格409；正式Supersede补齐后两项Checklist PASS，进入SOLUTION。
- 不计数目的：ILLUSTRATES Link即使覆盖字段列出全部验收标准，Scope可预览但Coverage资格409；正式新增VALIDATES Link后才PASS并推进。
- 跨项目与撤权：第二项目经理在其项目有效授权，但指向第一项目Requirement/PrototypeVersion的Link创建返回`RESOURCE_NOT_FOUND`且第二项目Link数0；第一项目PM被临时暂停后，资格GET及Checklist写返回404且Prototype记录数0，恢复后可正常推进。

三项隔离运行均迁移到当前head、Alembic drift无新增操作，停机后无本轮PG监听或Temp目录。既有向量表达式/计算默认值警告仍在。首轮夹具误设同一用户为两项目成员触发`uq_prj_members__user_active`，已改为独立用户后重跑通过；这不是生产代码或冻结业务规则变更。

兼容性/升级/回滚：仅验证资产、L2决策和版本说明；无生产代码、Migration、API、依赖或权限改变，无升级动作，撤脚本扩展即可回滚。仍待多原型对同一需求的合法并集/重叠验收、更多失效输入、20并发、Server2025和生产信任源/入口。Gate3仍BLOCKED。

TraceLink：`CR-PRT-005` → `DEC-20261008-1077` → P03-A03-P01/P02隔离PG证据 → P03-A03-P03多原型与后续并发/生产入口。
