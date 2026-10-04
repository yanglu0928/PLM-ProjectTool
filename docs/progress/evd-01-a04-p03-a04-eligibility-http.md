# EVD-01-A04-P03-A04：资格 POST 可选 HTTP 合同

日期：2026-10-01；Phase 2 Platform Core；结论：`OPTIONAL_HTTP_CONTRACT_PASS / PLATFORM_DB_PROOF_OPEN`。

输入为冻结 `EVIDENCE_SET_ELIGIBILITY` 项目/全局路径、S/L/C/I/M/A、内部资格命令；前置已有 Session/CSRF/Origin、Idempotency-Key 和强 `If-Match` 共用解析。范围仅 Evidence 可选路由及 `create_app` 注入点，不接正式 Windows 组合，不改变 Schema/冻结 API。

项目与 GLOBAL POST 仅在显式注入路由后开放；默认应用仍404。入口先验证可信 Origin、当前 Session+CSRF、幂等键、强单值 If-Match、资源身份和仅含 `eligibility_state`/`reason` 的请求体，再构造人工资格命令。响应仅提供资格状态、理由、EvidenceId、ETag 与 trace_id，不返回来源正文/路径。错误按冻结公共错误映射；未知内部异常不回显。

验证：HTTP合同4项覆盖默认关闭、项目/全局成功、缺少/弱/多值头、畸形Body与受限错误；后端全量1797项通过、3项跳过；wheel构建通过。测试使用合成 Session/服务，未验证实际PG18事务、真实角色/来源、正式平台装配、Windows Server 2025或Debian；不得据此关闭 Gate3。回滚为不注入路由，保留已有内部实现/历史。
