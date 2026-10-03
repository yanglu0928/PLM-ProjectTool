# AI-05-A06-P01 AI Task 提交选项安全投影

日期：2026-10-03；状态：`AI_TASK_OPTIONS_API_PASS`；依据 CR-AI-021、冻结 API-03 与现有部署 Task/Egress/Execution Policy。下一项：`AI-05-A06-P02` 严格 Egress/Task 写客户端。

新增项目级只读提交选项应用服务、PostgreSQL当前路由仓储与HTTP投影，并把它与既有 Task Create 组合为同一闭合路由。选项必须同时满足项目角色、License、ACTIVE Provider、AVAILABLE 结构化 CHAT Model 和非敏感执行白名单；Task/Egress/Execution配置链缺一时整个提交组合保持未挂载。只投影浏览器构造冻结写请求所需的最小字段，不返回Endpoint、Secret或Prompt。

无Schema/Migration/依赖/客户数据外发变化。服务/合同/策略定向12项、compileall、后端全量2346项通过（既有3项跳过）；wheel SHA-256 `5a0440e5d149006ce44c85ae6b21be35a691c890a04c76cf9c1d4905165de288`。真实PG/Windows组合、前端客户端与三步交互留后续。
