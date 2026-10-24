# SOL-06-A09-P03：专项受权内部创建 Service

- 日期/版本：2026-10-12 / `0.1.0-dev.0`。TraceLink：Gate 2 SOL-06 → 0161～0164 → A07 固定草案/A08 来源证明/A09-P02 Repository → 本项。Phase 2。
- 编码前检查：同事务来源、完整 INSERT-only DRAFT、首结果重建与持久收据/Audit/项目授权基础设施均已存在；本 WBS 仅接入内部创建 Service 与一项项目操作策略，不变更冻结 `/api/v1`、Schema、AI/插件边界。形式化判断见 DEC-20261012-1203。
- Changed：在 License、Session/CSRF 和 ProjectManager/ImplementationMember 授权后预留项目范围幂等 Key；新请求证明现时来源，写完整 DRAFT、单条 Audit 和首次 201 收据后才提交。同 Key 重放先重检当前授权/License，再重建不可变首次结果；不重复外部来源读取、写入或审计。前驱与 series 由 Repository/0164 拒绝过期或并发冲突。
- 验证：Win11 可弃 PG18.6 真实合成 Auth/Project/License/已批准 Requirement/最新 SectionVersion/Document/Evidence → 首次创建、同号与并发同号重放、成员创建、同 series v2、旧前驱/跨项目/错误 CSRF/无效 License/裸附件拒绝及 Audit 失败回滚；根、收据、Audit 均各 4 条。定向 5 项/3 子例，后端全量 3626 通过/3 跳过/5685 子例；开发 wheel 包含新 Service。
- 风险与回滚：无 Migration、公开 API 或旧数据变化；内部 Service/策略可撤，已写历史不可清除。合成 License 仅作隔离验证，绝非正式信任。未接 HTTP/Windows/UI，未建立 Artifact 目标、Trace/Spec 固定引用或章节 ready_for_review，Gate3/Pilot/正式发行仍阻塞。
- Next：`SOL-06-A09-P04` 私有 CREATE HTTP 合同与投影，之后单独验证 Windows 装配及页面。
