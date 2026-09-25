# CR-DOC-002：Document 逻辑身份正式持久层增量

日期：2026-09-25；状态：依据 CR-EXEC-001 持续授权，DOC-01-A01 已实施并验证。范围：Phase 2 / DOC-01-A01。

## 来源、冲突与证据

Gate 2 冻结 DM-03、SC-01/02、API-02 定义 `DOC-01 Document` 为稳定逻辑身份，Scope/Project、类别、标题、状态、latest/effective 版本指针和并发版本均须受控。当前正式 Migration head 为 `20260925_0020`，仅有 DOC-03 FileObject，尚无 `doc_documents`/DOC-02 DocumentVersion。冻结设计已定，生产 DDL 尚未实现；后续 Schema 增量必须保留原冻结历史。

## 方案比较与选择

- 不选直接开始上传 HTTP 或以 FileObject 代替 Document：缺逻辑身份、受权版本和指针，不能满足冻结三层分离。
- 不选为尚不存在的 DocumentVersion 建不可验证的自由 UUID 指针：会形成悬空/跨 Scope 版本引用。
- 选择先以 Migration `20260925_0021` 建立 `doc_documents` 与 Project/User 外键、Scope/类别/状态/显示元数据和 lock_version；latest/effective 指针先显式为 NULL 并由数据库检查，DOC-02 版本表落地时再建立真实 FK、同 Document/Scope 约束并解除初态限制。

## 差异、影响、迁移与回滚

这是 Gate 2 冻结设计的正式物理实现增量，不回写 `64cdf09`，不更改业务分类、技术栈或 `/api/v1`。目标库升级前备份并从 `0020` 升至 `0021`；空表可降级到 `0020`，已有 Document 时普通降级拒绝，防止丢失逻辑身份。DOC-02 后续 Migration 必须完整校验版本指针，不能以当前 NULL 检查冒充最终约束。无新第三方依赖。

## 验证计划与剩余风险

验证 ORM/Migration 差异、空库 up/down、已有 FileObject 数据升级、GLOBAL/PROJECT 与 Project FK、类别及 OTHER 的 subtype/purpose、GENERATED_ARTIFACT 的 PROJECT 范围、显示元数据、初态指针 NULL、并发版本、非空降级保护；使用隔离 PostgreSQL 18 与合成数据。DocumentVersion/文件发布、Project Archived 写保护、正式授权 HTTP 和三目标环境发行另项验收，不把本表视为 Document 功能可用。

验证结果：Windows 11 后端 453 项无失败（2 项真实符号链接场景因账户权限跳过）；PostgreSQL 18 临时库空/已有数据升降级、ORM 差异、Scope/类别/指针/版本约束、绕过 ORM 的身份变更拒绝及非空降级保护 PASS；开发 wheel PASS。DocumentVersion、正式权限/API 和最终程序包尚未完成。
