# SOL-03-A06-P04-P02：Outline Review 数据库结果与状态窄门

日期：2026-10-24。状态：`PASS`（仅数据库闭合层，不代表Outline正式送审可用）。

## 编码前检查

| 项目 | 结论 |
|---|---|
| 当前Phase/WBS | Phase 2 / `SOL-03-A06-P04-P02` |
| 输入基线 | Gate 2 冻结DM-05/API-04；DEC-20261024-1220；P04-P01现有Guard/Review前置核查 |
| 前置任务 | Gate 2已批准；Outline真实PG三维与Section统一Review测试已完成；Outline正式送审仍未实现，允许先独立建立数据库窄门 |
| 涉及模块/实体 | solution基础设施；`sol_outlines`、`sol_outline_versions`、新增`sol_outline_review_state_results`；只引用统一`rvw_*`事实 |
| 涉及API/权限 | 无公开API或角色变化；本片不装配Review写Owner |
| 验收标准 | ORM与Alembic up/down一致；仅结果闭合的START/APPROVED/RETURNED/WITHDRAWN及SUPERSEDED/指针转移可写；旧内容/子引用不可改；空库/有数据升级、降级和错误事实负例通过 |
| 风险/回滚 | 不改冻结API；不得伪造正式客户确认或关闭触发器。已有Review历史禁止降级；无历史可降级并重升；任何迁移失败先修复，不标PASS |

当前版本`0184`。本片仅为Outline Review准备SQL保护层；真实业务Owner、路由与客户交互留后续独立任务。

## 实施与独立验收

- 增加ORM和增量Migration `20261024_0185`：不可变`sol_outline_review_state_results`、同根唯一当前APPROVED索引、Version状态/Review引用窄门、同根评审中禁止新版本、根批准指针窄门，以及延迟结果闭合触发器。统一Review/Round/SOL-03快照与策略必须和当前版本摘要精确匹配；只允许START、APPROVED、RETURNED、WITHDRAWN结果。既有Section Review与冻结API未改。
- Migration在升级前锁定根/版本并拒绝已有非DRAFT/Review/批准指针历史的未经审计升级；在有结果或非DRAFT历史时拒绝降级。无历史可回退至0184并重升；不能删除已有业务历史。
- `validation/sol-03-a06-p04-p02-outline-review-schema/verify.py` 在Windows11一次性PostgreSQL18.6中退出0：空库升/降/重升、已有草稿数据升/降/重升、ORM drift无差异；合法START/APPROVED/RETURNED/WITHDRAWN/旧版SUPERSEDED及根指针闭合；无结果直接变状态、错快照/错策略、内容改写、评审中新建版本和有结果降级均被拒绝。夹具仅合成账户/项目，使用测试库`session_replication_role`播种先决事实，不是生产写路径。
- 相关定向17项/4子例与迁移清单7项通过；后端全量第二轮`4014 passed, 3 skipped, 6107 subtests passed`。第一轮仅因迁移版本及表集合测试清单仍固定0184而有2项失败，更新对应测试后全部通过；未将初轮失败隐去。

无公开API、UI、角色、License或正式客户事实变化。下一片`SOL-03-A06-P04-P03`实现Outline Review Subject的同事务现时资格与固定快照；其后再做送审/终态/HTTP/Windows/PG/浏览器。Gate3、Pilot和正式三平台Release仍未通过。
