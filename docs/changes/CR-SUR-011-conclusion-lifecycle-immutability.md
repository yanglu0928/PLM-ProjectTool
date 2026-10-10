# CR-SUR-011：SurveyConclusion 载荷不可变与 Review 生命周期兼容

日期：2026-10-07。状态：依据 `CR-EXEC-001` 持续授权批准实施。Gate 2 原冻结提交 `64cdf09` 不改写；
本 CR 修复 `SUR-04-A06` PostgreSQL 18 真实验证发现的内部 Schema 冲突。

## 差异与影响

`20261007_0109` 将 `srv_conclusions` 与其明细统一设为只允许 INSERT，以保证结论快照不可变；但同表同时
承载已冻结数据模型规定的 `DRAFT -> IN_REVIEW -> APPROVED/RETURNED -> SUPERSEDED` Review 状态及引用，
导致正式 Review Owner 无法绑定或消费审批。若绕过触发器，数据库不能独立阻止业务载荷篡改；若另建状态表，
会扩大 Schema、ORM、迁移及查询契约，且偏离当前阶段最小实现。

## 选择

- 新增 Alembic `20261007_0110`，只放行三类白名单状态迁移：DRAFT 绑定 Review、IN_REVIEW 终结为
  APPROVED/RETURNED、旧 APPROVED 被新批准版本置为 SUPERSEDED。
- 迁移逐字段证明 ID、项目/调查、来源引用、版本链、内容指纹、声明计数及创建事实均未变化；任何载荷变化、
  非法跃迁、清空或替换 Review 引用仍由数据库拒绝。
- 所有结论明细继续只允许 INSERT，逻辑删除、原地修订及 TRUNCATE 规则不变。

## 迁移、回滚与验证

- 升级仅替换 owner trigger function，不重写既有数据；已存在 DRAFT/其他状态行保持原值。
- 降级恢复只允许 INSERT 的旧函数；降级后既有状态可读，但不能继续审批，故业务回滚同时停止 SRV-05 写入。
- PostgreSQL 18 验证必须覆盖合法全生命周期、非法载荷更新与非法状态跃迁拒绝、旧批准版替换、空库升级、
  Alembic current/check 以及应用事务回滚与重放。
