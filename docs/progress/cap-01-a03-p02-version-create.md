# CAP-01-A03-P02：完整 Draft BaselineVersion 创建 Owner

日期：2026-10-05。结论：`CAP_01_A03_P02_VERSION_CREATE_PASS`。下一项：`CAP-01-A03-P03` Version Validate 报告Owner。

## 编码前检查

```text
当前Phase：Phase 2保持IN_PROGRESS；Gate 3保持BLOCKED
当前WBS：CAP-01-A03-P02
输入基线：冻结CAP_VERSION_CREATE、DM-05、Schema0091、CR-CAP-001、DEC-833
前置任务：P01 Baseline创建Owner通过
涉及模块：capability Version Owner/Repository；Document/Evidence只读Port；Schema0092守卫
涉及实体：Baseline锁、不可变BaselineVersion、CapabilityItem、DocumentRef、EvidenceRef
涉及API：内部Owner；HTTP仍未挂载
涉及权限：当前DeploymentAdmin/CSRF/License、强expected_lock_version、幂等、Audit
验收标准：完整聚合单事务、来源集合一致、Evidence同源、单调版本/明确supersedes、并发/回滚/历史拒降
风险：永久v0伪并发、半版本、跨来源Evidence、调用方自报摘要、Draft误作APPROVED
```

## 实现与偏差

新增Schema0092最小守卫：只开放Baseline业务字段完全不变时的`lock_version + 1`，用于冻结合同M控制；其余状态/来源/正式指针仍关闭。该调整不追写0091，并保留空历史可降、有历史拒降证据。

Version Owner严格校验最多500个Item及有界分类/文本/数组；每项必须有固定Document和ELIGIBLE Evidence。服务端通过Document Port锁定当前GLOBAL ACTIVE/AVAILABLE标准来源，通过Evidence Port锁定GLOBAL ELIGIBLE记录并要求与同Item DocumentVersion完全一致；调用方不能提交source hash或content hash。服务端分别计算不含并发令牌的内容指纹和包含expected lock的请求指纹。

写事务锁定Baseline，验证强ETag，单调生成version_no，自动固定上一版`supersedes_version_ref`，原子写Version/Item/Document/Evidence、推进Baseline锁、Audit和幂等收据。只创建DRAFT且Review/正式指针均为空；无HTTP、AI调用、资料自动导入、网络外发或新依赖。

## 验证

- Windows 11 / PostgreSQL 18.6：Migration/drift、真实DeploymentAdmin/CSRF/License、完整Document/Evidence来源、错误ETag、v1→v3单调升版与supersedes、同Key重放/冲突/双并发、Audit故障全回滚、撤权与0092历史拒降通过；标记`CAP_01_A03_P02_VERSION_CREATE_PASS`。
- Schema0091历史验证在0092 head重跑通过；首轮只因守卫错误消息从“Owner未安装”收紧为“内容不可变”使旧夹具文本断言失败，改为验证不可变语义后全新库完整重跑，产品规则未放宽。
- 定向12项通过，变更后相关8项复验；后端全量2542项通过、3项既有条件跳过、0失败。
- 开发wheel 909项，SHA-256 `83393f6584968a94a1efe5a86f27f7813ca92b7c077d1e0a8fafc1438fb164bd`；仅开发检查产物。
- `compileall`与`git diff --check`通过。

## 兼容、回滚与剩余边界

内部`0091 -> 0092`只替换守卫，无冻结API或依赖变化。无锁推进历史可降，有Version历史只向前修复；停用Owner关闭新Version但保留既有不可变快照。P03 Validate、Review/APPROVED、HTTP、前端、生产组合、真实内容确认仍未完成；合成来源不证明标准能力正确。Gate 3、正式信任、性能、Windows Server 2025当前链、Debian 13发行和可用程序包仍未完成。
