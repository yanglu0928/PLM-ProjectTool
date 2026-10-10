# AI-04-A06-P04-P02 Content Plan Schema0072 / ORM

日期：2026-10-03；状态：`PASS`（Windows 11 / PostgreSQL 18.6）；依据 CR-AI-016、DEC-731/732。范围仅为持久化结构与数据库保护，不开放新 HTTP、Repository、Worker 或 Provider 网络访问。

## 交付

- 新增 Schema0072：`ai_execution_content_plans` 保存无正文的完整执行身份、Content Plan/Envelope 指纹与服务端计数；`ai_execution_content_sources` 保存按序的业务引用和精确 Owner 内容版本、三类指纹、大小/记录数，不保存正文、参数值、locator、Secret、endpoint 或 Provider 响应。
- Plan 一对一反向绑定 `AI_TASK` Preview；Source 必须与对应 Preview Source 逐项一致、仅能与 Plan 同事务创建，延迟约束在提交时验证非空、序号连续、来源数量与 Preview 相同、来源与 Context 记录数之和等于 Plan/Preview 记录数。
- Plan/Source 禁止 UPDATE/DELETE/TRUNCATE；Plan 建立后禁止追加 Preview Source。数据库同时校验 Preview、Prompt Version 和 Provider Model 身份以及 payload/record/byte/token 上限。
- `ai_egress_authorizations`、`ai_tasks`、`ai_egress_authorization_snapshots`、`ai_invocations` 新增可空 `content_plan_ref`、外键、索引与引用不可变触发器。NULL 专用于0072前历史；P04-P05前尚不表示新写链已强制绑定。
- 有 Plan/Source 或非空引用时拒绝降级；无 Plan 的旧 AI/非 AI Preview 与旧 Task 可 `0071 → 0072 → 0071 → 0072`，不猜测回填。

## 验证

- `validation/ai-04-a06-p04-p02-content-plan-schema/verify.py` 在本机 Windows 11 / PostgreSQL 18.6 创建三套一次性数据库，完成空库与历史库 up/down/re-up、Alembic ORM drift、AI_TASK/RETRIEVAL_RUN兼容、完整 Plan 写入、错误 Source/不完整 Plan/修改/删除/TRUNCATE/Plan 后追加 Preview Source拒绝、敏感列排除及有历史拒降；脚本退出0并清理数据库。
- 新增 Schema 单元3项，Migration合同4项通过；后端全量 **2194 项运行、3 项既有环境跳过、无失败**。
- 开发 wheel 内容复核通过，SHA-256 `eee89c4747111b62db83116621d22e010fa16751f314835e62ac417a40adb306`；不是最终可使用发行包。
- 首次真实验证发现 PL/pgSQL 局部变量 `model_revision` 与列名歧义，改为 `observed_model_revision` 并限定表别名后全矩阵重跑通过。首次全量回归因 ORM 总表清单未登记两张新表失败1项，补充显式登记后全量重跑通过；均未产生持久业务数据。

## 兼容与回滚

这是增量、可空的历史兼容迁移；应用切片尚未写 Plan 时可安全降至0071。首次写入 Plan 后不可物理降级，应停止新 AI_TASK 消费并保留历史向前修复。Server 2025 留待可达环境复验，Debian 13 按用户指令跳过。

下一任务：`AI-04-A06-P04-P03`，实现 PostgreSQL Content Plan Repository/Owner，按应用指纹重算并用事务写入/读取完整 Plan；不提前改 HTTP。
