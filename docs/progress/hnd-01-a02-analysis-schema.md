# HND-01-A02：Handover Analysis Schema/ORM 基础

日期：2026-10-05。结论：`HND_01_A02_ANALYSIS_SCHEMA_PASS`。下一项：`HND-01-A03-P01` Analysis identity 创建 Owner。

## 编码前检查

```text
当前Phase：Phase 2保持IN_PROGRESS；Gate 3保持BLOCKED
当前WBS：HND-01-A02
输入基线：DM-05、SC-01/02、API-04、CR-HND-001、DEC-847
前置任务：HND-01-A01运行时差距与固定来源边界已通过
涉及模块：handover ORM/Alembic；只引用project/document/evidence/capability/ai Owner事实
涉及实体：HND-01 HandoverAnalysis、HND-02 HandoverAnalysisVersion及六类owned Item
涉及API：无公开Router或HTTP变更
涉及权限：PROJECT归属由复合外键和提交期守卫固定；Owner前全部变更失败关闭
验收标准：空/历史库升降重升、ORM drift、固定来源、完整提示、历史拒降
风险：一次迁移跨入Action状态机；source_missing在Action Root前被误当闭环；字段级提示只做最低DB校验
```

## 实施结果

- 新增 Schema 0096 与八张 ORM 表，物理化 Analysis identity、不可变 Version、固定 Project DocumentVersion、成功 GAP_ANALYSIS provenance、六类 Item、Evidence、Approved Capability Item 和 NEED_CONFIRM options。
- 延迟提交守卫验证声明计数、规范来源指纹、项目/可用性归属、当前 Approved Capability Version、Evidence/Capability/AI provenance 和 NEED_CONFIRM 最小形状；Owner 安装前禁止更新、删除、truncate 和非初始状态写入。
- 发现原计划把 HND-03 ActionItem 状态历史同时塞入 A02 会跨越两个独立问题；已在 CR-HND-001 留痕，将 HND-03 Schema 顺延至 `HND-02-A01`，不改变冻结三 Root/二十 Operation。
- `source_missing` 当前只保存“资料缺失”事实，不形成关闭；正式 Review/HTTP 在 Action 绑定完成前保持关闭。字段级输入提示的深层验证留给 A03 Validate Owner。

## 验证与证据

- Windows 11/PostgreSQL 18.6 临时库：从0095有数据升级、空历史降级/重升、ORM drift、合法快照、错误来源摘要、NEED_CONFIRM缺项、Owner关闭和有历史拒降均通过；临时库已删除。
- 定向 Handover Schema/Migration 测试8项通过；后端全量2601项通过、3项按既定环境条件跳过。
- `compileall`、`git diff --check`通过；最终开发wheel解包后的Handover/迁移/ORM定向11项通过并确认包含Schema0096，wheel SHA-256 `87b9680c9f80f25e41f6bb44c1d1d0e21d543616a501fa8199d10dfa2ceb762d`。本项不导入客户资料、不调用AI或外部网络。

## 兼容、回滚与未关闭项

新增内部Schema，不修改既有表、冻结API、生产依赖或配置。无Handover历史可降回0095；存在历史时拒降并向前修复。停止后续Owner/Router即可保持功能关闭，但不得删除已形成历史。

Analysis创建/验证Owner、Review正式化、HND-03 Action、20个HTTP Operation、Evidence快速定位/输入提示前端、Workflow Adapter、真实资料质量、性能、正式信任及目标平台发行仍待；Gate 3继续BLOCKED。
