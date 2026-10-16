# CAP-01-A04-A03：Capability Review Subject Owner

日期：2026-10-05。结论：`CAP_01_A04_A03_CAPABILITY_SUBJECT_PASS`。下一项：`CAP-01-A04-A04` Capability 评审终态正式化。

## 编码前检查

```text
当前Phase：Phase 2保持IN_PROGRESS；Gate 3保持BLOCKED
当前WBS：CAP-01-A04-A03
输入基线：冻结CAP-01/DM-05/API-04、Schema0092、CR-CAP-001、CR-RVW-003、DEC-837
前置任务：Review GLOBAL事务内核已通过且未挂HTTP
涉及模块：Capability Review Subject application/repository；Review start持久合同；Schema0093
涉及实体：CapabilityBaseline、BaselineVersion、Review、ReviewRound、Evidence/Document当前事实
涉及API：无公开HTTP；受信内部组合保持关闭
涉及权限：送审人为当前DeploymentAdmin，全部Reviewer必须为当前启用用户；非终态决策人必须当前启用
验收标准：真实DRAFT锁定为IN_REVIEW、Review绑定一致、来源重验、评审期间禁止替代Draft、终态在A04前失败关闭
风险：Review先写而Subject未绑定、伪GLOBAL权限、来源撤销后终态通过、未完成正式化却提交APPROVED
```

## 实现与偏差

新增真实 `CapabilityReviewSubjectOwner` 和仓储。送审前锁定Baseline和指定最新DRAFT Version，重验发起人、全部Reviewer、精确GLOBAL Document来源集合及逐项Evidence；Review首轮行创建后，通过新增的显式 `finalize_start_in_transaction` 阶段把Version原子绑定为`IN_REVIEW`并写入Review/Round引用，再执行第二次主题锁断言。该阶段是为满足Review外键必须先存在的事务内顺序约束；持久内核兼容既有无后绑定需求的Subject缺省该钩子，不改变既有PROJECT公开合同。

Schema0093只开放精确`DRAFT -> IN_REVIEW`状态转换，要求Review为GLOBAL/CAP-01、活动Round和Subject Version完全匹配，并以唯一部分索引保证每个Baseline最多一个评审中Version。Version创建仓储同步增加`IN_REVIEW`排他条件，评审锁存在时不能创建替代Draft。任何Review历史存在时拒绝物理降级并要求向前修复。

A03仅实现送审和非终态访问证明。终态前再次校验全部Reviewer及Document/Evidence当前事实，但`consume_terminal`和终态断言故意失败关闭；因此APPROVED、RETURNED、WITHDRAWN均不能在本项形成Capability正式状态。A04将以独立Schema守卫原子消费终态并更新正式指针。

## 验证

- Windows 11 / PostgreSQL 18.6：Schema0093升级及Alembic drift为零；错误Evidence使送审整笔回滚且Review为零；恢复后真实Version进入IN_REVIEW并精确绑定Review/Round；替代Draft被拒绝；首位Reviewer非终态决策提交；第二Reviewer撤权时拒绝；恢复后终态因A03失败关闭而整笔回滚；Version/Review保持IN_REVIEW且只有一条Decision。标记`CAP_01_A04_A03_CAPABILITY_SUBJECT_PASS`。
- 有Review历史时降级0092被拒绝；未把合成内容正确性、终态正式化或HTTP可用性描述为已验证。
- 定向28项通过；后端全量2557项通过、3项既有条件跳过、0失败。第一次全量回归只有迁移头契约仍固定0092而失败，更新为0093及0092父链后完整重跑通过，产品规则未放宽。
- 开发wheel内Review 103项、Capability 21项通过，SHA-256 `15f26b23db3391abfd959d04f31b1c59e6028aa7075c031a31a6a6a159f41c55`；仅开发检查产物。
- `compileall`、实库迁移检查与`git diff --check`通过。

## 兼容、迁移、回滚与剩余边界

内部Schema`0092 -> 0093`替换状态守卫并追加唯一部分索引/延迟绑定校验；无公开API、新依赖、网络、Secret、客户数据或资料自动导入。无Review历史可降；有Review/IN_REVIEW历史拒降并向前修复。停用GLOBAL组合可关闭新送审，但已提交Review与Capability锁必须由后续正式Owner处理，不能删除历史。

Capability终态消费、APPROVED正式指针、旧正式版SUPERSEDED、RETURNED/WITHDRAWN解锁、新版本创建、License/Session/CSRF/幂等外层、HTTP/前端和生产组合仍未完成。Gate 3、真实业务质量、正式信任、性能及目标平台发行证据保持阻塞。
