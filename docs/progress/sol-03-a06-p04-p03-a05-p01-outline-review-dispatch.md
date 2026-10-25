# SOL-03-A06-P04-P03-A05-P01：Outline 统一 Review 读/终态注册

日期：2026-10-24。状态：`PASS`（显式注册和隔离PG合成客户评审）。

## 编码前检查

| 项目 | 结论 |
|---|---|
| 当前Phase/WBS | Phase 2 / `SOL-03-A06-P04-P03-A05-P01` |
| 输入基线 | 冻结 Review Engine/SOL-03 API；0185结果闭合；A02 Subject/终态重证；A04-P02完整来源HTTP送审 |
| 前置 | 最新Outline DRAFT真实同库送审201/回放，客户确认人资格与合成终态仓储已验；统一Review已有Section运行时模式 |
| 涉及模块/实体 | Windows统一Review读/列表/命令分发与SOL-03 Owner；不新增Schema、实体或公开API |
| 涉及API/权限 | 复用已冻结Review GET/LIST/decide/withdraw；只有显式传入合格Outline Owner才注册，默认不开放SOL-03读/终态 |
| 验收标准 | 注册精确主体后合成客户可读待办并批准，批准前现时三维重证；Review/Round/Outline状态、批准指针、不可变结果、Audit同事务闭合；撤Trace后拒绝批准；错项目/身份/回放失败关闭；单元及隔离PG验收 |
| 风险/回滚 | 不把合成客户决定当真实签署；默认未注册仍不可读/审批；历史不可删除，停用注册只影响新路由暴露 |

选择由调用方构造并显式注入已校验的 `OutlineReviewSubjectOwner`，避免统一Review组合器复制Solution完整来源图；该非Breaking组合方式记录于决策日志。

## 实施与验收

- 统一 Review 读取、列表、命令组合器增加可选的精确 `OutlineReviewSubjectOwner` 注入。未传入时注册集合不变；传入伪造 Owner 或命令组合缺完整来源依赖时启动失败关闭。没有新公开 API/Schema/权限，也未把该 Owner 接入默认生产启动。
- 单元组合 8 项通过，覆盖三类分发器的显式 SOL-03 注册、默认兼容和错误输入拒绝；后端全量 `4065 passed, 3 skipped, 6112 subtests passed`。
- `validation/sol-03-a06-p04-p03-a05-p01-outline-review-dispatch/verify.py` 在 Win11/一次性 PG18.6 使用完整合成已批准需求/章节/Trace、正式 Session/Review 核心：HTTP 送审后合成客户 GET 固定 SOL-03 Review 200，跨项目404；撤 Trace 后客户 APPROVE 404且无决定；恢复 Trace 后 APPROVE 200、同Key回放200、历史GET显示APPROVED；数据库单客户决定、OutlineVersion APPROVED、根批准指针、新增APPROVED不可变结果和对应 Audit 各一，脚本exit0，临时库清理。

## 边界与后续

这是合成客户身份/信任下的隔离验收，不能视为真实客户签署或生产许可。真实Edge浏览器、默认Windows生产启动接线、正式公钥/服务账户、离线安装仍待；下一片做客户待办浏览器链。撤显式注入可停用新路由分发，已产生的评审历史不删除、须前向修复。Gate3/Pilot/正式发行未通过。
