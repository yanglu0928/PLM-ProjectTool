# HND-01-A03-P02：完整 DRAFT HandoverAnalysisVersion 创建 Owner

日期：2026-10-05。结论：`HND_01_A03_P02_VERSION_CREATE_PASS`。下一项：`HND-01-A03-P03` AnalysisVersion Validate Owner。

## 编码前检查

```text
当前Phase：Phase 2保持IN_PROGRESS；Gate 3保持BLOCKED
当前WBS：HND-01-A03-P02
输入基线：DM-05、API-04、Schema0096、CR-HND-001、DEC-847～849
前置任务：Analysis identity创建Owner与固定PROJECT来源已通过
涉及模块：handover及document/evidence/capability/ai/project/auth/license/audit只读Port
涉及实体：HND-02完整不可变DRAFT Version及owned source/item/evidence/capability/option/AI refs
涉及API：冻结HND_VERSION_CREATE语义；本项不挂HTTP
涉及权限：ProjectManager、ImplementationMember；ACTIVE Project；强ETag
验收标准：完整快照单事务、固定Approved Capability、NEED_CONFIRM提示、幂等并发、supersedes
风险：无关AI/跨项目Evidence进入快照；部分子表提交；缺资料被误当关闭；父锁被任意改写
```

## 实施结果

- 新增完整 DRAFT Version Owner：固定 Project DocumentVersion 集合必须与 identity 来源摘要一致；Capability 必须为当前 ACTIVE Baseline 的精确 APPROVED Version，逐项引用只接受其中 AVAILABLE Item。
- PROJECT Evidence 必须 ELIGIBLE、属于同项目并定位到固定来源文档；AI provenance 只接受同项目、SUCCEEDED 的 GAP_ANALYSIS Task。AI Task 可为空且仅作为建议来源，不赋予 Item 正式状态。
- 六类 Item 均以 CANDIDATE 写入。`NEED_CONFIRM` 强制问题、影响、建议、至少两个选项，并要求每个输入字段提供名称、格式、示例和必填标志；非缺资料项至少一个 Evidence。`source_missing=true` 仍不构成闭环。
- Schema0097 只允许父 Analysis 不可变元数据下锁版本精确加一；Version及子项保持不可变。创建写入、Audit、幂等收据和第二次 License 检查同事务，后续版本形成单调 version_no/supersedes 链。

## 验证与证据

- Windows 11/PostgreSQL 18.6 临时库：空历史0097降升、drift、错误Capability/AI拒绝、完整Document/Capability/Evidence/AI快照、同key重放/冲突、两线程并发、Audit失败整笔回滚、三版supersedes/锁推进和历史拒降均通过；临时库已删除。
- 0096历史Schema验证在0097 head下重新通过；既知pgvector表达式与计算默认值比较器警告不形成新增drift。
- 定向24项、后端全量2610项通过，3项按既定环境条件跳过；`compileall`和`git diff --check`通过。
- 最终开发wheel解包定向24项通过，SHA-256 `ce1fd1c07600ef9ef05146c772d8c760222a096c50bf2973a2aeac955ccd2188`。

## 兼容、回滚与未关闭项

内部`0096 -> 0097`只替换触发器函数，无公开HTTP、依赖、配置、网络或客户数据外发。无Version历史可降回0096；有历史拒降。停止装配服务可关闭新Version创建，已形成快照/Audit/收据保留。

P03 Validate报告、Review正式化、HND-03 Action、HTTP/UI/Workflow与真实质量仍待；任何DRAFT和CANDIDATE不等于客户确认或正式业务事实。
