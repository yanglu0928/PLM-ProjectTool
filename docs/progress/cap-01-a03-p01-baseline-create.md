# CAP-01-A03-P01：CapabilityBaseline 内部创建 Owner

日期：2026-10-05。结论：`CAP_01_A03_P01_BASELINE_CREATE_PASS`。下一项：`CAP-01-A03-P02` 完整 Draft BaselineVersion 创建 Owner。

## 编码前检查与拆分

```text
当前Phase：Phase 2保持IN_PROGRESS；Gate 3保持BLOCKED
当前WBS：CAP-01-A03-P01
输入基线：冻结CAP_BASELINE_CREATE、DM-05、Schema0091、CR-CAP-001
前置任务：CAP-01-A02 Schema0091/ORM通过
涉及模块：capability应用/领域/仓储；通过Document公开读Port重验来源
涉及实体：仅CapabilityBaseline Identity；不创建BaselineVersion/Item/Review
涉及API：内部Owner；HTTP仍未挂载
涉及权限：当前有效DeploymentAdmin Session+CSRF、有效License、部署级幂等与Audit
验收标准：严格输入、当前GLOBAL标准来源、原子Baseline/Audit/收据、重放/冲突/并发/回滚/撤权
风险：把归档/Project/损坏来源写入基线；重复创建；把空正式指针误报为APPROVED
```

冻结合同把 Baseline 身份创建、完整 Draft Version 创建和 Version Validate 定义为三个独立 Operation。为遵守一个 WBS 一个明确问题，A03细分为P01～P03；不改变冻结路径、字段语义或总体顺序。P01只实现`CAP_BASELINE_CREATE`内部Owner，P02/P03分别处理版本创建和无状态验证报告。

## 实现

新增稳定且带域分隔的来源集合摘要规则，以及只接受1～500个不重复 GLOBAL DocumentVersion 的来源验证器。验证器通过 Document 模块公开读Port锁定当前 Version/File，并要求 Document 为 ACTIVE `STANDARD_CAPABILITY`、Version/File 为 AVAILABLE且完整性元数据一致；Capability不导入Document ORM或直写其表。

创建Owner先验证Session/CSRF，再验证License，写事务内重新验证DeploymentAdmin、幂等和当前来源；随后原子写入 ACTIVE/`v0`/无正式版本指针的Baseline、`CAP_BASELINE_CREATED` Audit及收据。重放必须匹配原始代码、名称、描述和来源摘要；未知提交由幂等Owner收敛。无HTTP、Schema、依赖、Review、AI调用、外部网络或客户数据变化。

## 验证

- Windows 11 / PostgreSQL 18.6：真实管理员/普通用户Session、CSRF、License、GLOBAL标准来源、首次创建与重放、异载荷冲突、同Key双并发一次结果、Audit故障全回滚、撤权后拒绝；库内无BaselineVersion且正式指针为空。标记`CAP_01_A03_P01_BASELINE_CREATE_PASS`。
- 定向9项通过；后端全量2538项通过、3项既有条件跳过、0失败。
- 开发wheel 906项，SHA-256 `f6cfb4ad42c3bd8269b5c9a11945096dc16f19827438edbaa0236d43c991874b`；仅开发检查产物，不是最终发行包。
- `compileall`与`git diff --check`通过。

首次PG轮次因复用的Schema夹具中FileObject SHA与DocumentVersion SHA故意不一致，被生产Document Port正确拒绝；已只修正A03验证夹具的合成File SHA并从全新临时库完整重跑。该失败不作通过证据，产品验证条件未放宽。

## 兼容、回滚与剩余边界

复用Schema0091和现有`cryptography`等依赖，无Migration或冻结API破坏。可停止组合该内部Owner来关闭新Baseline创建；已提交Baseline/Audit/收据不可删除，空正式指针必须保留。当前没有Draft Version/Item/Evidence创建、Validate、Review、APPROVED、HTTP、前端或生产组合；现有资料没有自动导入。Gate 3、正式信任、性能、Windows Server 2025当前链、Debian 13发行和可用程序包仍未完成。
