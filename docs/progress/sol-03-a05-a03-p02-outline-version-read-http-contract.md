# SOL-03-A05-A03-P02：OutlineVersion 历史 GET/LIST 可选 HTTP 合同

日期：2026-10-09。结果：`SOL_03_A05_A03_P02_OUTLINE_VERSION_READ_HTTP_CONTRACT_PASS`；本项仅合同验证，真实 PG/Windows 组合另项。

编码前检查：Phase 2 / 本 WBS；输入为 Gate2 API-04 冻结路径、A05-A02 受权历史 Owner、A05-A03-P01 独立签名游标；依赖满足。只修改 Solution API 可选读取路由、应用组装参数、合同测试和增量响应说明，不变更 Schema/Migration、冻结角色或版本写入。DEC-1146 在实施前记录 LIST 最小元数据、GET 完整固定引用且不承诺 ETag 的设计取舍。

新增可选路由：GET 单个固定版本与按版本号倒序 LIST，统一可信 Host/Session/Owner/License/Project 成员检查、跨项目不可见、严格查询参数和独立签名游标。LIST 不批量回传固定引用/声明；GET 返回创建时固定快照，不将历史引用宣称为当前合格。未注入时 GET/LIST 保持 404；只读注入不开放 POST，既有写路由组装顺序保留。错误经 API-01 安全投影，响应 `no-store`。详细投影见 `docs/api-contract/solution-outline-version-read-v1-increment.md`。

验证：定向合同 3 项/14 子例，后端全量 3466 通过、3 跳过、5328 子例。未执行本路由真实 ASGI/PG 或 Windows 独立游标密钥来源/恢复，不将合同测试冒充端到端验收。可撤可选路由回滚，历史数据不受影响。下一项 `SOL-03-A05-A03-P03` 真实双 Scope ASGI/PG 验收，随后 Windows 组合与浏览器。Gate3/发行仍 BLOCKED。

TraceLink：Gate2 API-04 → A05-A02 Owner → DEC-1146 → A05-A03-P01 游标 → 本合同 → P03/P04。
