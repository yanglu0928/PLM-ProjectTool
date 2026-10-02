# TRC-01-A06-P01：Trace 单跳逐节点受权查询

日期：2026-10-02；Phase 2；状态：**内部单跳 PASS，完整图/HTTP 未完成**。输入为冻结 TraceService/TraceLink 与 API-02 逐节点授权合同、既有 `TRC-01-A05-P02` 内部创建及 DocumentVersion Owner；决策 `DEC-20261002-608`。原 Gate 2 冻结提交 `64cdf09` 未改。

新增内部 `TRACE_GRAPH_READ` 项目成员只读策略；服务在同一事务核当前 Session、License、目标 Project、起点固定版本 Owner，仓储只读目标项目指定方向/关系的 ACTIVE 边。返回前再逐边证明两端当前访问权：无权/未注册 Owner 的候选边完全省略，其他故障失败关闭；原始候选窗口最多 `limit+1`，只返回受权固定引用与布尔 `truncated`，不返回标题、正文、无权节点身份或数量。当前只提供单跳、最多 100 原始候选，不装配公开图/列表 API，不把窗口结果冒称完整链路。

验证：单元新增 6 项（项目/会话/License/起点、撤权、跨项目、方向、候选上限等）；隔离 PostgreSQL 18.6 自启动临时库验证真实 Session、项目成员、上下游、关系过滤、跨项目拒绝、目标文件 RESTRICTED 后隐藏边、License 失效拒绝，并回归原创建/幂等/审计/环拒绝。首次旧验证脚本因固定端口服务未运行连接超时，改成自带隔离 PG 后 PASS；全量回归首次因授权策略数量断言旧值 29 失败，改为 30 并补只读权限断言后重跑：1863 项运行、3 跳过、无失败。开发 wheel SHA-256 `0369bc1c7d853c70ff048fe2483f8dbb47540bceafdc39fee077b66d86037cc6`。

兼容/升级/回滚：内部 Application/Repository 与项目只读策略增量；无公开 API、Schema/Migration、依赖或数据回填。不装配此服务即可保持旧行为，既有 Trace 历史不变。下一步必须补有界多跳、稳定游标/页、逐节点防泄露与其他真实业务 Owner，再挂冻结 HTTP；正式信任、Server 2025/Debian、质量/UAT/Gate 与发行包均未因此通过。
