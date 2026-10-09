# SOL-03-A04-P02-P02-P02-A02：固定 Evidence 的内部现时证明

日期：2026-10-09。结果：`SOL_03_A04_P02_P02_P02_A02_EVIDENCE_USE_PROOF_PASS`；仅 Evidence 自身当前资格、固定 Locator/节点内容指纹通过，Solution 完整来源组合与目录版本写仍未开放。

## 编码前检查

- 当前 Phase/WBS：Phase 2 Platform Core / SOL-03-A04-P02-P02-P02-A02。输入：Gate2 DM-05/API-04、CR-SOL-016、已验 Document 固定文件/Parse 内部证明、Evidence 自有 `get_for_trace` 共享锁及节点 `prove_verified`。
- 单一问题：ReferenceVersion 固定 Evidence 被目录使用时，如何由 Evidence 模块重新证明其当前为 ELIGIBLE，Locator 仍指向已验 Document 或解析节点，内容指纹未变化，且不向 Solution/UI 泄露位置和解析字节。
- 模块/实体/API/权限：仅 Evidence Application 内部服务；EvidenceRow/DocumentVersion/ParseResult 跨模块通过既有 Application Interface，不直读 Document 内部表；无新 Schema、公开 API、角色或依赖。
- 验收：PROJECT/GLOBAL、DOCUMENT 与解析节点正例；跨项目、撤回、不合法 Locator、Document 物理篡改、Parse 结果篡改、摘要不一致及端口异常失败关闭；定向/隔离 PG/全量回归。
- 风险：固定 Evidence 通过仍不能单独证明 ReferenceRoot 当前 ELIGIBLE 或 GLOBAL 脱敏确认未过期；这些由后续 Solution 组合负责。

## 实施与验证

新增 `ReferenceUseEvidenceProofService`：先通过 Evidence 自有 Repository 共享锁读取仅 ELIGIBLE 行，再验证 Scope/Project、固定 DocumentVersion 和 Locator；DOCUMENT 使用 Document 安全快照摘要，非 DOCUMENT 使用 Document 内部 Parse 结果及原 `ParsedNodeEvidenceProofService.prove_verified` 重新定位节点。将计算指纹与 EvidenceRow 固定指纹做恒时比较，仅返回 EvidenceId、DocumentVersionId、Scope/Project 和指纹；Locator、文件路径、解析字节及管理员凭据不返回。

定向 4 项通过。Win11 两套隔离 PG18.6 真实来源夹具中 PROJECT 文档 Evidence、GLOBAL 文档 Evidence 与解析节点、跨项目、文档与 Parse 文件篡改拒绝均退出0；现有上游夹具的 Evidence 撤回负例亦退出0，但本新服务撤回负例目前由其 Repository `ELIGIBLE` 过滤和定向 Mock 覆盖，待完整组合联测再直接验证。后端全量结果见版本说明。

兼容/回滚：无 DB/Migration、公开 API 或依赖变化；不接线/撤服务即可回滚，既有 Evidence 历史不动。下一项 `SOL-03-A04-P02-P03` 在 Solution 内组合当前资格账本、Document/Evidence 真实来源指纹重算和 GLOBAL 当前确认，验证项目角色不获 GLOBAL 原文、资格/确认撤回及并发，再考虑 OutlineVersion Owner/Guard。Gate3 仍 BLOCKED。

TraceLink：Gate2 DM-05/API-04 → CR-SOL-016 → Document/Parse 内部证明 → 本 Evidence 证明 → Solution 全来源组合 → OutlineVersion Owner。
