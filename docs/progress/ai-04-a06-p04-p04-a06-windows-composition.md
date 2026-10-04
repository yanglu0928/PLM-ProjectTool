# AI-04-A06-P04-P04-A06 Windows 生产组合

日期：2026-10-03；状态：`WINDOWS_COMPOSITION_PASS`；依据 CR-AI-016、DEC-731/737～739。

Windows 显式写平台现把已配置的 `ai_task_policies` 和绝对 `data_root` 注入 Egress 组合。存在 Task Policy 时，组合根建立 Prompt 规划 Owner、Document 最小内容 Owner、确定性 Envelope/Plan Builder 和 Content Plan Repository；AI_TASK Preview 因而在一个数据库事务内生成并保存服务端计数、payload fingerprint、Plan/Source、Audit 与幂等 Receipt。部署只配置 Egress Policy 而未配置 Task Policy 时，路由仍可服务非 AI 操作，但 AI_TASK 计划请求失败关闭，不会退回信任客户端摘要。

组合根保持以下边界：

- Document 正文只从 `data_root` 下的私有 ParseResult 读取、复核并短生命周期投影，不进入普通响应、日志、Audit 或数据库 Plan。
- Prompt/参数由版本化 Task Policy 和当前 ACTIVE Prompt 决定；模型 key/revision 来自同事务锁定的数据库 Route。
- `no-retrieval.v1` 是当前唯一已实现 Context Policy；未实现 RAG 继续失败关闭。
- 未创建 Invocation，不调用 Provider，不改变 Schema、依赖或冻结 URL/响应。

验证使用 Windows 11、Python 3.13、PostgreSQL 18.6、真实 ASGI TestClient 与真实 Session/Project/Document/Prompt/ParseResult 数据链。结果：新 AI_TASK 请求返回 201；相同 Key 精确回放；旧客户端计数/hash 返回 400；授权返回 201；License 失效返回 403；数据库只有一套 Preview/Source/Plan/PlanSource，Preview 与 Plan 的 record count/payload fingerprint 完全一致，模型身份为数据库值，Invocation 为 0。首次验证因复用了 Schema 约束专用双花括号 Prompt 返回安全 503，改为独立可执行 Prompt 后在新数据库完整重跑通过；生产规则未放宽。

回归：定向 45 项和后端全量 **2206 项通过、3 项既有条件跳过、无失败**。开发 wheel SHA-256 `38884673913bd55efc194680f35513dd7a8e0020f728688458523a03a8aa5ced`。验证脚本执行后删除一次性数据库和临时结果目录，无客户数据或网络外发。

兼容与回滚：无新迁移；部署要启用 AI_TASK Preview，必须同时配置匹配的 Egress Policy、Task Policy、已准入 Prompt 和可读取的 ParseResult 根。回滚可移除 Task Policy 并重启，使 AI_TASK 计划失败关闭；已保存的不可变 Plan 历史保留。下一切片 `AI-04-A06-P04-P05` 绑定 Authorization、Task、授权快照与 Invocation 的同一 PlanRef，旧 NULL 历史不得执行。
