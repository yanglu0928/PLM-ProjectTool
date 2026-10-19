# Review List 索引增量 0166

日期：2026-10-19；WBS：`SOL-06-A16-P03`；来源：`CR-RVW-004`、冻结 REVIEW_LIST 与 A16-P02 `created_at DESC, review_id DESC` / `my_pending` 合同。

## 变更

- Migration `20261019_0166`，父版本 `20261019_0165`。
- `plm.rvw_reviews` 新增 `ix_rvw_reviews__scope_created(scope, scope_project_key, created_at DESC, review_id DESC)`，服务 Project/GLOBAL 边界内稳定 keyset 顺序；当前 V1 HTTP 只开放 PROJECT。
- `plm.rvw_review_assignments` 新增 partial index `ix_rvw_assignments__reviewer_pending(scope, scope_project_key, reviewer_id, review_round_id) WHERE assignment_state='PENDING'`，只加速当前 reviewer 待处理候选。
- ORM 声明同名、同顺序、同 partial predicate；不增加列、约束、业务状态或数据回填。

## 迁移、回滚与边界

- 升级只建索引，可在空库或已有 Review/Round/Assignment/Decision 历史上执行，不改任何行。
- 降级只删两个索引，允许保留全部历史；应用入口应先关闭或回退到不依赖 LIST 的版本，再降至 0165。
- 索引不是授权、任务事实或客户确认。查询仍必须执行 License、Session、Project、Subject Owner 和 Assignment 当前事实检查。
- 迁移验收必须覆盖空库、有历史升级、降级重升、索引定义/查询计划、行计数不变、Alembic check 与 Review 上游回归；正式性能指标仍需后续独立压测。
