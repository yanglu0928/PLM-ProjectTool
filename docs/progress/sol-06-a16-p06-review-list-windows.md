# SOL-06-A16-P06：Windows Review List 生产组合

日期/版本：2026-10-19 / `0.1.0-dev.0`。状态：`REVIEW_LIST_WINDOWS_HTTP_PG_PASS`；仅 Windows 11 合成环境实测，正式信任、Inbox UI、Pilot、Gate 3 和三平台发行未通过。

## 编码前检查

|项目|结论|
|---|---|
|当前 Phase / WBS|Phase 2 / `SOL-06-A16-P06`|
|输入基线|冻结 REVIEW_LIST、CR-RVW-004、A16-P02 AES-GCM 游标、P03 索引、P04 授权 Service、P05 默认关闭 HTTP|
|前置任务|P02～P05 已独立验收；现有 Windows Credential Manager/Vault 工厂和 SOL-06 REVIEW_GET Owner 可复用组合方式|
|涉及模块|Windows 独立 cursor key 工厂、Review List 生产 Router 工厂、显式读/写平台装配及合同/PG 验证|
|涉及实体/API|只读现有 Review/Round/Assignment；实现冻结 `GET /api/v1/projects/{project_id}/reviews`，不改迁移|
|涉及权限|既有 License、Session、Project `REVIEW_LIST` 与 SOL-06 当前系列/活动固定版本 Owner 逐项复验|
|验收标准|专用密钥缺失失败关闭、默认未挂载、读/写模式装配、真实 HTTP/PG 权限与分页、全量回归、wheel|
|风险|复用其他模块 key、缺 key 时降级临时 key、只凭历史 Assignment 放行、读取历史泄露其他审核人|

## 实施与验收

- `review-list-cursor-v1` 仅从运行账户的 Windows Credential Manager/Vault 读取，必须为 32 字节。缺失、长度不符或读取异常使启动失败关闭；不创建临时密钥或复用其他模块密钥。临时唯一测试凭据验证了实际 Vault 写入、备份、丢失和恢复，不接触正式固定 ref。
- 新增独立 Review List Windows Router 工厂，组合真实 SQL Repository、Session/Project 策略与 SOL-06 Subject Owner。只在显式平台读和读写模式挂载；默认应用和登录专用模式不开放。组合必需依赖缺失拒启动，生产入口清理运行时并返回安全启动错误。
- Windows 11 可弃 PostgreSQL 18.6、真实 SQLAlchemy/ASGI 链：提交后，经理和普通成员可看受权历史；仅经理当前 PENDING 分配进入 `my_pending`，成员无他人分配；`page_size=1` 连续分页可到达目标，游标跨会话或跨 view 拒绝。默认 404、无效 Session 401、跨项目 404、License 拒绝 403、未知 query/坏游标 400；读取不写 Audit。审批终态后历史仍在 `all`，`my_pending` 消失，`active_round=null`。
- Windows 工厂和生产启动合同：定向共 `63 passed, 71 subtests passed`；后端全量 `3781 passed, 3 skipped, 5924 subtests passed`。开发 wheel 1423 项，包含独立 key、Windows 和生产入口模块，SHA-256 `628b576f15b15f519f51141a404c74cd8aeeda155b4c934774a74dbf1982188c`。该 wheel 是开发检查产物，不是 Pilot/Release 包。

## 兼容、升级、回滚与剩余约束

- 无 Schema/API Breaking、角色集合、License 权益、依赖或历史数据变化；运行数据库需 0166。启用读/写模式前须在实际服务账户下供给、备份和验证专用 key。旧版本回滚可停用新路由并保留 key/Review 历史；已发出的游标不跨密钥轮换继续使用，需要客户端重新起页。
- 真实 PG/HTTP 链仍使用合成账户、License 与来源资料；不能证明正式服务账户、公钥、真实授权和安装。P07 前端 Inbox、P08 Edge 实测、正式性能、Gate 3/Pilot/发行仍待。

Next：`SOL-06-A16-P07` 实现 Reviewer Inbox 前端、项目入口与自动分页；用户无需输入 Review UUID，切项目/失权清屏且待办与历史状态不混同。
