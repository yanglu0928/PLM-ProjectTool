# SOL-01-A04-P02-P02：Reference Evidence 固定来源证明适配

日期：2026-10-08；结果：`EVIDENCE_PROOF_ADAPTER_INTERNAL_PASS`，不是 Reference 写 Owner/HTTP 或完整物理文件端到端 PASS。

当前 Phase 2；前置为 CR-SOL-005、A04-P01 资格合同和 A04-P02-P01 Document 适配。Evidence 模块新增 Reference 专用 GLOBAL 固定来源证明：同一 caller transaction 验证当前管理员、`GLOBAL/ELIGIBLE` 的锁定 Evidence、精确 DocumentVersion、定位器、Document 固定来源受权/物理摘要、整文件或 ParseResult 节点内容指纹。GLOBAL 允许 `REFERENCE_MATERIAL` 与 `STANDARD_CAPABILITY`，但不修改原标准能力专用的“目标项目 PM + STANDARD_CAPABILITY”服务。PROJECT 仍复用 Evidence 原有固定来源服务；Solution 适配仅接受当前有效的项目 PM/ImplementationMember Proof，核验 Scope/Project/版本/指纹后转交 A04-P01。

没有新增公开 API、角色、Schema、Migration、依赖或外发；0139 DML 仍关闭。回滚可移除新内部服务/适配，不影响旧 GLOBAL 标准能力路径。定向含旧服务 `20 passed, 3 subtests passed`；后端全量 `3282 passed, 3 skipped, 4815 subtests passed`。本项使用合成 Port 验证事务、拒绝分支和节点；未重跑真实 PG/磁盘/HTTP 的 Reference 组合，现有 Evidence/Document 服务各自的真实验证不能替代该组合。人工 GLOBAL 脱敏确认 Port 与原子 Owner 仍待，Gate 3 保持 BLOCKED。

TraceLink：CR-SOL-005 → A04-P01/P02-P01 → 本服务/适配/单测 → DEC-20261008-1103 → A04-P02-P03。
