# SurveyVersion Owner Schema 0104 增量

日期：2026-10-06

迁移：`20261006_0103 -> 20261006_0104`

0104 只把 `srv_surveys` 的临时全关闭保护收紧为 DRAFT Version Owner 所需的唯一合法更新：Root identity、Project、名称、状态、批准指针和创建事实必须不变，状态必须 ACTIVE；批准指针可为空或保留既有已批准版本，但本迁移不得改变它。仅允许填写 `updated_by/updated_at` 并把 `lock_version` 精确加一。删除和其他更新继续失败关闭。

空 SurveyVersion 历史可降级并恢复 0103 关闭保护；存在 Version 历史时拒绝降级。无新表列、冻结 API、角色或依赖变化。
