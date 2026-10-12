# SOL-06-A01：StructuredSolutionSpec 前置核查

- 日期/版本：2026-10-12 / `0.1.0-dev.0`。TraceLink：Gate 2 DM-05/SC-01/02/API-04 → DEC-1194 → TRC-01-A03-P01～P03 → 本项 → SOL-06-A02。
- 基线：SOL-06 是 PROJECT V-PRJ 不可变专项版本，以 `spec_series_id` 升版；`sol_structured_specs` Root 配四类固定 Requirement/Section/Evidence/Artifact 引用。四种类型为 PROCESS_MODEL、INTERFACE_SPEC、MIGRATION_SPEC、PERMISSION_DESIGN，均有专属字段校验。冻结 API 包含创建、修订、读取、验证、评审；章节后续固定 SpecVersion 引用并须现时核验。
- 现状/差异：当前 Solution ORM 与迁移 head `20261009_0160` 只有 Outline/Section 等，未有 SOL-06 Root、四类 child、Section→Spec refs 或受权 Owner。Trace 的 REQ-03/SOL-05 与 ACTIVE `IMPLEMENTS` 内部证明已完成，但尚未接 Section VALIDATE/公开 Trace 写；Spec 和 Trace 六维仍不可用。这是施工缺口，不是冻结 Scope 删除或 Gate PASS。
- 顺序：A02 先建闭锁版本 Root/ORM/Migration；随后四类 owned refs 与类型化 payload、真实 Owner/生命周期、HTTP/Windows；再以独立 CR 处理 Section 既有 CREATE 兼容与固定 Spec refs，最后接六维现时资格/Review。A02 编码前单独核对字段、锁顺序、可逆迁移；未具备 payload/受权 Owner 不开写。类型化表/JSONB 候选留 payload 切片决策。
- 验证/风险：本项仅静态比对冻结 DM/SC/API 与当前 ORM/迁移/路由，没有新程序测试或数据库 Migration。后续真实 PG 必测空/有数据升降、非空保留、漂移、跨项目/版本、受控 DML；Section 0160 历史不可变，旧 CREATE 不破坏。正式公钥/账户、Server2025、Debian13、性能、Gate3/Pilot 均未由本项验证；Debian13 实机依用户指令跳过。
