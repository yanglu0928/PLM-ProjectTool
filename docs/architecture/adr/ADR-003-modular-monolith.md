# ADR-003：第一版采用模块化单体

## Status

`ACCEPTED_FROM_BASELINE / NOT_GATE_2_FROZEN`

## Date

2026-09-22

## Context

第一版面向单套部署、并发不超过 20 人、单服务器和私有化交付。系统包含多个实施业务域，但当前不存在需要独立伸缩、独立发布或跨团队自治的证据。微服务会增加离线安装、监控、网络、事务、升级和故障定位成本。

## Decision

1. 客户运行后端采用一个 FastAPI 模块化单体，模块按 `module-boundaries-v1-candidate.md` 划分并拥有各自 Domain 与数据状态。
2. 依赖方向固定为 `UI → API → Application Service → Domain → Repository / Gateway`。
3. 模块间只通过 Application Port、Domain Event、TraceLink 和 DTO/Contract 通信；禁止跨模块 Repository、ORM 或表写入。
4. Worker 是同一产品、同一模块 Contract 的独立进程，不构成微服务。
5. 使用一个 PostgreSQL 18/pgvector 实例；共享数据库不等于共享数据所有权。
6. 第一版单服务器部署，不引入服务注册、分布式事务、消息队列或独立 API Gateway 产品。

## Consequences

- 部署、备份、离线升级和本地诊断保持简单。
- 单进程内同步调用与事务边界清晰，长任务交给 PostgreSQL Job/Outbox。
- 模块必须通过静态依赖检查、目录约束和 Contract 测试保持边界；否则单体容易退化为无边界代码库。
- 单个 API 进程故障影响整个同步业务面，需通过进程守护、健康检查和恢复流程控制。
- V1 不承诺按模块独立伸缩或独立发布。

## Rejected Alternatives

- 微服务：没有当前容量或组织证据，且违反 V2.1。
- 模块各自数据库：增加部署与跨库一致性成本。
- 无边界分层单体：无法保护项目隔离、Trace、Review 和正式对象版本规则。

## Rollback / Change Rule

Gate 2 前可调整模块粒度，但不得破坏依赖方向和数据所有权。Gate 2 后如出现独立伸缩、隔离或发布的真实证据，必须提交 Architecture Change Request 和 L3 决策；拆分前先保持 Application Contract 稳定，不得直接把内部表暴露为服务接口。

## References

- `docs/architecture/module-boundaries-v1-candidate.md`
- `docs/architecture/application-contracts-v1-candidate.md`
- 《PLM项目实施辅助工具软件开发实施方案 V2.1》1.1、1.15、4.1
