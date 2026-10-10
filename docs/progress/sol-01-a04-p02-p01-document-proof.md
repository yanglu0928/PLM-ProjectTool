# SOL-01-A04-P02-P01：Reference DocumentVersion 身份与固定来源适配

日期：2026-10-08；结果：`DOCUMENT_PROOF_ADAPTER_INTERNAL_PASS`，不是完整 Reference Owner/HTTP PASS。

```text
当前 Phase：Phase 2，依 CR-SEQ-001 前置 Solution 基础
当前 WBS：SOL-01-A04-P02-P01
输入基线：冻结 DM-05/API-04、CR-SOL-004/005、Schema0139
前置：A04-P01 来源资格合同；Document 固定来源证明与真实文件校验服务已存在
涉及模块：Document 内部身份 Port、Solution Infrastructure 适配；不改既有标准能力证明
涉及实体：DocumentVersion 固定引用
API/权限：无公开 API/新角色；实际权限仍由 DocumentFixedSourceProofService 验证
验收：同事务版本身份查找、跨项目/Scope拒绝、固定来源返回范围与摘要核对、后端回归
风险：完整 Document 字节/授权的端到端组合未在本项重测；Evidence 和人工脱敏 Port 未完成
```

Document 内部新增只返回 `(document_id,document_version_id,scope,project_id)` 的版本身份查询，不暴露内容或存储位置，不把查询结果视为授权。Solution 适配将该身份交给现有 Document 固定来源证明服务，要求同一 caller transaction，并再次核对范围、版本、类型和摘要；资格合同随后按类别决定是否允许。既有 GLOBAL `STANDARD_CAPABILITY` 专用路径未放宽。

同时修正 A04-P01 合同遗漏：GLOBAL 人工脱敏 Proof 必须满足 `confirmed_at <= now < expires_at`，过期或未来确认拒绝。该修复无迁移/API 变更。

验证：Document 适配与 A04-P01 定向 `12 passed`；Win11 一次性 PG18.6 身份查询及 0138 前序迁移/约束复跑 PASS；后端全量 `3275 passed, 3 skipped, 4815 subtests passed`。一次性 PG 已停止清理；测试夹具 DocumentVersion 不含真实 FileObject，因此不能据此宣称物理文件组合 PASS。现有 Document 固定来源单元测试覆盖该服务本身，完整 Reference 组合留后续。TraceLink：CR-SOL-005 → A04-P01 → 本适配/验证 → DEC-20261008-1102 → Evidence/人工确认/Owner。
