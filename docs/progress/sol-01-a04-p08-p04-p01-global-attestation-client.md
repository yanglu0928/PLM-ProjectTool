# SOL-01-A04-P08-P04-P01：GLOBAL 人工脱敏确认前端严格客户端

日期：2026-10-09；结果：`GLOBAL_ATTESTATION_CLIENT_PASS`，客户端封装/合同测试通过；尚无人工核查页面，也不代表真人已确认。

编码前检查：Phase 2；WBS P08-P04-P01；输入 CR-SOL-009、P08-P02 增量 API 合同与 P03-P05 Windows 显式组合。前置后端 Preview/Confirm/Revoke HTTP/PG 已通过。仅涉及前端 Auth CSRF 传输和 Solution 严格客户端，不改后端、Schema、依赖或冻结接口。涉及固定 Document/Evidence 来源、确认/撤回收据；权限要求当前 DeploymentAdmin Session。验收为白名单路径、CSRF 不外泄、来源/指纹/Trace/时间/固定身份响应严格校验、异常不盲目重试；风险为客户端检查不能替代服务端授权或人类脱敏判断。

新增 `ReferenceDeidentificationClient`，Preview/Confirm/Revoke 通过 `SessionClient` 私有 CSRF、同源 no-store 传输；Confirm 强制预览 64 位来源指纹和明确声明常量，调用方保留原幂等 Key；响应仅接受固定字段、当前来源有序 Document 根/版本与 Evidence ID、合法 UTC 时间和 Trace。漂移 409 给出重新预览指引，网络不确定返回明确未确认状态，不自行换 Key 或重试。客户端仅是业务页面未来使用的传输能力，不自动确认或创建 GLOBAL Reference。

验证：定向 4 通过；前端全量 `104 files / 1618 tests`、typecheck/build 通过。既有主入口包约 791 kB，Vite >500 kB 警告仍在。本项无数据升级；回滚可撤去未使用客户端和新增 Auth 传输，后端确认历史不变。未验：逐项打开文档/Evidence、显式勾选页面、Edge、真人业务确认、正式 License/目标账户、Server 2025、20 并发/Gate 3/发行；Debian 13 依用户指令跳过。TraceLink：CR-SOL-009 → P08-P02 → P03-P05 → P04-P01 客户端/测试 → P04-P02 UI。
