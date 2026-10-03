# CR-AI-021：AI Task 提交选项安全投影

日期：2026-10-03；状态：依 V1.1 持续授权登记，P01 已实施；关联冻结 API-03 `AI_TASK_CREATE` 与 `EGRESS_*`、CR-AI-013/014/019。原 Gate 2 冻结提交 `64cdf09` 不改。WBS：`AI-05-A06-P01`。

## 差异与原因

冻结写接口要求客户端提交 Provider、Model、Task Policy、Egress Policy 与固定输入版本，但没有项目成员可读取的受控选项接口。让用户手工填写 UUID 或策略字符串会把部署内部标识变成操作知识，容易选择未启用、未通过执行白名单或彼此不兼容的组合，无法形成可交付的前端流程。

新增非破坏性 `GET /api/v1/projects/{project_id}/ai-task-options`。它不修改任何冻结路径或 DTO，只向具备 `AI_TASK_CREATE` 角色的当前项目成员投影：部署 Task Policy 的公开字段和参数约束、允许 AI_TASK 的 Egress 上限/风险，以及同时满足 ACTIVE Provider、AVAILABLE 结构化 CHAT Model 和执行策略白名单的路由身份。Endpoint URL、Prompt模板身份/正文、Secret、质量内部记录和配置私有字段不返回。

## 风险、兼容、迁移与回滚

- 风险：错误选项可能导致客户数据发往未批准路由；通过当前数据库状态与部署执行策略双重求交、项目授权和 License 前后复核失败关闭。
- 兼容：纯新增 GET；原冻结 Preview/Authorize/Task Create 保持精确请求和响应。完整 Task/Egress/Execution 三类部署策略缺一时，Task提交组合不挂载，避免展示无法执行的选项。
- 迁移：无 ORM/Alembic 变化；部署配置不含新字段。
- 回滚：撤回新增路由、服务、仓储与授权操作；原写接口、既有 Task/Authorization 事实不变。前端在该路由缺失时必须关闭新建入口，不回退到手填内部标识。

## 验证计划与结果

服务/合同/策略定向 12 项通过；源码 compileall 通过；后端全量 2346 项通过、3 项按既有条件跳过；wheel 构建通过，SHA-256 `5a0440e5d149006ce44c85ae6b21be35a691c890a04c76cf9c1d4905165de288`。本项无外部网络、客户数据、真实 Secret 或数据库迁移；真实 PostgreSQL/Windows 组合留后续 P04。
