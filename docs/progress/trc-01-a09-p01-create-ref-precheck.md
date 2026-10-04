# TRC-01-A09-P01：Trace 创建冻结三字段引用前置核查

日期：2026-10-02；Phase 2；结论：**公开创建前置未满足；内部同事务输入可独立推进 P02**。输入冻结 API-02/DM-03、TRC-01-A05-P02/P03、CR-TRC-002 和 A08-P04 的 Owner Resolver；原 Gate 2 提交 `64cdf09` 不改。

## 证据

- 冻结 `TRACE_LINK_CREATE` 请求的 source/target 是 `resource_type/resource_id/version_id`，ProjectId 由路径给出；当前 `TraceCreateService` 只接受已解析的 `TraceEdgeShape`（含内部 Scope/Project）。HTTP 不能让客户端填写内部字段，也不能用独立事务预解析后再创建，因为固定版本、当前权限和提交将失去同事务约束。
- 已有 `TracePublicEdgeResolver` 可在调用方事务解析注册 Owner；目前仅 DOC-02 具备真实版本/Scope/Project 证明。CR-TRC-002 选择的方案 B 仍有效：通用创建 POST 不因单一 Owner 就正式挂载；其他业务 Owner 后续逐个接入。
- 当前创建服务在预留持久幂等收据**之前**调用 `prove_edge`，已创建边的来源后来 RESTRICTED/撤权时，历史同 Key 重放被端点新状态阻断；若把证明挪到收据之后，必须先显式复验当前 License（不能再只依赖端点 Owner 的间接 License 检查）、Session/CSRF 和 Project 角色，且不可把历史首次结果描述成当前 ACTIVE 状态。

## 决定与验证计划

P02 只增加内部三字段命令及同事务 Resolver，并修复创建收据顺序：当前 License、Session/CSRF、Project 授权后按原始三字段/关系预留收据；同 Key 首次结果只返回原 LinkId，核实收据与目标 Project 归属，不重新证明现已受限的端点；首次写入才在同一事务解析并重证固定版本、验环、去重插入和 Audit。原内部已解析命令继续兼容，亦须显式 License，历史重放安全规则一致。未知 Owner/跨项目/错误形状失败关闭；新 Key 对已失效端点不得创建。需单元、Permission/Exception、隔离 PG18 的首次/重放/失效来源/并发去重/Audit 回滚及回归。无 Schema/Migration/冻结 API 改动；不注入内部命令即可停止新写，既有历史和收据保留。实现选择记 DEC-20261002-620。

本项为静态核查，无产品代码或新业务测试，不判创建 HTTP、Gate 3、UAT 或可用程序包 PASS。下一项 `TRC-01-A09-P02` 实现并验证内部三字段创建及安全历史重放；公开路由继续遵守 CR-TRC-002，不在此项开放。
