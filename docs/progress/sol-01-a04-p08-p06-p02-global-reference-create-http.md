# SOL-01-A04-P08-P06-P02：GLOBAL Reference Create 可注入 HTTP

日期：2026-10-09；结果：`GLOBAL_CREATE_HTTP_CONTRACT_PASS`，仅可注入 API 合同/单元回归，不是隔离 PG/Windows 正式装配或真人确认通过。

编码前检查：Phase 2；输入 P06-P01 前置、冻结 API-04 `SOL_REFERENCE_CREATE`、CR-SOL-006/007/009/010，及现有全局 Owner/来源证明/确认账本。前置内部 GLOBAL 创建能力存在，缺公开路由。仅修改 Solution Create API、平台可选注入和合同测试；无 Schema/依赖/权限扩大。验收为冻结六字段、Session/CSRF/Origin/License 的分层入口、Owner 安全响应、默认关闭和错误失败关闭。

实现：新增 `create_global_reference_create_router`，沿用 PROJECT Create 的受限 JSON/规范 ID/可信来源解析，将 scope 固定为 `GLOBAL`、project 固定为 `None`；既不接受客户端确认 ID，也不自行认可预览。调用现有 `ReferenceCreateService`，由其在写事务内重算来源并证明最新有效人工确认；响应仅白名单投影 201、ETag/Location/no-store/Trace，确认 ID 仅在内部持久记录。`create_app` 可选择注入该路由，默认和仅装 PROJECT 路由时保持 GLOBAL 404。详细合同见 `docs/api-contract/solution-reference-create-global-v1-increment.md`。

验证：GLOBAL/PROJECT 定向合同 `7 passed / 17 subtests`，包括默认/错 scope 404、成功安全投影、缺 Session/错误 Origin/CSRF、缺 Key、非法 query/额外确认 ID/错 UUID/重复 JSON、Owner 来源拒绝与错返回 503；后端全量 `3340 passed, 3 skipped, 4939 subtests passed`。本项未运行真实 PG/文件、Windows 组合、浏览器或正式人工确认；不把 Fake Owner 合同测试当成业务资格证明。

兼容/升级/回滚：完成原冻结 Operation 的 GLOBAL 路径展开，不改既有 PROJECT 行为或冻结请求；无 Migration、依赖或数据升级。回滚不注入新路由，已持久化的业务历史和确认/Audit/收据不删除。风险为误挂载或把脚本确认当正式确认；P06-P03/P04 须以独立证据关闭。正式 License/目标账户、Server 2025、20 并发、Gate 3/UAT/发行、真人资料脱敏未验；Debian 13 依用户指令跳过。

TraceLink：冻结 API-04 → CR-SOL-006/007/009/010 → P06-P01 → 本 P06-P02 → P06-P03/P04。
