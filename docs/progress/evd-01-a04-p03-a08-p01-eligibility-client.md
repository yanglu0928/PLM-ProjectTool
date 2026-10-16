# EVD-01-A04-P03-A08-P01：前端资格当前版本与人工提交客户端

日期：2026-10-01；Phase 2 Platform Core；结论：`FRONTEND_CLIENT_PASS / UI_OPEN`。

输入为冻结资格 API、已验证的后端强 If-Match/Idempotency/Session+CSRF、Evidence Viewer 固定来源描述。前置：SessionClient 已持有 CSRF，Evidence GET 返回强 ETag，Viewer 能核验原文；范围仅 Auth 受控 POST 传输和 Evidence 安全客户端，不做 UI 自动裁定。

客户端在人工操作前新取 Evidence GET，验证响应体与 ETag 一致，仅保留 EvidenceId、DocumentId、固定 VersionId、资格和 ETag；提交前核对 Viewer 的三项身份完全一致、当前状态 CANDIDATE、人工理由和原幂等键。SessionClient 使用同源受控 POST、CSRF、Idempotency-Key、If-Match。200 仅作为首次回执，不充当当前状态证明；网络/响应异常标记不确定，不自动更换 Key 或重试。调用方必须在 UI 中保留原操作记录并重新核对。

定向4项测试覆盖强 ETag、同源头、来源不符、版本冲突和传输不确定；前端全量1029项、typecheck/build通过。尚未提供人工按钮/表单、真实浏览器与正式目标账户验收。无 API/Schema 变更，回滚撤未接入页面的客户端。
