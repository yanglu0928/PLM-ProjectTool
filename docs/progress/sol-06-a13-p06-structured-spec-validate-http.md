# SOL-06-A13-P06：结构化专项 VALIDATE HTTP 合同

日期/版本：2026-10-19 / `0.1.0-dev.0`。状态：`STRUCTURED_SPEC_VALIDATE_HTTP_CONTRACT_PASS`；只完成默认关闭的 HTTP Router 与投影合同，不表示 Windows 生产组合或真实 HTTP/PG 已装配。

## 编码前检查

|项目|结论|
|---|---|
|当前 Phase / WBS|Phase 2 / `SOL-06-A13-P06`|
|输入基线|冻结 API-04 `SOL_SPEC_VALIDATE` 路径/角色/S,L,C,I,A；A13-P02 报告；A13-P05 内部受权 Service|
|前置任务|内部 Service 已具备授权、License、幂等、Audit 和报告防伪，可增加不含业务逻辑的 HTTP 边界|
|涉及模块/实体|Solution API；无实体或数据库变化|
|涉及 API / 权限|POST `/api/v1/projects/{project_id}/structured-solution-specs/{spec_id}:validate`；可选 Router，默认应用保持 404|
|验收标准|受信 Origin、Session/CSRF、Idempotency-Key、无查询/空正文、UUID 路径；200 返回完整八维/类型化报告、首次观察 Trace 与本次 Trace 分离；错误统一映射|
|风险|200 被误读为业务通过；重放覆盖首次 Trace；缺字段或类型检查失序；默认应用意外开放；Owner 内部错误泄漏|

## 实施与验证

- 新增 `create_structured_spec_validate_router`，仅显式注入时注册冻结路径。边界先校验 Origin、Session/CSRF、无查询、Idempotency-Key、两个 UUID 和严格空正文，再在线程池调用内部 Service；默认 `create_app()` 继续返回 404。
- 200 响应投影固定版本/系列/类型/状态、content/payload fingerprint、四类引用计数、八维 facts、按类型固定顺序的 checks、`valid`、`ready_for_review`、issue codes、Audit 与观察时间。顶层 `trace_id` 是本次 HTTP 请求，`data.observation_trace_id` 保留首次观察，响应 `Cache-Control: no-store`。
- Owner 的权限/项目/License/幂等/验证错误统一映射为现有错误信封；报告项目或版本身份不符一律 503，不回显异常或 Traceback。
- 新增合同 4 项、13 子例；与 Section VALIDATE 和 P05 Service 联合定向 17 项、26 子例通过。后端全量：`3724 passed, 3 skipped, 5809 subtests passed in 68.03s`。
- py_compile、`git diff --check` 通过。Python 3.13.15 开发 wheel：1408 个条目，Router 入包 1 份；SHA-256 `26b84bb8501a0c149b352c7fe743a000eb55e7f0dce59ada51a0b7705511ffd2`。
- 无 Migration、外部 AI/网络、客户数据或 Secret 外发。

## 兼容、升级、回滚与遗留

本项只增加默认关闭的可选 Router 与 `create_app` 可选参数；无 Schema、冻结路径/角色/字段破坏、License 权益、依赖或旧数据变化。不注入 Router 即回滚，既有 Audit/收据历史保留。开发 wheel 不是 Pilot 或正式发行包。

Windows 生产组合、真实 HTTP/PG、页面/Edge 尚未实现。Trace、非空 Artifact 及非结构类型 Owner 缺口不因 HTTP 开放而改变；正式信任、Windows Server 2025、Debian 13、性能、Gate 3、Pilot 与正式发行状态不变。

Next：`SOL-06-A13-P07` 将 VALIDATE Router 仅装入 Windows 显式读写模式，并用真实 Session/License/Owner/Audit/收据/PostgreSQL 18.6 验证 HTTP 首次观察与重放；默认/只读模式保持关闭。
