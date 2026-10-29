# CR-EXEC-027：A17 Edge harness 适配受限 HTTPS Origin

- 日期：2026-10-29
- 状态：已实施，待托管验收
- 来源与证据：GitHub hosted Windows 2025 run 40827041759 的基础测试/构建、候选包组装、PG lifecycle 和前置业务链通过。日志确认 CR-EXEC-024 Section fixture、CR-EXEC-026 coverage restore、Outline Review API 均越过。随后 run-edge-browser.mjs 在启动 Edge 前抛出 “Owned P51-A17 synthetic identities and non-C RUNNER_TEMP child required”。该 guard 将传入 origin 硬编码为 https://localhost:<port>，但本 Harness 被 A17 复用在已有 packaged HTTPS flow 下，origin 来自上游 context；当前汇总错误没有单独指出具体谓词值。
- 问题：浏览器 harness 的 HTTPS origin guard 沿用了独立 localhost smoke 形状，未与 packaged runner 的受控 HTTPS origin 参数保持一致。临时目录、合成账号值按 A17 调用端显式设定，runner-temp 静态检查也已通过。
- 方案比较：A. 去掉 origin 校验；B. 仅允许 packaged HTTPS fixture 明确使用的 loopback 或固定测试域名主机（localhost / plm.example.test），要求 scheme=https、无路径/凭据/查询，并拒绝其他主机及 HTTP。选择 B，保留严格主机边界并兼容 packaged origin。
- 基线差异：只改 A17 Edge harness 的验证 URL host allowlist，不改产品网络配置、Caddy、TLS、登录来源策略或业务 API。
- 影响与风险：应用启动后请求仍走上游传入 HTTPS origin；浏览器忽略自签名证书只在本次 disposable 验收配置范围内。若 packaged origin 实为 allowlist 外主机则继续 fail closed，先读取日志诊断，不扩大 allowlist。
- 实施：用 URL parser 严格校验 HTTPS、hostname 必须精确等于 localhost 或 plm.example.test，且 parsed.origin 必须与入参完全一致；Malformed URL 失败关闭。其余 D-drive RUNNER_TEMP 子目录和合成身份约束不变。\n- 回滚：恢复单一 localhost:port 正则；不影响产品包和验证数据库。
- 验证计划：hosted Windows 2025 全量工作流；确认 Node guard 接受实际预期 HTTPS origin、仍拒绝 HTTP/其他 host/URL 路径，随后真实 Edge PlanVersion Create/GET/Validate/SubmitReview 与 PostgreSQL readback/decisions=0、清理和 candidate integrity 均通过。
- 执行边界：仅 GitHub hosted runner 与合成数据；不在用户本机/C盘运行项目代码，不外发客户资料或 Secret。
