# SUR-01-A04-A02-P01：Survey Review Schema0105

日期：2026-10-06。结论：`SUR_01_A04_A02_P01_REVIEW_SCHEMA_PASS`。

实现 Migration 0105，在不增加列的前提下开放三条唯一 SurveyVersion 状态路径，并以延迟完整性检查把 `PROJECT + SRV-02 + SURVEY_ALL_V1` Review/Round、Version 状态、旧版 `SUPERSEDED` 和 Root 正式指针绑定到同一提交。终态不得替换 Review 引用；Root identity、Project、名称和 ACTIVE 状态仍不可改变，历史不得删除。

验证：新增 Schema 单元 5 项，连同 Migration 合同共 9 项通过；Windows 11 / PostgreSQL 18.6 实际验证空库 head、0105 降级/重升、drift、错误政策、过早批准、首版批准、第二版撤回、第三版批准并取代首版、正式指针和历史拒降，标记 `SUR_01_A04_A02_P01_REVIEW_SCHEMA_PASS`。原 `SUR_01_A02_DEFINITION_SCHEMA_PASS` 在 0105 head 下回归通过。后端全量 2802 项通过、3 项跳过；开发 wheel 1036 项且包含 0105，SHA-256 `6fe3201f64ef9a213d8c2e2020f57203fce4ce796736bdd9db429d73a7f74637`。

验证偏差：首次全量命令把 `apps/backend` 误设为 discovery top，在中文 Windows 路径下于收集前失败；改用既有 `apps/backend/tests` 包根后完整重跑通过，未改变产品代码。0105 改写守卫错误文本后，原 0103 验证器仍断言旧文本；仅将回归断言更新为当前失败关闭文本并重新完整通过。

升级无需数据回填。无 Review 历史可降至 0104；已有正式指针、非 DRAFT Version 或 Review 引用时拒降。无公开 API、依赖、Secret、网络或外发变化；wheel 仅为开发验证产物，不是可使用发行包。下一项 `SUR-01-A04-A02-P02` 实现真实 Survey Review Subject Owner，应用层当前仍未开放送审。
