# AI-01-A05-P03-A03：Provider Test 可选 202 HTTP

日期：2026-10-02；状态：Windows 11 合成 HTTP 合同 PASS；未挂 Windows 平台组合，整体 A05/Gate 3 未通过。

## 前置与实现

- Phase 2；P01、P02、P03-A01/A02 已完成。冻结 API-03 指定 `POST /api/v1/admin/ai/providers/{provider_id}:test`、DeploymentAdmin、S/L/C/I/M/A、`202 JobRef`。DEC-20261002-643 控制可选挂载。
- 路由检查可信 Origin、Session/CSRF、必填幂等键、强 If-Match、规范 ProviderId、无查询及空正文，调用 A02 内部服务。成功返回 `202`、`job_id`、trace 和管理 Job Location；错误只映射公共安全码，不反射端点、Secret 或正文。
- `create_app` 仅增加显式 `ai_provider_test_router` 注入点；默认应用仍 404，Windows 生产组合仍未挂载。无网络/Secret 解密/客户数据外发。

## 验证与遗留

- 合同 3 项覆盖默认关闭、202 响应/trace/Location、缺少或错误前置条件、拒绝正文/查询以及权限/版本/Secret/策略错误安全映射。A02 隔离 PG 受权原子提交证据见独立进度文档；本项未运行 HTTP+PostgreSQL 合成端到端，故不把生产可用性标 PASS。
- 后端全量 1949 项运行、3 项跳过、0 失败；开发 wheel `plm_project_tool_backend-0.1.0.dev0-py3-none-any.whl` SHA-256 `0e2c2844cbc10750600c1ee6105c60077a245ad6435a1625dbcc2a341a250112`，仅开发构建而非发行包。
- 无 Migration、依赖或 Breaking API；撤显式路由注入可回退，持久历史保留。下一项 P04 Worker/Adapter 的受控执行安全，之后 P05 结果/激活和平台装配；正式信任源、真实外发、质量/三平台/Gate/UAT/发行仍待。
