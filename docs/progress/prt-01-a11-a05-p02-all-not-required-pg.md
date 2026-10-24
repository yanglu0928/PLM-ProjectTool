# PRT-01-A11-A05-P02：全 NOT_REQUIRED 分支的真实 PostgreSQL/HTTP 验收

日期：2026-10-08。范围：Windows 11、隔离 PostgreSQL 18.6/pgvector、合成项目与文件；只验证 Prototype 范围全部由项目经理确认“不需要原型”的分支，不代表客户确认，也不代表需原型/Approved PrototypeVersion/Link 分支或完整 A05 已通过。

编码前检查：延续 `CR-PRT-005`、Gate 2 冻结合同与 A04 显式可选装配；先确认既有 Requirement→PROTOTYPE 真实验收脚本可复用，55434 端口空闲且旧共享数据归属未知。仅在本轮创建的 ASCII Temp 目录启动独立数据库，不操作旧实例。复用现有受权服务与 HTTP Router，不开放正常生产入口。

真实检查：空库迁移至当前 head 且 Alembic 无新增差异；Requirement 批准后顺序进入 PROTOTYPE/v10；未注入可选制品存储时三类 Prototype HTTP 操作均拒绝；注入后缺范围决定仍拒绝；项目经理按固定批准 RequirementVersion 作 NOT_REQUIRED 决定，Audit 由真实服务写入且必须可独立证明。两项资格预览返回当前 Requirement 主体、受审轮次和来源 Evidence；按强 ETag 连续登记 `PROTOTYPE_SCOPE_DECISIONS`、`PROTOTYPE_COVERAGE` 两个 PASS，再推进到 SOLUTION/v13。原幂等键重复推进不增加历史；数据库核对当前阶段、两个 Checklist、唯一 StageTransition 和唯一决定 Audit。脚本结束先删本轮临时数据库，再停止实例，只删除本轮 Temp 目录。

首轮发现本地时区 `Asia/Shanghai` 的 `timestamptz` 被 Audit 适配器误判为缺失，详见 `CR-PRT-005` A05 兼容修订。修订只在 Audit 公共适配器边界将带时区的输入/读回值规范化到 UTC；无时区、时间倒序、超出五分钟和非唯一仍失败关闭。未更改 API、Schema、权限或授权判断。

验证结果：`PRT_01_A11_A05_P02_ALL_NOT_REQUIRED_HTTP_PG_PASS`；后端全量 3244 passed、3 skipped、4791 subtests passed。此验收只证明该分支在单实例合成负载下可顺序工作，不能推定 20 并发、其他平台、客户真实数据或正式生产可用。

兼容性/升级/回滚：无迁移、依赖或公开 API 变化；部署同步后端代码即可。若回滚时间规范化，必须保持 Prototype 生产注册关闭，不能跳过 Audit；历史记录保留。下一项为 Approved PrototypeVersion、有效 Link、真实 Document 制品和混合范围的 Owner/HTTP/PG 验证，再做失败关闭、并发与生产入口验收。Gate 3 仍 BLOCKED。

TraceLink：`CR-PRT-005` → Audit 时区化修订 → A05-P02 隔离 PG/HTTP 全 NOT_REQUIRED 证据 → A05 后续混合分支与生产开关。
