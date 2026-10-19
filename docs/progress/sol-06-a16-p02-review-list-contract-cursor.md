# SOL-06-A16-P02：Review List 合同与加密游标

日期/版本：2026-10-19 / `0.1.0-dev.0`。状态：`REVIEW_LIST_CONTRACT_CURSOR_PASS`；本项只完成纯合同与游标，不表示 Repository、HTTP、Windows Inbox 或 Gate/Pilot 已通过。

## 编码前检查

|项目|结论|
|---|---|
|当前 Phase / WBS|Phase 2 / `SOL-06-A16-P02`|
|输入基线|冻结 API-01/02 REVIEW_LIST、Q-RVW-01、CR-RVW-004、A16-P01|
|前置任务|P01 已确认路径冻结且需专用游标；无数据库或生产组合前置阻塞纯合同|
|涉及模块|Review application DTO、Review API cursor、单元测试与增量合同文档|
|涉及实体|只定义 Review 列表投影与位置；不创建/修改 Review 事实|
|涉及 API|细化既有 GET 的 `all/my_pending`、Page 与最小 item；未挂 Router|
|涉及权限|游标绑定 Session/Project/view/page_size；DTO 形状不构成授权|
|验收标准|严格 DTO；加密位置；随机 nonce；篡改/错 key/跨范围拒绝；全量回归与 wheel 入包|
|风险|隐藏候选位置明文泄露；游标跨用户/项目/筛选复用；列表 DTO 带出他人意见；把形状校验当授权|

## 实施结果

- 新增纯 `ReviewListQuery/Position/Item/Page` 合同：`view` 仅 `all/my_pending`，页大小 1～200；活动 Review 只带固定版本和当前 actor 的 Assignment 摘要，终态必须没有 `active_round`。Page 明确允许空 `items` 且 `has_more=true`，支持 Subject Owner 隐藏候选后继续翻页。
- 新增 `ReviewListCursorCodec`，使用专用 32-byte key 和 AES-256-GCM。AAD 绑定 family/version、Session SHA-256、Project、view、page_size；密文只保存 UTC microsecond `created_at` 与 canonical `review_id`，12-byte 随机 nonce 使同位置每次 token 不同。
- DTO 不包含主题正文、Evidence/Trace、内部锁、其他 reviewer 身份/意见；游标形状或解密错误统一 `REQUEST_MALFORMED`，不暴露失败原因。
- 首版游标曾按 HMAC 设计；在提交前发现隐藏候选的 Base64 位置仍可被读取，故改为 AES-GCM 并完整复验。该修正没有进入远端历史，也未改变生产依赖（`cryptography` 已为正式依赖）。

## 验证证据

- 定向：`6 passed, 11 subtests passed`，覆盖合法/非法 DTO、短页、活动/终态、随机密文、位置不可见、篡改、错 key、跨 Session/Project/view/page_size 与畸形输入。
- 后端全量：`3764 passed, 3 skipped, 5870 subtests passed`。
- Python 3.13 开发 wheel：1418 项，两个新模块均恰好入包，SHA-256 `28515074cbb0af6af6a5ed4d2eaf56a013abca9e650f4eddd346ab122d405d44`；该 wheel 不是 Pilot/Release 包。
- 初次非法 DTO 测试把异常捕获点写在构造之后，导致 1 项测试失败；修正测试后通过。`python -m build` 与 venv `pip` 入口均不可用，未把旧 wheel 误记为证据；最终使用既有 setuptools build backend 构建成功。

## 兼容、回滚与未完成项

- 无 Migration、运行 Router、Project policy、Windows Vault、角色或旧数据变化；新增合同/codec 尚未装配，删除新增模块即可回滚。
- AES-GCM 复用已经批准的正式 `cryptography` 依赖，不新增依赖。后续必须使用独立 `review-list-cursor-v1` key；不得复用其他列表 key 或生成 fallback。
- Repository/逐项 Subject Owner 授权、0166 索引、HTTP、Windows 组合、前端与 Edge 均未完成；Gate 3、Pilot 和发行状态不变。

Next：`SOL-06-A16-P03` 实施 CR-RVW-004 的 Migration 0166 与 ORM 索引，完成空库/有 Review 历史升级、降级重升、索引查询路径和 Alembic drift 验证。
