# 0164：StructuredSolutionSpec 完整草案 INSERT-only 闭合

- 版本/来源：2026-10-12 / `20261012_0164`；0161 Root/0162 四类引用/0163 payload → DEC-1202。保留旧迁移与 Gate 2 原冻结提交，不改表列或 `/api/v1`。
- Root 只接收无 Review 的 DRAFT INSERT；同 series 使用事务级 advisory lock 串行决定首版 `version_no=1` 或准确前驱+递增版号，并保持同 Project/Type。UPDATE/DELETE/TRUNCATE 继续拒绝。
- payload、RequirementRef、SectionRef、EvidenceRef 只允许在其 Root 创建的同一数据库事务内插入；通过 Root 的 PostgreSQL `xmin` 对照当前事务 ID，提交后集合封印。延迟闭合约束在提交时要求每个 Root 恰一个 payload、至少一条需求及章节固定引用，四类 ordinal 各从 1 连续；ArtifactRef 仍无真实 OutputArtifact 目标，全部写入拒绝。旧非空历史不得降级，空集合可降回 0163 重新闭锁。
- 本迁移只建立不可变结构，不验证四类业务语义、来源现时资格、Session/CSRF/License/Project 权限、Audit、持久幂等或人工 Review；这些由后续正式 Owner 及验收承担。直接有数据库写权限的服务账户仍属于可信边界，不能用此迁移替代最小权限与数据库凭据保管。
- Windows 11 可弃 PostgreSQL 18.6：空库升至 0164、已有 Project/Section/Requirement/Evidence 升级、空 SOL-06 降级重升、缺 payload/顺序空洞/Artifact/错误版号与前驱/修改或删历史/提交后补写拒绝、同 series 并发恰一成功、非空拒降及 Alembic drift 均通过。历史 0161～0163 验证改为分别固定其原修订，不再把旧闭锁断言误用于新 head。
