# SOL-06-A09-P04：专项 CREATE HTTP 合同

- 日期/版本：2026-10-12 / `0.1.0-dev.0`。TraceLink：冻结 API-04 `SOL_SPEC_CREATE` → A07/A08/A09-P03 内部 Owner → 本项。Phase 2。
- 编码前检查：现有 Session/Origin/CSRF/Key/Trace HTTP 边界、受权内部 Service 与首次 DRAFT 投影均存在；只新增冻结 POST 路径的默认关闭可选 Router，未扩大 Schema、角色或公开 API 语义。typed payload 为 A06 严格对象，需求/章节固定版本至少各一；无 OutputArtifact Owner 前非空附件在 HTTP 边界拒绝。
- Changed：`POST /api/v1/projects/{project_id}/structured-solution-specs` 强制 Origin、Session/CSRF、幂等 Key、无 query、严格 UTF-8 JSON/字段集合；将固定来源传给受权 Service，201 仅返回不可变首次 DRAFT、payload、引用计数/指纹/版本和 Location，`Cache-Control: no-store`。缺省 `create_app()` 保持 404；不提供 Review/送审暗示。
- Verification：合同 4 项/17 子例涵盖默认关闭、201/Trace/Location、匿名/错 Origin/CSRF/Key、未知字段、裸附件、坏固定引用、重复 JSON/NaN、错误映射及跨项目结果失败关闭；后端全量 3630 通过/3 跳过/5702 子例；开发 wheel 含路由。尚无真实 Windows HTTP/PG 装配，本项不称实际用户可用。
- 回滚/风险：仅可选 HTTP 层与注入槽，无 Migration/旧数据/依赖变化；删除路由注入可回退入口，已有业务/Audit 历史保留。下一项 P05 验证真实 Windows 运行路径，OutputArtifact/Trace/Review/Gate3/Pilot/正式发行仍待。
