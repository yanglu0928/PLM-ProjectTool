# GATE-3-A01：Platform Core 与 AI/RAG 客观证据收口审计

日期：2026-10-04。结论：`GATE_3_BLOCKED`。本审计只汇总已经形成且可反查的证据，不把合成数据、Schema/合同通过、单平台机制闭环或用户持续执行授权解释为 Gate 通过。

## 编码前/审计前检查

```text
当前Phase：Phase 2 Platform Core（依据 CR-SEQ-001 前置完成可独立验证的 Phase 3 基础任务）
当前WBS：GATE-3-A01
输入基线：V2.1 §Phase 2/3、Gate 2 冻结基线、ADR-009、EXC-P0-006、CR-SEQ-001、STATUS.md
前置任务：RAG-04-A06-P08 Windows 11 浏览器/生产组合/PG18.6 机制闭环完成
涉及模块：platform/auth/project/document/evidence/workflow/review/trace/audit/license、ai/rag/jobs/parser
涉及实体：仅审计既有实体与证据；不创建业务事实
涉及API：只核对冻结 /api/v1 与已经显式装配的运行合同；无 API 修改
涉及权限：核对 Session、License、ProjectId、Owner、逐次外发授权和人工确认边界
验收标准：Platform Core 完整模拟项目可走通权限与阶段；任意业务模块可通过统一接口使用 RAG/AI；既有质量、安全、性能及目标平台阻塞不得被弱化
风险：把合成 ACTIVE、Windows 11 单平台或历史已见集误写为业务质量/生产/三平台通过
```

## 证据矩阵

|审计项|现有证据|结论|关闭条件|
|---|---|---|---|
|统一 AI 入口|业务调用边界固定为 `AIService → ModelRouter → ProviderAdapter`；Provider/Model/Prompt/Task/Invocation、外发预览与逐次授权、第四 Worker 及前端工作台已完成 Windows 11 合成/隔离 PostgreSQL 验证|`MECHANISM_PASS`|不再新增旁路；正式 Provider 信任、目标服务账户和安装证据另行完成|
|统一 RAG 入口|DocumentChunk、Index/Build/Embedding、质量登记/激活、PROJECT FTS-only Retrieval、Result/Context/Cancel 已完成 Schema 0076～0090、生产组合与 Edge/PG18.6 闭环|`MECHANISM_PASS_WIN11`|不得把合成 ACTIVE/正文外推为业务质量；补正式 ACTIVE、目标账户密钥和平台证据|
|Project 隔离与失败关闭|PROJECT 查询强制 ProjectId、固定版本/Index/Chunk、当前成员和文档授权复核；无候选失败；query 不进 URL/storage；读取隐藏内部 fingerprint|`PASS_IN_TEST_SCOPE`|后续业务 Owner、性能、目标账户及发行回归继续保持相同边界|
|AI 建议态与人工确认|`NOT_FORMAL_FACT`、Evidence 定位、人工维护提示和 Review 强制边界已固化；AI 不可直接创建正式业务事实|`CONTROL_IMPLEMENTED`|真实 Capability/Handover 等 Owner 回接 Review/Trace/Workflow，并完成完整模拟项目阶段验收|
|Platform Core 总体验收|平台机制已大量完成，但 Capability/Handover/Survey/Requirement/Prototype/Solution/Plan 的正式 Owner 尚未全部存在，Review/Trace/Workflow 无法用真实业务固定版本完成完整模拟项目|`BLOCKED`|按 CR-SEQ-001 实现最小真实 Owner，回接 Review/Trace/Workflow，走通权限与六阶段|
|独立业务质量|历史 50 条 Top-5 49/50（98%）通过；分类 24/50（48%）、精确引用 37/50（74%）失败。当前集已见，R12 来源核查只有合同 0/7、技术协议 1/8，未生成新 50 条|`BLOCKED`|取得未参与调优的新来源，完成独立性与人工标签审查；新集分类 ≥90%、精确引用 ≥98%，并保留隔离/越界引用/失败关闭检查|
|性能|目标为 20 并发、非 AI GET P95 ≤500 ms、普通写 P95 ≤1 s、长 AI 提交 ≤1 s；尚无覆盖正式业务链与真实数据偏斜的合格报告|`NOT_RUN / BLOCKED`|在正式组合与代表性数据规模执行并留存报告|
|正式信任与进程部署|开发 wheel、合成 Vault/License/服务角色机制已验证；正式发行公钥、目标服务账户 Vault/ACL/CA、SCM 安装/重启和可信时间材料未提供|`BLOCKED`|完成生产等价信任材料供给、服务安装/恢复/撤权和失败关闭验收|
|平台兼容|Windows 11 为主要已验证环境；Windows Server 2025 有早期 PoC/部分底层证据但没有当前完整运行链；Debian 13 按用户要求暂不执行验证但仍是正式兼容目标|`PARTIAL / RELEASE_BLOCKER`|Release 前分别完成要求的平台安装、运行、升级与回归；不得用 Windows 11 外推|

## Gate 判定

Gate 3 不能关闭，判定为：

```text
GATE_3_A01_EVIDENCE_AUDIT_COMPLETE
GATE_3_BLOCKED_PLATFORM_OWNER_QUALITY_TRUST_PERFORMANCE
```

阻塞原因按独立责任域保留：

1. Platform Core 缺真实业务 Owner 回接和完整模拟项目阶段验收。
2. POC-03 历史分类/引用质量仍为 48%/74%，且没有满足来源配额的新独立 50 条。
3. 正式信任材料、服务账户/SCM、20 并发性能和当前目标平台发行证据不完整。
4. Debian 13 暂缓不等于兼容通过；Windows Server 2025 的早期 PoC 不能替代当前程序包验收。

## 后续执行

依据 `CR-SEQ-001`，Gate 3 保持阻塞并不要求停止所有独立工作。下一项进入 `CAP-01-A01`，先核清 GLOBAL CapabilityBaseline/不可变 Version/Item 的最小真实 Owner 与冻结 API/Schema 差距；Capability 是 Handover 固定输入，也是 Review/Trace/Workflow 回接的首个真实业务 Owner。该前置开发不宣称 Phase 4 或 Gate 3 已通过。

本项无代码、Schema、Migration、API、依赖、网络或客户数据外发。回滚只需撤销本审计记录；历史证据和 Gate 阻塞不得删除或改写。
