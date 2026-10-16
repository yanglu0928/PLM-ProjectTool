# SOL-04-A14：Section LIST 可选 HTTP/真实 PG

日期：2026-10-09。结果：`SOL_04_A14_SECTION_LIST_HTTP_PG_PASS`，限 Windows 11 隔离 PostgreSQL 18.6、真实 ASGI/Session 与合成 cursor key/License；Windows 显式模式与正式目标账户尚未挂载。

## 编码前检查

- Phase/WBS：Phase 2 Platform Core / SOL-04-A14。
- 输入基线：冻结 API-04 `SOL_SECTION_LIST`、A11 内部 Owner/keyset、A12 Section 家族签名 cursor、A13 Windows 独立 key 来源。
- 前置：成员/批准指针每页复验、三页 PG keyset、游标隔离/篡改拒绝与临时 Vault 恢复通过。
- 模块/实体/API/权限：仅 Solution 可选 HTTP、应用工厂注入与验证；不改 Schema/Migration、角色或冻结路径。当前 Project member 由 Owner 复验。
- 验收：三页固定安全摘要、Trace/no-store、cursor Session/项目/page size/家族绑定、匿名/跨项目/暂停/License/错误查询拒绝、默认和只读 POST 404、后端全量。
- 风险：错误暴露、把内部位置当公开 cursor 或只读 POST 返回 405。HTTP 仅接受签名令牌，错误最小映射并显式 POST 404；正式 key/性能另验。

## 实施与验证

新增 `create_section_list_router`，默认 page size 50、上限 100，拒绝重复/未知参数和原始 after ID；基于独立 Section cursor 解码内部位置，每页调用受权 Owner，返回安全摘要与下一签名 cursor。默认应用不注入，读模式 Section POST 显式 404。Win11 一次性 PG18.6 真实 ASGI/Session 夹具验证三页、项目成员含客户角色、无页游标全量、跨 Session/项目/大小/篡改拒绝、重复/未知参数、匿名/Origin/暂停/License 和默认关闭；A11 与原 PROJECT Reference 夹具回归通过。

后端全量 `3391 passed, 3 skipped, 5111 subtests passed`。兼容/升级/回滚：冻结 API-04 内实现，无 Migration、依赖或前端变化；撤下可选 Router 可关闭入口，Section 历史保留。下一项 `SOL-04-A15` Windows 显式读/写组合及独立 Vault key fail closed。正式目标服务账户 key/ACL/备份、20 并发、Server2025、Gate3/UAT/发行未验；Debian13 实机依用户指令暂跳过。
