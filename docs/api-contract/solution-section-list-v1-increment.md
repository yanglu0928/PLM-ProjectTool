# SOL-04-A14：SolutionSection LIST HTTP 增量合同

日期：2026-10-09；细化 Gate 2 冻结 API-04 `SOL_SECTION_LIST`，不改变冻结路径或资源种类。

`GET /api/v1/projects/{project_id}/solution-sections` 要求当前 `plm_session`、可信 Host/可选匹配 Origin、有效 License 和当前 Project member。只接受 `page_size`（默认 50，1～100）与 `cursor` 各最多一个查询参数；ProjectId 仅来自 canonical 路径。拒绝任意原始 `after_section_id`、重复/未知参数。读模式 Section POST 返回 404，写模式 CREATE 由显式写路由优先处理。

分页按 SectionId UUID 升序稳定 keyset；`cursor` 为 Section 家族独立 32 字节 key 的 HMAC-SHA256 令牌，绑定版本、家族、ProjectId、Session 摘要、页大小及上一 SectionId。不同 Session/项目/页大小、Outline 家族串用、篡改和错误结构拒绝。HTTP 不接收客户端提供的原始数据库位置。

成功 `200` 含 `data.items[]` 固定安全摘要（Section/Outline/Project ID、key、状态、当前批准指针、创建时间、强 ETag）、`next_cursor`、`has_more`、一致 Trace ID 与 `Cache-Control: no-store`。不含正文、Requirement/Evidence/Trace 明细；每页仍由 Owner 重验当前 Session/成员/License 和非空批准指针。身份列表不等于已审批方案。

Session 无效 401、Host/Origin/License 403、项目不可见 404、游标/查询畸形 400、页大小非法 422、投影异常 503，均用 API-01 错误 Envelope。此增量只提供 `create_app(solution_section_list_router=...)` 可注入插槽；默认和当前 Windows 显式模式尚不挂载。正式目标账户独立 Vault key/备份恢复及 20 并发性能由后续任务验证，不能把合成 key 视为生产供给。
