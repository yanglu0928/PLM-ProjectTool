# SOL-01-A04-P04-P02：PROJECT Reference 当前版本 GET 增量

日期：2026-10-09；依据 Gate 2 冻结 API-04 的 `SOL_REFERENCE_GET`。本文件细化既有操作，不修改冻结路径/方法，也不开放 GLOBAL 路由。

`GET /api/v1/projects/{project_id}/reference-solutions/{reference_solution_id}` 使用当前 `plm_session` Cookie、可信 Host 和可选匹配 Origin；不要求 CSRF 或请求正文。两个路径 ID 必须为非零 canonical UUID，路径 ProjectId 是唯一 Scope 来源；查询串拒绝。有效 License、当前 Session 及同项目有效成员必需；跨项目、暂停成员、缺记录统一不可见。GET 不赋予 PM/IM 创建权，也不代表固定来源现在仍合格。

成功 `200` 的 `data` 白名单为根/当前版本 ID、Scope/ProjectId、名称、Eligibility 状态/原因、版本号/状态、来源项目分类、脱敏分类、适用性、按创建顺序固定的 DocumentVersion/Evidence ID、创建时来源/内容 SHA-256 指纹、创建人/时间、版本创建人/时间和强 ETag。响应含一致的 `trace_id`、`ETag`、`Cache-Control: no-store`。无文档正文、绝对文件路径、Session 或内部异常。历史引用展示不替代来源当前性、Eligibility 命令、Review 或人工确认。

公开错误沿用 API-01 Envelope：Session 无效 401，Host/Origin 403，License 拒绝 403，缺记录/越权 404，查询畸形 400，固定来源投影异常 503。该 Router 仅以 `create_app(project_reference_read_router=...)` 显式注入；默认应用及 Windows 正式组合仍不挂载，后者留下一项。
