# SOL-03-A06-P04-P03-A04-P02：Outline送审Windows HTTP/PG验收

日期：2026-10-24。状态：`PASS`（显式Windows组合/隔离HTTP+PG；未进入默认正式启动）。

## 编码前检查

| 项目 | 结论 |
|---|---|
| 当前Phase/WBS | Phase 2 / `SOL-03-A06-P04-P03-A04-P02` |
| 输入基线 | 冻结API-04 Outline送审；A02 Subject/0185 Guard；A03完整来源同库；A04-P01默认关闭HTTP合同 |
| 前置 | A03-P02隔离PG内部原子送审/回放已验；P01可选HTTP合同11通过，默认不挂载 |
| 涉及模块/实体 | Windows显式Router组合、隔离PG HTTP验证脚本；无Schema或冻结实体变化 |
| 涉及API/权限 | 仅显式注入开通既有 `/api/v1` Outline送审；ProjectManager、Session/CSRF/Origin/License沿原边界 |
| 验收标准 | 同库完整来源与合格客户确认人；HTTP201单Review/Round/START/快照/收据/Audit，重放等价无新增；错项目/版本、额外字段/来源、已在评审的异Key请求拒绝；后端全量回归 |
| 风险/回滚 | 不把HTTP成功当客户批准；默认关闭不变，非正式信任只能标合成；可撤显式挂载，真实评审历史保留 |

后续另做Review读/终态分发、真实Edge及正式信任验收。

## 实施与独立验收

- 新增 `create_windows_outline_review_submission_router`，仅在调用方显式提供完整 Runtime、Session、可信 Origin、License、Audit、私有存储及当前来源依赖时组装；默认 `create_app()` 仍不挂载 Outline 送审。
- `validation/sol-03-a06-p04-p03-a04-p02-outline-review-http-pg/verify.py` 复用隔离Win11/PG18.6完整合成已批准需求/章节/Trace：DRAFT三维PASS，真实Session Cookie/CSRF/License/ProjectManager/合格合成客户确认人发起HTTP201，返回固定SOL-03身份/ETag/no-store；同Key HTTP201回放完全等价，数据库单Review/Round/快照/START/收据。错Origin 403、额外字段400、错项目/版本404、评审中异Key再送审404；后者是Subject只允许最新DRAFT而当前为IN_REVIEW的失败关闭结果，不将其误报为409。撤Trace后终态现时证明拒绝；脚本exit0，临时库清理。
- Section/Outline既有HTTP合同22项通过；后端全量 `4063 passed, 3 skipped, 6112 subtests passed`。本片不含真实Edge浏览器或真人客户签署。

## 边界与后续

HTTP201仅是提交评审，不是客户审批。公开Review读取/终态分发器尚未注册SOL-03，真实浏览器及正式信任/服务账户/离线安装仍待；下一片从统一Review的读/终态注册和真实PG终态验收开始。没有Schema、冻结API Breaking Change或License权益变化；停用显式Router可撤，历史保留。Pilot/Gate3/正式发行未通过。
