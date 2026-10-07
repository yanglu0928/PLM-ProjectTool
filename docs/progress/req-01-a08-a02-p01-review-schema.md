# REQ-01-A08-A02-P01：Requirement Review 生命周期 Schema

日期：2026-10-07。结论：`REQ_01_A08_A02_P01_REVIEW_SCHEMA_PASS`。下一项：
`REQ-01-A08-A02-P02` Requirement Review Subject Owner。

## 实现与偏差

- 新增Migration0120，保持0119 DRAFT创建能力，并只开放Review Owner所需的DRAFT→IN_REVIEW、
  IN_REVIEW→APPROVED/RETURNED和旧APPROVED→SUPERSEDED；内容、来源、分类和Review绑定仍不可改写。
- 延迟完整性同时验证`REQ-03 + REQUIREMENT_ALL_V1` PROJECT Review/Round、同项目Subject/Version、
  活动Round、终态一致性、唯一APPROVED及Root正式指针，不允许孤立Review或孤立业务终态提交。
- Requirement Root已有“每次ETag变更必须绑定不可变结果”的强闭包，而同类Survey模块没有这项约束。
  为不降低既有保护，新增内部`req_requirement_review_state_results`，固定START/APPROVED/RETURNED/
  WITHDRAWN、Review/Round、前后正式指针、Actor和前后lock version；Version与Root提交均要求精确结果。
- 该表是A01计划实施时识别出的内部兼容偏差，不改变冻结业务实体或公开API。P02必须同事务写结果；
  直接状态更新、无结果Root bump、结果改删/截断均失败关闭。

## 验证

- Windows 11 / PostgreSQL 18.6：0120空库升降重升、真实0119 Version创建后Review START、RETURNED、
  后续Version START和首次APPROVED、Root ETag/正式指针闭包、无结果直写拒绝、结果截断拒绝、历史拒降、
  Alembic drift均通过。
- 首轮验证暴露终态完整性函数在Root分支仍解析Version专属字段；改为显式表分支后修复。随后夹具使用了
  ReviewRound不存在的`completed_at`列，按真实Schema删除夹具字段后从全新库复跑；两项均未放宽产品规则。
- 定向20项、后端全量3014项通过且3项既有环境跳过；开发wheel共1146项，SHA-256
  `ed08fa488cd784d883a8c69f944fb0e70ab57403bcc61be95c8a28d0b6117d38`，不是正式发行包。

Schema head升至0120；无公开API、依赖、Secret、客户数据或外发变化。无Review历史可降0119；存在结果、
正式指针或非DRAFT Version时拒绝物理降级并要求向前修复。P02前业务Review Owner仍未开放。
