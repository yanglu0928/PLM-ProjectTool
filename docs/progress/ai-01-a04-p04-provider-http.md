# AI-01-A04-P04：可选 Provider GET/LIST HTTP

日期：2026-10-02；结果：`OPTIONAL_HTTP_ASGI_PG_PASS / PLATFORM_COMPOSITION_CLOSED`。依据冻结 API-01/API-03、DM-04、P01～P03；本项只新增显式注入的 Provider 只读 Router，不让普通默认应用自动开放，Phase 2/Gate 3 仍开放。

## 编码前检查

|项目|结论|
|---|---|
|当前 Phase/WBS|Phase 2；`AI-01-A04-P04` 可选 GET/LIST HTTP|
|输入基线|冻结 `AI_PROVIDER_GET/LIST`、安全 Envelope/错误码、P01 详情安全投影、P02 签名列表、P03 Windows 钥来源|
|前置任务|内部详情/分页及独立游标来源已验证；现有 Host/Session/License 边界可复用|
|涉及模块/实体|AI API Router、可选 `create_app` 注入；当前 Provider 只读，不改实体|
|涉及 API|新增冻结 GET `/api/v1/admin/ai/providers` 与 `/{provider_id}` 的可选实现；默认仍404|
|涉及权限|可信 Host、Cookie Session、当前 DeploymentAdmin/License；GET 不要求 CSRF；非管理员按404，失效 License 按403|
|验收|成功 `data`/`trace_id`、`X-Trace-Id` 一致；详情 ETag/no-store；列表1～200、签名游标、仅固定脱敏字段；未知/重复查询400、坏游标400、页长422；隔离 PG/ASGI/权限/撤权|
|风险|路由被误认为正式生产可用；当前 Windows 平台组合未装配，正式服务账户独立钥/License 信任材料尚未供给|

## 结果与验证

AI 自有可选 Router 显式投影 ProviderView，包含稳定 ID、kind、显示名、受控端点策略/地区/外发类别、能力、SecretRef 遮罩、状态、配置版本及资源 ETag；不返回完整 SecretRef、API Key、密文或 Adapter 内部信息。详情返回 `ETag: "vN"`，所有响应 `Cache-Control: no-store`；列表保留 P02 的会话绑定游标和每页授权重验。将内部无效游标分类修正为冻结的 `REQUEST_MALFORMED` 400，P02 回归同步更新。Router 仅可通过 `create_app(ai_provider_read_router=...)` 显式挂载。

定向合同/单元7项 PASS；Windows 11 隔离 PostgreSQL18.6 + ASGI：默认404、显式两页列表/详情、真实 DeploymentAdmin/普通用户授权、合成 License 拒绝、完整 SecretRef 不回显、强 ETag、游标错页长400、撤销真实 Session 后拒绝 PASS；P02 隔离 PG 游标回归 PASS。后端全量第一次与 P02 回归连续运行时 Python 进程以 Windows 访问冲突 `-1073741819` 退出，未形成测试结论；单独重跑1920项/3跳过、0失败。访问冲突未复现，原因未定，后续若重现需定位原生依赖/进程状态。开发 wheel SHA-256 `9a2eced0b188bc11f94e736ff296deeab6ffc0c014002387b655d5074f687685`；测试库已删除，PG 恢复原停机状态。

兼容/升级：无 Schema/依赖/Breaking API；需既有0054及显式 Router 注入，不注入即回退。未完成 Windows 正式平台组合挂载、目标账户密钥与信任供给、Provider 写 API/激活/模型路由/逐次外发、质量、三平台/Gate/UAT/可用包。下一项 `AI-01-A04-P05` Windows 显式平台组合挂载/缺密钥失败关闭与隔离 PG 验证；不得把合成材料记为生产就绪。
