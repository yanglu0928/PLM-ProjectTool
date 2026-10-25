# AI-04-A06-P04-P04-A04 AI_TASK Preview 与 Content Plan 原子事务

日期：2026-10-03；状态：`PASS`（Windows 11 / PostgreSQL 18.6）；依据 CR-AI-016、DEC-731～737、Schema0072。该切片完成内部应用事务，公开 HTTP 尚未切换到新请求体，生产组合仍未装配。

`CreateEgressPreview` 增加可选 `ai_task_plan` 内部合同。存在该合同的 AI_TASK 请求必须把客户端派生的 `estimated_record_count/payload_fingerprint` 留空；Service 在同一事务内解析业务 Source、锁定 Provider/Config/Model、调用 Prompt/Document Owner 构建确定性 Envelope，再以服务端 record count/payload bytes/input tokens/fingerprint 写 Preview，并写入同一 Preview 的唯一 Content Plan/Source。Egress Route 补齐数据库当前模型的 provider model key/revision，Plan 不接收客户端路由版本。

同一幂等 Key 重放不重新解析 Source/Prompt，而是读取原 Preview 并要求其不可变 Plan 仍存在且 Project/Purpose/payload/record count 一致；缺 Plan 或历史漂移失败关闭。Task 参数进入请求指纹，改变参数的同 Key 请求返回幂等冲突。旧内部非 Plan 路径与非 AI 操作继续保留，A05 在公开 AI_TASK HTTP 边界强制新形态。

验证：新增2项原子服务单元并回归相关12项；Windows 11 一次性 PostgreSQL 18.6/私有临时结果证明服务端 Envelope、Preview/Plan/Source/Audit/Receipt 原子提交、精确重放、Task 参数冲突、Audit 故障全回滚及零 Invocation/Provider I/O。旧 Preview 服务 PG 链重跑通过。后端全量 **2204项运行、3项既有环境跳过、无失败**；开发 wheel SHA-256 `3b4bae40ee433e65dcee8e43e52a72c40fe33834a1172de357e0b7ce0487ef99`。

无 Migration、公开 API、依赖或网络变化；Schema0072 历史语义不变。回滚为不装配可选 Builder/Plan Owner并继续关闭新 AI_TASK HTTP。下一切片 A05 修改 `/api/v1` Preview 请求合同：AI_TASK 必须提交 `ai_task_plan` 且不得提交客户端派生摘要；其他 operation 保持原字段。
