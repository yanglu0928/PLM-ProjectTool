# HND-02-A05-A03：Handover Action 生命周期写 HTTP

日期：2026-10-05。结论：`HND_02_A05_A03_ACTION_LIFECYCLE_HTTP_PASS`。下一项：`HND-02-A05-A04` Windows 写组合与 Win11/PostgreSQL 18 七写闭环。

## 实施结果

新增默认关闭的 START、SUBMIT、VERIFY、CLOSE、CANCEL 五个 Action 生命周期 Router，并在应用工厂增加独立可选注入点。所有路径统一强制受信 Origin、Session、CSRF、`If-Match`、`Idempotency-Key`、canonical UUID、严格白名单 JSON 与无 query；未注入时保持 404。

START只接收原因；SUBMIT接收固定响应DocumentVersion、SUBMISSION Evidence与原因；VERIFY接收VERIFICATION Evidence与原因；CLOSE接收Resolution Trace与原因；CANCEL接收原因。HTTP只投影既有Owner返回的事件、状态、固定引用、时间与ETag，权限、当前受理人、项目隔离、Evidence/Trace资格、状态机、Audit、收据和事务不在传输层重写。

响应明确保持`SUBMITTED != VERIFIED != CLOSED`：SUBMIT不返回关闭字段，VERIFY不返回关闭字段，只有CLOSE返回`closed_at`和`resolution_trace_ref`。

## 客观验证

- 新增合同3项，覆盖默认五路404、五条成功投影、安全/并发/幂等头、未知字段、非canonical Trace与状态错误映射。
- 后端全量2712项通过、3项跳过。
- Windows Python 3.13 wheel构建及wheel内生命周期Router导入通过；SHA-256 `39aeb417c9f1aa3b5ef9202ccaf129abd3a895f919204787844daaee10a4a900`。

## 兼容、回滚与未关闭项

无Schema、Migration、冻结URL、依赖、配置、Secret、网络、外发或客户数据变化。撤生命周期Router可选注入即可恢复404，合法业务历史不变。当前仍未在Windows生产组合挂载；真实Win11/PG七写、正式信任、Server 2025、前端写工作台、浏览器、Gate 3、UAT与发行继续开放。
