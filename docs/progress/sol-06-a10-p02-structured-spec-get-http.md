# SOL-06-A10-P02：结构化专项详情 GET 合同

- 日期/版本：2026-10-16 / `0.1.0-dev.0`。TraceLink：Gate 2 冻结 `SOL_SPEC_GET` → A10-P01 受权内部读取 → 本项。
- 编码前检查：Phase 2；P01 实际 PG 读取/项目成员隔离及合成 License 验收已通过，冻结路径、统一响应及错误合同存在。本项仅增加 Solution 可选 HTTP 详情路由与应用组合参数，不装配 Windows，不改变 Schema/权限/冻结路径。
- Changed：GET `/api/v1/projects/{project_id}/structured-solution-specs/{spec_id}` 返回当前版本状态、类型化载荷、固定 Requirement/Section/Evidence 引用与 Review 字段；只接受受信 Host、有效 Session 和无查询 URL。成功 `data`/`trace_id` + `Cache-Control: no-store`；内部异常失败关闭。默认 `create_app()` 不挂载，仍返回 404。
- 验证：合同 3 项含默认关闭/固定投影/Session/Host/查询/畸形 ID/授权/License/损坏输出；后端全量 3636 通过、3 项既有跳过、5706 子例通过；开发 wheel 含路由模块（1396 条目）通过。第一次合同测试误预期畸形 ID 为 400，既有 `_uuid` 合同实际为 404，修正测试后复跑；未改产品行为。
- 兼容性/升级/回滚：无 Migration、破坏性 API、依赖或旧数据变化；移除可选路由参数可回滚，历史不动。仅合同/模拟服务测试，不声称实际 Windows HTTP/PG 已通过。
- 限制：OutputArtifact Owner、Windows 运行时、前端详情与 Review/章节六维可送审未完成，Gate 3/Pilot/正式发行保持未通过。
- Next：`SOL-06-A10-P03` Windows 显式运行时装配与真实 HTTP/PG 合成验收。
