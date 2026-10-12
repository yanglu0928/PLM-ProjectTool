# SOL-06-A03：专项四类固定引用 Schema

- 日期/版本：2026-10-12 / `0.1.0-dev.0`。TraceLink：Gate 2 SC-01/SC-02 → DEC-1200 → 0161 Root → 0162 refs → 本项。
- Changed：追加四张闭锁 owned-ref 表、ORM 和迁移 head/元数据清单测试；RequirementVersion、SectionVersion 均有同项目复合 FK；Evidence 仅身份 FK；Artifact 因目标 Root 缺失保持无目标 FK 且闭锁。无 API/权限/依赖变更。
- Verification：Windows 11 可弃 PostgreSQL 18.6 空/有数据升级、空表降级重升、DML/TRUNCATE 闭锁、FK/ordinal/重复约束、非空拒降及 drift 退出 0；0161 根表验证因 0162 新 FK 调整 TRUNCATE 断言后复跑退出 0。定向迁移/ORM 清单 7 通过、全量后端 3601 通过/3 跳过/5612 子例、开发 wheel 构建通过。未植入合法 Requirement/Section/Evidence 业务版本，目标现时资格留后续 Owner 验收。
- Risk/rollback：四表不能写入；未来 Owner 必须证明 Evidence 当前资格、Artifact 真实目标和同事务不可变版本快照。只有空表可降回 0161，非空历史不得清空回退。typed payload、正式 Owner/HTTP/Windows、章节固定引用及六维可送审未完成；Gate3/Pilot/正式发行未放行。Server 2025 未实测，Debian 13 实机依用户指令跳过。
