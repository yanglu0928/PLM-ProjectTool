# SOL-05-A02-P09：SectionVersion 不可变首响应闭锁表

日期：2026-10-09。结果：`SECTION_VERSION_FIRST_RESULT_SCHEMA_PG_PASS`；仅闭锁存储结构，非业务 CREATE PASS。

## 编码前检查

Phase 2 Platform Core；WBS `SOL-05-A02-P09`。输入 Gate2 DM-05/API-04、CR-SOL-003/P07、0138/0158 与 P08 操作策略；前置满足。单一问题是为未来持久幂等重放提供不可变首次 201 DRAFT 结果形状。涉及 Solution ORM、Alembic 0159、临时 PG 验证；无公开 API、权限或业务写 Owner。验收为空库/已有 Section 数据升级、空表降级重升、约束/Guard 正反例、非空拒降、Schema drift。风险为错误开放写入、结果与版本不一致或降级丢历史。

## 实施与验证

新增 `SolutionSectionVersionCreateResultRow` 与 `20261009_0159`。版本/Section/Project 复合 FK 和结果自身 CHECK 限定结构；首次响应全字段相等性和引用集完整性将在 P10 Guard 的原子提交闭环中验证，当前表始终全拒写。0138 根/子表的全拒 Guard 保持，Artifact 分支无 Owner 时仍不可写。详细列定义、兼容与回滚见 `docs/database-schema/solution-section-version-first-result-0159-increment.md`。

Win11 可弃 PG18.6 验证脚本退出0：空/已有 Project+Section 行升级、空表降级重升、Schema drift、字段约束/复合 FK、INSERT/UPDATE/DELETE/TRUNCATE 拒绝、非空首响应拒降；合成行仅在一次性测试连接内绕过 Guard 后清理，不是正式写入。后端全量 3526 通过、3 跳过、5510 子测试通过；首次全量发现两处测试清单仍固定 0158/旧表集合，更新迁移头和 ORM 表清单后重跑通过。旧 0138 全量脚本受后续 0146/0148 门禁影响仍未复验 PASS，本 0159 脚本不替代其旧历史结果。

兼容/升级/回滚：无现有 API/角色/配置/依赖变化。升级只增加空表，既有业务行不改写；结果表空时可降回 0158，非空时禁止降级并保留历史，不能用生产 `TRUNCATE` 清除。下一项 P10 是独立的 INSERT-only Guard/闭环迁移，须再次进行空历史审计与真实 PG 负例；P11 才建受权 Owner。正式信任/Server2025、性能/质量、Gate3/发行未通过，Debian13 实机依用户指令跳过。

TraceLink：Gate2 DM-05/API-04 → CR-SOL-003 → P07/P08 → DEC-1175 → 0159 闭锁首响应 → P10 Guard → P11 Owner → P12 HTTP → Gate3。
