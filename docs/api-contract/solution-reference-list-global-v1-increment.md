# SOL-01-A04-P09-P04：GLOBAL Reference List HTTP 增量

日期：2026-10-09。依据 Gate 2 冻结 API-04 `SOL_REFERENCE_LIST` 与 P09-P01 设计核查；仅细化原有 GLOBAL 展开，不改变 PROJECT 路径、请求或游标。

`GET /api/v1/global/reference-solutions` 要求当前 `plm_session`、可信 Host/Origin、有效 License 与当前 DeploymentAdmin。仅接受 `page_size`（默认 50，1～100）和 `cursor` 各最多一次；不能传入 ProjectId、自由 scope、原始 `after_reference_solution_id` 或请求正文。未登录 401，Origin/License 403，非 Admin 404；输入/游标、投影或依赖异常按 API-01 错误 Envelope 失败关闭。

按 GLOBAL Reference 根 UUID 升序 keyset 分页。专用 32 字节密钥签名的 HMAC-SHA256 不透明游标绑定版本、`global-reference-list` 家族、Session 摘要、页大小和末项 ID；PROJECT 游标即使恰用相同测试密钥也不可接受。篡改、跨 Session、换页大小、重复或未知查询参数一律拒绝。

成功 `200` 含 `data.items[]` 安全摘要：Reference/当前版本 ID、`scope:"GLOBAL"`、`project_id:null`、名称、Eligibility 状态、版本号/状态、创建时间和强 ETag；另有 `next_cursor`、`has_more`、Trace ID、`Cache-Control:no-store`。不含文档/证据明细、客户正文、脱敏确认 ID 或“当前确认有效”断言；详情和来源物理内容须分别经过已有授权入口。已撤回的确认仅保留历史 Reference 读取，不授予当前再利用资格。

默认应用不注入时 404。Windows 显式只读/写模式从当前运行账户 Vault 解析独立 `global-reference-list-cursor-v1` KeyRef，缺失/错长即启动失败；只读模式 POST 保持 404，写模式既有 Create 路由优先。正式目标服务账户供给、离线备份与异账户恢复属于发行验收，不得把合成测试密钥当生产信任源。
