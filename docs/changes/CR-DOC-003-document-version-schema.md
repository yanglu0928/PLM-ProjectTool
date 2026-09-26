# CR-DOC-003：不可变 DocumentVersion 正式持久层增量

日期：2026-09-25；状态：依据 CR-EXEC-001 持续授权，DOC-02-A01 已实施并验证。范围：Phase 2 / DOC-02-A01。

## 来源、冲突与证据

Gate 2 冻结 DM-03、SC-01/02 和 API-02 要求 DOC-02 保留不可变内容版本、受控 FileObject、连续版本号、同文档前驱、来源和可受权的 latest/effective 指针。当前正式 head `20260925_0021` 仅有 Document 逻辑身份与 FileObject，`doc_document_versions`/来源引用表不存在；Document 指针被临时约束为 NULL。须用后续增量实现，不能回写冻结提交 `64cdf09` 或放开自由 UUID。

## 方案比较与选择

- 不选仅以 JSON 字段保存版本/归属：无法建立版本唯一性、Scope/Project 关系及反向引用。
- 不选直接解锁 Document latest/effective 指针：会产生悬空、跨文档或不可用版本引用。
- 选择 Migration `20260925_0022` 建独立 DocumentVersion Root 和来源引用表，物理 FK 约束基础身份，数据库触发器核对 Document/FileObject 同 Scope/Project、PERSISTENT+AVAILABLE、Hash/Size/MIME 快照、前驱属于同文档较早版本以及版本/指针不可变与可用性；继续以事务命令负责预期版本、授权、文件完整性、Audit/Job/Outbox。

## 差异、迁移与回滚

这是已冻结设计的正式物理实现，不改变 API/技术栈/业务分类。目标库先备份再由 `0021` 升至 `0022`；已有 Document 行的 NULL 指针保留。空版本/来源表且 Document 指针均 NULL 时可降级至 `0021`，否则普通降级拒绝；不得删除正式版本历史。无新增第三方依赖。触发器不能证明磁盘文件真实存在，也不能代替文件/数据库联合恢复。

## 验证计划与剩余风险

隔离 PostgreSQL 18：空库 up/down、已有 Document/FileObject 数据升级、ORM 差异、合法第一/后续版本、GLOBAL/PROJECT 归属、同文档指针、可用性、Hash/Size/MIME、一对一 FileObject、前驱链、内容不可变、来源引用不可改写、错误状态/跨项目/非空降级拒绝；开发 wheel 与全量后端回归。正式授权、上传 Commit/恢复、文件 Hash 验证、Server 2025/Debian 13 及最终程序包均另项验收。

验证结果：Windows 11/Python 3.13 后端 453 项无失败（2 项真实符号链接场景因账户权限跳过）；PostgreSQL 18 临时库空/已有数据升级、空表降级再升级、ORM 差异、GLOBAL/PROJECT 及归属/摘要/前驱/指针/来源/不可变负向测试、已发布 FileObject 元数据锁定和非空降级保护 PASS；开发 wheel PASS。测试库已删除，服务已停止。实际磁盘文件、正式授权/上传 Commit/恢复和三平台发行未验证。
