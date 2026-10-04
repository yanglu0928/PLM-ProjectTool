# WBS 1.07 JSON log 验收记录

- 日期：2026-09-24
- 阶段：Phase 1 架构冻结与基础工程
- 状态：PASS
- 前置：WBS 1.02、1.06 PASS；Gate 2 基线未修改。
- 追溯：WBS 1.07 → 已冻结安全/文件/任务运行边界的三类日志隔离与最小字段 → `DEC-20260924-066` → 平台日志器、App Factory 注入、错误处理接入 → Unit/Contract 测试。

## 交付与验证

新增可注入的 `StructuredLoggers`，分别写 Application 与 Integration JSON 行；字段由固定 schema 组装，事件、集成类型和 Provider 由目录控制，TraceId 只接受规范 UUID。Application 可记录时间、级别、组件、TraceId、安全错误码、耗时；Integration 可记录类型、Provider、Invocation ID、耗时、重试及脱敏结果。Audit 不写这两类日志，后续独立模块负责数据库审计。

未分类 API 异常只记录 `SYSTEM_INTERNAL` 和与错误响应一致的 TraceId，不记录异常原文、请求/响应正文、SQL、路径或客户字段。默认 Application 写 stdout、Integration 写 stderr；部署时可注入受控流。Windows 11 / Python 3.13.15 全量后端测试 48/48 PASS，包括日志分流、字段白名单、恶意值拒绝、日志故障时安全响应和 API 异常端到端脱敏；业务 API、数据库变更及客户数据外发均为 0。

## 兼容性、升级与剩余风险

当前为未发行基础工程，部署无需 Migration。WBS 1.08 才会实现全请求 TraceId 与耗时上下文；现在只有未分类 API 失败接入运行日志。日志收集器、轮转、保留期和访问控制尚待 Release 配置，不将 stdout/stderr 文件作为 Audit。Windows Server 2025 与 Debian 13 本任务未验证。
