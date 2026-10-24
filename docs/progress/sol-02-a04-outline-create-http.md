# SOL-02-A04：目录身份创建可选 HTTP

日期：2026-10-09；结果：`OUTLINE_CREATE_HTTP_PG_PASS`，限定可注入 Router 与 Win11 隔离 PG/合成 License，不是 Windows 生产组合或 Gate 3 PASS。

```text
当前 Phase：Phase 2；依 CR-SEQ-001 前置 Solution Owner
当前 WBS：SOL-02-A04
输入基线：冻结 API-01/API-04、CR-SOL-011、A03 内部 Owner/0146
前置任务：A03 Win11 隔离 PG 受权创建、幂等/审计/回滚通过
涉及模块：solution HTTP、可选 app 装配插槽；复用 Auth Session/Origin
涉及实体：SolutionOutline；不修改 Schema/版本/Review/Trace
涉及 API：SOL_OUTLINE_CREATE 项目 POST；默认未装配
涉及权限：PM/ImplementationMember，同项目有效 Session+CSRF/License
验收标准：201/ETag/Location/Trace、严格正文、安全拒绝、同 Key 重放与默认404
风险：目录身份被误作正式方案、成功 Location 尚无 GET、错误或响应泄露内部信息
```

Changed：新增严格项目 CREATE Router 和 `create_app` 可选插槽；响应只投影初始逻辑身份，不接受客户端 Scope/Actor/批准状态。Migration/依赖：无，复用0146。API 合同见 `docs/api-contract/solution-outline-create-v1-increment.md`。Tests：合同4通过/13子例，真实 SessionService/ASGI/Win11隔离PG18.6 创建/重放/冲突、PM/实施成员、客户角色/跨项目/撤权、CSRF/Session/License 及默认404通过；前序 PROJECT Reference 来源夹具也退出0。后端全量 `3364 passed, 3 skipped, 5016 subtests passed`。未运行 Windows 正式组合、真实浏览器或 Server2025。

兼容/回滚：无 Breaking Change、新 Schema/依赖/数据迁移；不注入新 Router 即恢复404，不能删除已建立的目录/Audit/Receipt。正式 License/服务账户、浏览器 UI、Review/Trace/Workflow、20 并发、POC-03 质量、Gate3/UAT/发行仍未验；Debian13 当前实机按用户指令暂跳过。TraceLink：API-04 → CR-SOL-011 → A03/0146 → 本 A04 → A05。
