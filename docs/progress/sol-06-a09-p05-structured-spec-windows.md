# SOL-06-A09-P05：Windows 专项 CREATE 真实链

- 日期/版本：2026-10-12 / `0.1.0-dev.0`。TraceLink：冻结 API-04 `SOL_SPEC_CREATE` → A09-P03 受权 Owner/P04 默认关闭 HTTP → 本项。Phase 2。
- 编码前检查：Windows Solution 组合已有显式写模式、正式设计的 Session/Origin/License/Document/Evidence/PG/Audit/Receipt 装配；本项仅把 SOL-06 CREATE 接入该模式，不更改默认开关、Schema、角色或 API 语义。正式信任锚仍非验收事实。
- Changed：Windows 工厂在所有来源/写依赖齐备时构造受权 SOL-06 Service；`production_login` 只在 `include_secret_write` 下注入可选 Router。默认 `create_app` 不装载。依赖缺失失败关闭。
- Verification：Win11 可弃 PG18.6 的真实 ASGI/Session/Document/已批准 Requirement/最新 SectionVersion/Evidence/SQL 链首创、同号重放、实施成员创建、跨项目/错误 CSRF/裸附件拒绝；DB 2 Root、2 Receipt、2 Audit，关闭默认 404、缺 Document 依赖拒装；后端全量 3630 通过/3 跳过/5702 子例，开发 wheel 通过。
- 风险/回滚：无 Migration；关显式写模式或撤工厂注入可停止新入口，不删除历史。隔离环境使用合成信任，不等于生产 License；未证明真实服务账户、离线安装、UI 或客户确认。`SOL-06-A09-P06` 接前端；OutputArtifact、Trace/Spec、章节 ready_for_review、Gate3/Pilot/Release 继续阻塞。
