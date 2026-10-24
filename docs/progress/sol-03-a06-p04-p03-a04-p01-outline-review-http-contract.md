# SOL-03-A06-P04-P03-A04-P01：Outline 送审可选 HTTP 合同

日期：2026-10-24。状态：`HTTP_CONTRACT_PASS / WINDOWS_NOT_MOUNTED`。

## 编码前检查

| 项目 | 结论 |
|---|---|
| 当前Phase/WBS | Phase 2 / `SOL-03-A06-P04-P03-A04-P01` |
| 输入基线 | Gate2冻结API-04 `SOL_OUTLINE_VERSION_SUBMIT_REVIEW` 路径/ProjectManager/201 ReviewRef+RoundRef；A03-P02内部同库组合已验 |
| 前置 | A02 Subject及0185闭合、A03-P01提交服务和P02完整来源同库送审均通过；Section可选HTTP合同可参考 |
| 涉及模块/实体 | solution可选HTTP router、app注入点；无Schema/历史实体变化 |
| 涉及API/权限 | 冻结 `/api/v1/projects/{project_id}/solution-outlines/{outline_id}/versions/{outline_version_id}:submit-review`；ProjectManager由服务复核；默认不挂载 |
| 验收标准 | Origin、Session Cookie/CSRF、无查询、严格正文、Idempotency；固定策略/目标；201 Review/Round/ETag/no-store；失败映射、默认404、定向与全量回归 |
| 风险/回滚 | 不把HTTP201或合成确认人当客户批准；非法来源/响应错主体失败关闭；未装配可选Router可撤，不触碰冻结API版本 |

本片只建立HTTP合同与默认关闭注入点，真实Windows组合、PG HTTP/浏览器及Review终态分发后续独立验收。

## 实施与验收

- 新增冻结路径的可选 POST Router 与 `create_app` 注入点。只有显式提供该 Router 才挂载；默认 `create_app()` 仍返回 404。请求严格使用 Origin、Session Cookie、CSRF、无查询、幂等 Key 与固定 `reviewer_ids/policy_ref/due_at/submission_note`；首版后两者仅允许 null。应用服务仍负责 ProjectManager、客户确认人、当前事实与原子事务。
- 成功响应仅投影固定 `SOL-03` Outline/Version/Review/Round、客户确认人、IN_REVIEW、提交者与 UTC 时间；201、ETag 和 no-store；错误映射不回显内部异常。HTTP201 只代表已送审，不代表客户批准。
- 可选 Outline Router 合同 11/11 通过；与既有 Section Router 合同合计 22 项通过；后端全量 `4063 passed, 3 skipped, 6112 subtests passed`。本片未用真实 Session/PG 请求新入口，也未挂载 Windows 正式组合，故不称端到端通过。

## 边界与后续

下一片做 Windows 显式 Router 工厂与隔离 Win11/PG HTTP 提交/回放/拒绝验收；之后补统一 Review 读/终态分发与浏览器。无 Schema/权限或冻结 API Breaking Change；未挂载时撤可选注入即可回滚，已有真实评审历史不可删除。Pilot/Gate3/发行仍未通过。
