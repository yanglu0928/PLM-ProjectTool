# Survey Review Terminal Schema 0105 增量

日期：2026-10-06。迁移：`20261006_0104 -> 20261006_0105`。

## 目的与边界

0105 不增加表或字段，只把 0104 的 Survey DRAFT Owner 写门替换为 Review 所需的最小状态门，并以可延迟约束触发器保证 Review、Round、SurveyVersion 与 Survey 正式指针在同一事务收敛。通用 Review 必须精确匹配 `PROJECT + SRV-02 + SURVEY_ALL_V1`、同一 Project/Survey/Version 和活动 Round。

允许的 Version 路径只有：

- `DRAFT -> IN_REVIEW`：一次性固定非空 `review_ref/review_round_ref`；
- `IN_REVIEW -> APPROVED | RETURNED`：Review 引用不得替换；
- `APPROVED -> SUPERSEDED`：Review 引用不得替换，且必须已有更高版本的当前 APPROVED Version。

批准必须把新版本置 `APPROVED` 并把 Root 正式指针指向该版本；退回或撤回映射为 `RETURNED` 且不得改变正式指针。替换批准时旧正式版、新正式版和 Root 指针必须在同一事务完成。问题、选项、来源和目标部门仍不可修改或删除。

## 升级、降级与回滚

升级只安装/替换守卫函数和三项可延迟触发器，不迁移或推定既有业务状态。无 Review 历史时可降至 0104，并恢复原 DRAFT Version Owner；存在正式指针、非 DRAFT Version 或 Review 引用时拒绝降级，必须向前修复或恢复备份。应用层可停止装配后续 Subject Owner，但不得删除已形成历史。

## 验证

Windows 11 / PostgreSQL 18.6 已验证空库至 head、0105 空历史降级/重升、Alembic drift、错误政策拒绝、PROJECT Subject/Version 精确绑定、过早批准拒绝、批准/退回/取代链、正式指针收敛和历史拒降。`SUR-01-A02` 原 Schema 验证在新 head 下同步回归通过。

本增量不开放公开 HTTP，不改变冻结 `/api/v1`、角色、依赖、Secret、网络或数据外发边界。Windows Server 2025、Debian 13、性能、正式信任、UAT 和发行不由本项证明。
