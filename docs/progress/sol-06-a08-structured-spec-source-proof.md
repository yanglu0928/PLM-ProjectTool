# SOL-06-A08：专项来源现时组合证明

- 日期/版本：2026-10-12 / `0.1.0-dev.0`。TraceLink：冻结 DM-05/SC-01 SOL-06 → A07 固定输入 → 既有 Requirement/Section/Document/Evidence Owner → 本项。当前 Phase 2。
- Changed：新增同事务 `StructuredSpecSourceProofService`，复用 Requirement 当前已批准版本证明、Section 当前 ACTIVE 身份及固定版本完整历史、Document 固定版本物理内容证明、Evidence 当前 PROJECT 资格证明；按请求顺序绑定各来源指纹/Review/状态/版本与载荷请求指纹。APPROVED Section 必须为当前 approved pointer 且有 Review；DRAFT/IN_REVIEW 必须为最新固定版本，IN_REVIEW 要有 Review 对。RETURNED/RESTRICTED、旧草案、跨项目及内容制品为裸 ArtifactId 均拒绝。
- 权限边界：Requirement/Section 内部证明仅在调用者同一事务读目标，Evidence/Document 证明使用实际 Session/Project 边界；本组合本身不执行 SOL-06 创建操作授权、License、写入或 Review/Trace 判定。未来正式 Owner 必须在同事务先证明 actor/Project/License/CSRF，锁定版本 series 并重验来源，不能把本返回值单独用作授权凭据。OutputArtifact Root 仍不存在，非空 `artifact_ids` 直接失败关闭。
- Verification：内部六项/六子例覆盖正例、当前批准章节、旧/失效/跨项目/错误证明/裸附件及异常；Windows 11 一次性 PG18.6 合成真实 Auth/Document/Evidence/Requirement/SectionVersion 链验证当前来源、物理文件篡改、Evidence 撤回、跨项目与旧章节拒绝，通过后临时资源清理。底层合成 Requirement Review 是测试数据，非客户确认。后端全量 3621 通过/3 跳过/5677 子例，开发 wheel 构建及模块入包通过。
- Migration/API/rollback：无 Migration、公开 API、权限或旧历史更改；内部未装配 Service 可撤，来源历史保持。正式写 Owner、Version Root 开锁、同事务 Audit/幂等、Trace/Section VALIDATE、Pilot/Gate3/正式发行仍未通过。Server2025 未在本项实测，Debian13 实机依用户指令跳过。
