# WFL-01-A07-P07-A04：Workflow Checklist 冻结 HTTP 合同与安全适配

日期：2026-10-06。结论：`WFL_01_A07_P07_A04_CHECKLIST_HTTP_PASS`。

## 完成范围

- 实现冻结 `WORKFLOW_CHECKLIST_RECORD` POST 路径，仅在组合根显式注入 Router 时开放，默认应用仍返回 404。
- 写入边界依次强制可信 Origin、Session/CSRF、Idempotency-Key、强 If-Match、无 Query、唯一 JSON key、精确字段集、canonical UUID 和 `PASS/FAIL/WAIVED` 传输枚举。
- HTTP 层不判断 Handover 资格、项目角色或 WAIVED 例外；只适配 A03 Owner 命令与安全错误。冻结 `WORKFLOW_GATE_NOT_SATISFIED` 注册为 409。
- 成功回执投影不可变 Record 身份、Item/Workflow 记录版本、服务端 ReviewRound 引用、理由/影响和 UTC；ETag 单独反映当前 Workflow 版本，因此历史幂等重放不伪装成当前 Record。

## 兼容与回滚

- 不修改冻结 URL/请求 DTO，无 Schema/Migration、角色、依赖、Secret、客户数据或外发变化。回执为对“checklist projection”的最小明确实现，不返回用户凭据、摘要或 Owner 私有事实。
- 回滚可撤销可选 Router 注入点和错误注册；内部 A03 命令、历史 Record/Audit/receipt 不改写。

## 验证证据

- 新增合同 5 项，相关定向 19 项通过；覆盖默认关闭、成功投影、FAIL 空证明、安全/格式拒绝、冻结错误映射及返回 503 时不泄漏内部异常。
- 首轮合同证据发现传输层可将 `PENDING` 构造成命令；已在调用 Service 前限定三个冻结结果并重跑通过。
- 后端全量：2750 项运行、3 项按既有条件跳过，0 失败。
- 开发 wheel 包含新 API 模块，SHA-256 `e8cd5e076e44c3bdf95b1e0925aa1689ddd9eb2acf631cc6332f284b2d25af8d`；仍不是可发行程序包。
- 本项使用合同替身，不声称 Windows 生产组合、真实 HTTP/PG、Gate 3、发行或 UAT 通过。

下一项：`WFL-01-A07-P07-A05` Windows 生产组合与真实 HTTP/PostgreSQL 闭环。
