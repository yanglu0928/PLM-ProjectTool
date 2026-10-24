# AI-04-A06-P04-P04-A02 Prompt 规划期 PostgreSQL Owner

日期：2026-10-03；状态：`PASS`（Windows 11 / PostgreSQL 18.6）；依据 CR-AI-016、DEC-731～735。该切片只接通 Preview 规划所需的当前 Prompt/参数投影，尚未修改公开 HTTP、生产组合或触发 Provider 网络访问。

新增 `SqlAlchemyAIExecutionPromptPlanningRepository` 与严格 Owner：在调用方短事务内锁定 `DEPLOYMENT/ACTIVE` PromptTemplate，读取其 `active_version_no` 对应的不可变 PromptVersion，并精确匹配 Task Policy 的 task type、template、output schema 与 context policy。任务参数只来自已解析的部署 Policy，转换为 PostgreSQL JSONB 后由数据库规范化并计算 SHA-256；Prompt 正文和参数值仅存在于短生命周期对象且不进入 repr。

活动 Prompt 版本号不由部署 Policy 固定；同一模板切换活动版本后，新 Preview 应读取新版本并形成新 Plan。Owner 只拒绝被 Policy 固定的身份漂移，不把合法版本推进误判为漂移。Plan 落库后的执行仍按不可变 `prompt_version_no/hash` 读取，不会随活动版本变化。

验证：新增单元2项，并回归 Builder/Prompt/Envelope 合计10项；Windows 11 一次性 PostgreSQL 18.6 数据库证明活动版本读取、服务端 JSONB 指纹、事务期间 `FOR KEY SHARE` 行锁、敏感 repr 排除、输出 Schema 漂移失败关闭及零 ContentPlan/Invocation。后端全量 **2201项运行、3项既有环境跳过、无失败**；开发 wheel SHA-256 `2fc1a8ef6d9216063715acd205e143cd678af01a8ff325b645d7ba189e14f2db`。

开发期首轮单元失败来自测试错误地假定 Policy 固定活动 Prompt 版本；按冻结模型修正为模板/Schema/Context 漂移负例后，定向、真实 PostgreSQL 与全量回归均通过。无 Schema、API、依赖、持久化格式或网络变化；回滚为不装配并移除新 Repository/Owner。

下一切片 `P04-P04-A03`：给 Document Owner 增加规划期精确最小投影，供现有服务端 Plan Builder 使用；随后 A04 组合 Preview 事务。
