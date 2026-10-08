# SOL-01-A04-P01：ReferenceSolution 来源资格合同

日期：2026-10-08；结果：`INTERNAL_CONTRACT_PASS`，不是 ReferenceSolution 真实 Owner/PG/HTTP PASS。

```text
当前 Phase：Phase 2，依 CR-SEQ-001 前置 Solution 基础
当前 WBS：SOL-01-A04-P01
输入基线：冻结 DM-05、API-04，CR-SOL-004/005，Schema 0139
前置：Document/Evidence 已有受权固定来源证明；GLOBAL 标准能力 Proof 用途更窄，不直接复用
涉及模块：Solution Application 合同；Document/Evidence/Admin 仅通过待装配 Port
涉及实体：ReferenceVersion 的固定 DocumentVersion/Evidence 来源与 GLOBAL 人工脱敏确认
API/权限：无新公开 API；PROJECT/PM、IM 与 GLOBAL/DeploymentAdmin 的实际授权由后续 Port 执行
验收：范围/来源/摘要/确认指纹/重复/异常失败关闭，定向及后端全量回归
风险：可信 Document/Evidence/人工确认 Port 尚未实现/装配，0139 写入继续闭锁
```

增加内部请求与受权证明 DTO/Port、同事务来源资格服务。`PROJECT` 必须精确绑定项目；`GLOBAL` 必须另有 DeploymentAdmin 人工脱敏确认 Proof，且确认绑定本次来源集合和分类的 SHA-256 指纹。对来源的资格只接受上游 Proof，不能由客户端提供；完整性异常与不可用均失败关闭。没有调用外部 AI 或外发客户内容。

验证：定向 `7 passed`；后端全量 `3270 passed, 3 skipped, 4815 subtests passed`。无 Migration/API 变更。真实 Port 适配/人工确认记录/原子写入未验，不能将本合同当已开放功能。TraceLink：CR-SOL-004 → CR-SOL-005 → 本服务/测试 → DEC-20261008-1101 → A04-P02。
