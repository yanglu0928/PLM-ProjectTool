# CR-OUT-030：输出制品的本地文件发布与一致性

- 日期：2026-11-05
- 状态：已登记；P34 编码前检查完成，尚未编码
- 来源：OUT-01-A01-P34，承接 CR-OUT-029 明确保留的真实 Storage 发布后续任务
- 基线：ADR-008、冻结 DM-03/OUT-02、P32 Migration 0232、P33 PASS_SCOPE_LIMITED

## 问题与证据

P33 仅在合成 PostgreSQL 事务中证明已存在且状态为 AVAILABLE 的 FileObject/DocumentVersion 可与 OutputArtifact、OutputRequest、Job 和 Audit 原子收敛。它没有读取或提升真实 staged 文件。ADR-008 要求隔离暂存、流式 SHA-256、同卷不可覆盖提升、发布后复验，并明确数据库与文件系统不能原子提交，须由 STAGED 状态、补偿清理和恢复审计处理。

当前分支已有 `LocalFileStorage.publish_verified`（文件身份/链接数/重解析点检查、大小与SHA-256复验、同卷硬链接无覆盖提升、提升后再次复验）、`inspect_recovery`/受限恢复原语、Document `FilePublishService`，以及 P33 `OutputGenerationCompletionOwner`。这几个部件尚未形成安全的 Output 专用协调流程。直接在 P33 完成Owner里做文件I/O会在长Hash/文件操作期间持有数据库锁；只提升文件再提交P33则会留下 final-only 窗口，必须有精确恢复与不可误删边界。

## 方案比较

A. 将文件I/O塞入现有P33单个数据库事务：会长时间持锁，且回滚不能撤销文件系统副作用；拒绝。
B. 使用ADR-008现有Storage原语，建立单独的内部Output发布协调Owner：短事务验证并固定候选；事务外执行带身份和Hash保护的 staged→generated提升；发布后复验；短事务重新锁定并核验同一请求/执行/Document/File/版本/Hash及fencing后复用P33完成Owner。记录final-only/linked-pair等可识别恢复状态；未知或不安全状态失败关闭，绝不盲删。选定，具体接线以前置不变量审查和托管验收为条件。
C. 改为对象存储、数据库大对象或新队列：超出现行架构，拒绝。

## 选定方案与差异

在 ADR-008本地Storage范围内复用现有原语，不更改冻结API、Schema/Migration、Locator语义、模块边界或默认生产组合。新增内部应用协调流程与合成/隔离验收；不直接调用插件，不创建产品文件，不接入Worker、HTTP或默认平台装配。Output事务与文件系统仍是两个资源，保证以精确状态与恢复流程表达，不声称跨资源ACID。

## 影响、风险与控制

- 风险：文件提升后数据库失败形成final-only；并发重试、Hash不匹配、路径替换或错误恢复会破坏正式数据。
- 控制：数据库候选快照与fencing校验；LocalFileStorage现有locator/no-follow/普通文件/硬链接/身份/同卷/Hash限制；发布后重验；再次检查DB事实；只对DB仍为STAGED且绑定完全一致的候选允许有限恢复；不匹配或未知路径不变更并转人工/隔离诊断。
- 迁移：无数据库结构迁移；若编码前检查发现缺少冻结字段/状态而需要Schema变化，先补充本CR并保留冻结版本。
- 回退：Owner保持内部未装配，可撤回新增协调模块/测试/Verifier；已移动文件不回滚删除，按DB状态和文件身份分类对账，保留原始Hash/locator与审计证据。
- 验证：GitHub hosted Windows Server 2025 D: 临时目录与隔离PG18、纯合成文件/行；测试原子无覆盖提升、发布前/后Hash与大小、错项目/执行/文件、并发/旧fencing、DB/Audit失败后的final-only核对、重复调用、重解析点/链接数/不一致时失败关闭；后端全量/wheel、前端/build及父包现有验证。用户本机和C:不运行代码。

## 执行门槛

P34编码前检查必须先确认 FileObject/DocumentVersion 提交顺序、Document发布Owner与恢复能力、Output生成Claim身份和锁序，以及Storage locator语义。若现有状态不允许无Schema变更安全表达恢复，停止P34实现并转向独立非阻断任务，按持续授权提出最小兼容CR；不得伪造AVAILABLE或回滚删除不明文件。
