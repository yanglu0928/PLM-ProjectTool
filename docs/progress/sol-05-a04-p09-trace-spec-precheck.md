# SOL-05-A04-P09：章节 Trace/StructuredSpec 可信验证前置核查

- 日期/版本：2026-10-12 / `0.1.0-dev.0`。TraceLink：Gate2 DM-05/SC-01/API-04 → CR-SOL-003 → A04-P01～P08 → 本项 → TRC-01-A03/SOL-06/Section Review。
- 证据：冻结模型要求 `SolutionSectionVersion.structured_spec_refs`，SC-01 映射 `sol_section_spec_refs` 并要求 SOL-06 `sol_structured_specs` 及四类引用；当前 Solution ORM/0160 只有章节根、需求、Evidence、首次结果，没有 Spec 引用表或 SOL-06 实体/迁移。Trace 域白名单包含 REQ-03/SOL-05/SOL-06，通用 Link 表及内部创建已存在，但可见组合层仅有 DocumentVersion Trace 目标证明，缺 Requirement/Section/Spec 目标 Owner 和正式创建路由。A04-P03 Validator 将 trace/spec 固定 `UNAVAILABLE`；浏览器验证 200 不意味着可送审。
- 结论：`VALIDATE` 四项固定/来源核查与 UI/PG/Edge 流程已验，但 Trace/Spec 两维目前没有可信 PASS 路径。不能以“零引用”或 AI 推断代替显式设计/Trace 覆盖；`ready_for_review=false`、Section Review 与 Gate3 继续受阻。本项只完成静态前置审计，不声称新业务能力 PASS。
- 实施顺序：`TRC-01-A03-P01` RequirementVersion 目标证明 → `P02` SectionVersion 目标证明 → 当前有效 `IMPLEMENTS` 关系/覆盖核验 → SOL-06 专项规格 Schema/Owner/类型验证 → Section 固定 Spec 引用与相应 CREATE 兼容/迁移设计 → 六维现时核验 → Section Review。每项单独前置/测试；若需破坏冻结 `/api/v1`，先独立 Change Request 选新 API/v2，并保留旧历史。
- 兼容/升级/回滚：本项仅核查与排序，无 Migration、API、程序/数据变更；后续 DB 变更必须独立完成空/有数据升降及非空保留验证，不能改变 0160 历史 DML Guard 的不可变性。正式信任、Server2025/Debian13、性能/Gate3/Pilot/发行未通过。
