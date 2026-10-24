# 0162：闭锁 StructuredSolutionSpec 四类固定引用

- 版本/来源：2026-10-12 / `20261012_0162`；Gate 2 SC-01/SC-02 → DEC-1200 → 0161 版本根。只追加新迁移，不改冻结 Schema V1 或已有历史。
- 四表：`sol_spec_requirement_refs`、`sol_spec_section_refs`、`sol_spec_evidence_refs`、`sol_spec_artifact_refs` 均保存固定 SpecVersion/Series/Project 与正 ordinal；复合 FK 回根，并约束同一版本中顺序及目标不重复。
- Requirement/Section 分别保存逻辑身份和固定 VersionId，同项目复合 FK 确保身份、版本与项目一致。Evidence 保存固定 EvidenceId FK；其 GLOBAL/PROJECT 现时资格须由未来 Owner 检查，数据库 FK 不代表可用。Artifact 保存固定 OutputArtifactId；由于 OutputArtifact Root 尚不存在，暂无目标 FK，不能视为有效来源。
- 闭锁：四表所有 INSERT/UPDATE/DELETE/TRUNCATE 拒绝，不能从外部绕过类型化 payload、来源资格、授权或审计。0161 Root Guard 不变；SectionVersion 0160 Guard 不变。
- 升级/回滚：0161 → 0162 不回填、不修改已有业务数据。四张表全空才可降回 0161；任一非空均拒降并保留历史。离线降级禁用。
- 验收：Windows 11 隔离 PostgreSQL 18.6 空/已有 Project 数据升级、空表降级重升、FK/ordinal/重复负例、DML 闭锁、合成非空拒降、Alembic drift；0161 根表回归、后端全量 3601 通过/3 跳过/5612 子例及开发 wheel 通过。非空测试仅在可弃数据库中临时停用 Owner 触发器。正式合法目标、Owner 与客户数据均未参与本次验证。
