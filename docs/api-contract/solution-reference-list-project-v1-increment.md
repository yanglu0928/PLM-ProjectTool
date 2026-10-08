# SOL-01-A04-P04-P05：PROJECT Reference List HTTP 增量

日期：2026-10-09；依据 Gate 2 冻结 API-04 `SOL_REFERENCE_LIST`、DEC-20261009-1115。细化现有 PROJECT 路径，不修改冻结操作；GLOBAL 未装配。

`GET /api/v1/projects/{project_id}/reference-solutions` 要求当前 `plm_session`、可信 Host 和可选匹配 Origin、有效 License 及同项目 ACTIVE 成员。仅允许 `page_size`（默认 50，1～100）和 `cursor` 各最多一个查询参数；路径 ProjectId 为唯一 Scope 来源。无请求正文、CSRF 或任意 Scope 参数。

分页按 Reference 根 UUID 升序稳定 keyset。`cursor` 为独立 32 字节密钥的 HMAC-SHA256 不透明令牌，绑定版本、Reference 列表家族、ProjectId、Session 摘要、页大小和上一条身份；不同 Session/项目/页大小、篡改、重复参数或错误结构拒绝。HTTP 不接受原始 `after_reference_solution_id`。

成功 `200` 含 `data.items[]` 的安全摘要（Reference/当前版本 ID、PROJECT/ProjectId、名称、Eligibility 状态、版本号/状态、创建时间、强 ETag），以及 `next_cursor`/`has_more`、一致 Trace ID 和 `Cache-Control: no-store`。List 不含固定 DocumentVersion/Evidence 明细、文件内容或创建时指纹；详情由 GET 返回，历史读取不等于当前来源资格。Session 无效 401、Host/Origin/License 403、项目不可见 404、游标/查询畸形 400、页大小不合法 422、投影异常 503，均使用 API-01 错误 Envelope。

此增量仅提供 `create_app(project_reference_list_router=...)` 可注入插槽，默认、Windows 显式模式及 GLOBAL 仍不挂载。Windows 正式独立游标密钥来源与恢复验证由后续组合任务完成；不得将本轮隔离测试密钥投入生产。
