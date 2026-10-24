# AI-04-A05-P02：AI Task 提交快照 Schema0070

- 日期：2026-10-03
- 结果：PASS（Schema/ORM与Win11 PostgreSQL 18.6迁移证据）
- 依据：CR-AI-014、DEC-715/716；原冻结提交 `64cdf09` 不改

新增迁移 `20261003_0070` 及一致ORM元数据，为AITask提供不可变的 PromptTemplate/PromptVersion、最小业务参数和SHA-256快照。数据库强制四列全空或完整，完整值必须引用当前ACTIVE Prompt版本，并与Task类型、Output Schema和RAG Policy一致；参数限定为有界JSON object，摘要按PostgreSQL规范JSON文本计算；提交快照后续不可修改。

这是分阶段兼容迁移：0069遗留行及当前仍关闭的内部旧创建链可保持全NULL，避免在Task Policy/Prompt Owner尚未接入时破坏现有功能。P03将使应用层新写入必须完整，并禁止旧NULL Task进入执行。公开AI Task HTTP、Worker执行与真实外发均未因本项开启。

验证在Windows 11本机PostgreSQL 18.6随机空库/数据库完成：upgrade/down/re-up、0069历史保留、Alembic drift、Prompt复合引用、活动状态与版本、task type/output/RAG匹配、JSON形态/大小/键数/摘要、不可变和非空拒降均PASS。迁移开发中两项缺陷——PL/pgSQL变量歧义和非对象JSON检查顺序——均已修正，并从头完整重跑。后端全量 `2136` 项通过、`3` 项既定跳过；wheel构建通过，SHA-256 `a6e14f401ffc911cf84091c685e932f76eff74d611ad97e8b484caa18af22c7a`。

Changed：Migration0070、AITask ORM、migration head合同与独立PG验证脚本。Compatibility：无公开API、依赖或真实Provider行为变化。Upgrade/Rollback：完整历史为空时可降；存在完整快照时拒降并须向前修复/受控恢复。Known Issues：Task Policy/Prompt Owner及新写完整快照、Task HTTP/读取、Worker发送前撤销与payload重验、正式信任、Server2025、Gate3/UAT/交付包待完成。Next：`AI-04-A05-P03`。
