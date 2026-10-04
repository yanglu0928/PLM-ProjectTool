# AI-04-A06-P04-P03 Content Plan Repository / Owner

日期：2026-10-03；状态：`PASS`（Windows 11 / PostgreSQL 18.6）；依据 CR-AI-016、DEC-731～733、Schema0072。无公开 HTTP、Worker、Invocation 或 Provider 网络访问。

## 交付

- 新增应用层 `AIExecutionContentPlanOwner` 与无正文持久化投影。写入前重验 Plan/Envelope 类型、Plan fingerprint、source projection fingerprints、encoding、estimator、Context fingerprint及记录数；不把 Envelope 正文交给 Repository。
- 新增 PostgreSQL Repository，完整映射 Schema0072 Plan/Source；创建根和有序来源后显式把两个 `plm` constraint trigger切到IMMEDIATE，确保返回前已验证完整图，再恢复DEFERRED，不接管外层事务的commit/rollback。
- 读取时从数据库重建强类型Plan并重新计算完整Plan fingerprint；任一字段、来源顺序、hash、Context或计数不合法均按损坏历史失败关闭。
- 同一PlanId与PreviewId的完全一致重放返回原记录且不新增；任一Plan/Envelope证明漂移返回 `AI_EXECUTION_CONTENT_PLAN_CONFLICT`。并发唯一冲突与Preview创建幂等将在P04-P04的同一写服务内收口。

## 验证

- 单元新增3项：完整持久化/精确重放、Envelope/唯一身份漂移、读取损坏指纹失败关闭。
- `validation/ai-04-a06-p04-p03-content-plan-repository/verify.py` 在一次性Windows 11/PostgreSQL18.6数据库执行真实 Repository/Owner：事务写入→提交→新事务完整回读→精确重放→漂移拒绝；第二Plan显式rollback后数据库仍仅1 Plan/1 Source；`ai_invocations=0`，无Provider I/O。Schema0072 Alembic drift通过，数据库清理。
- Schema0072 P02三库验证在辅助函数扩展后再次回归通过；后端全量 **2197 项运行、3 项既有环境跳过、无失败**。
- 开发 wheel 内容复核通过，SHA-256 `b7c2a8b7a088339cb3dc2b03d0af2e6431dcf7e016cc4ff117526394eb307c6a`；不是最终可使用发行包。
- 首次PG运行因连接默认search_path不含`plm`，未限定schema的 `SET CONSTRAINTS` 找不到constraint trigger；改为 `plm.trg_*` 后从新库完整重跑通过，无持久业务数据。

## 兼容与下一项

本项只增加未装配的内部应用/基础设施组件，不改0072、HTTP、依赖或旧读取。回滚可撤Repository/Owner；已存在Plan仍由0072保护，不应删除。下一任务 `AI-04-A06-P04-P04`：将AI_TASK Preview改为服务端接收计划输入、构建Envelope并与Preview/Plan同事务持久化，非AI操作保持原合同。
