# SOL-03-A04-P02-P02-P02-A01：固定解析结果的内部现时证明

日期：2026-10-09。结果：`SOL_03_A04_P02_P02_P02_A01_PARSE_USE_PROOF_PASS`；仅 Document 模块的解析结果证明，Evidence Locator/节点指纹仍未形成最终业务证明。

## 编码前检查

- Phase/WBS：Phase 2 Platform Core / `SOL-03-A04-P02-P02-P02-A01`。输入：Gate2 DM-05/API-04、CR-SOL-016、P02-P02-P01 Document 物理来源证明、现有 ParseRecord/ResultRef 只读锁与本地安全结果存储。
- 单一问题：GLOBAL/PROJECT 固定 Evidence 指向解析节点时，Document 如何在调用者事务内证明固定 ParseRecord 已 SUCCEEDED、结果文件未篡改且确实来源于已验证的 DocumentVersion，而不要求项目用户获 GLOBAL 原文权限。
- 模块/实体/API/权限：仅 Document Application 的内部 Parse 证明；复用 Document 自有 Repository 与 LocalParseResultStorage，无公开 API、数据库迁移或角色变更。仅 Evidence 内部校验器可消费 VerifiedParseResult，Solution/UI 不接收解析字节。
- 验收/风险：固定 Document/Parse ID、Scope/Project、结果摘要/大小、schema/source SHA/parser profile/version 绑定、读后重证及篡改拒绝；风险为将“合法 ParseRecord 元数据”误当作未篡改内容。

## 实施与验证

新增 `ReferenceUseParseProofService`，先调用 Document 固定文件证明，再共享锁取得 ParseRecord/ResultRef，使用现有安全结果存储验证文件字节和 SHA-256；解析 JSON 并核对 schema、文档版本、源 SHA、解析器信息和节点数组，最后复验文档及结果元数据。返回的 `VerifiedParseResult` 仅用于后端 Evidence `prove_verified`，内容字段不进入公开响应。

定向 4 项/3 子例通过。Win11 临时 PG18.6 + 真实 GLOBAL 文件/解析节点夹具中正例、结果字节篡改拒绝、恢复再验均退出0；后端全量 3421 通过/3 跳过/5226 子例（2 条既有警告）。无 Migration/公开 API/依赖变化，撤未接线服务可回滚，解析历史不变。

下一项 `SOL-03-A04-P02-P02-P02-A02` 由 Evidence 模块验证当前 ELIGIBLE 行、固定 Document 或 Parse 节点 Locator 与存储指纹，并只返回不含 Locator/内容的摘要；再与 ReferenceRoot 账本、Document/Parse 及 GLOBAL 确认组合。未完成前 OutlineVersion CREATE Guard 不开放，Gate3 仍 BLOCKED。

TraceLink：Gate2 DM-05/API-04 → CR-SOL-016 → Document 固定文件证明 → 本解析证明 → Evidence 节点证明 → Solution Owner。
