# TRC-01-A03-P01：RequirementVersion Trace 目标受权证明

- 日期/版本：2026-10-12 / `0.1.0-dev.0`。来源：Gate 2 Trace/REQ-03 冻结合同 → DEC-1194 → DEC-1195 → 本项；目标为下一项 SectionVersion Owner 与之后的 `IMPLEMENTS` 覆盖证明。
- 范围：RequirementVersion 读服务新增调用方事务内的轻量固定目标证明，当前 License、Session 和 `REQ_VERSION_GET` 项目成员授权每次重验；仓储仅取版本/根/项目/状态身份。组合层 `RequirementVersionTraceOwner` 支持冻结三字段公开解析及内部目标再证明，跨项目/无权限隐藏为未找到，License 明示拒绝，异常失败关闭。DRAFT 可作历史 Trace 目标；RESTRICTED 不可作新证明。本证明不代表已批准、现时有效、已覆盖或客户确认。
- 验证：定向单元 11 项/7 子例通过；一次性 Windows 11 PostgreSQL 18.6 真实迁移/Schema drift、同事务 DRAFT、跨项目、缺失版本、无效会话、License 关闭和无额外 Audit/收据通过；后端全量 3590 通过、3 跳过、5608 子例；开发 wheel 构建通过。首次真实 PG 验证尝试直接修改版本状态，被既有 Review Owner 数据库 Guard 正确拒绝；已去掉该不合规夹具操作并重跑通过。RESTRICTED 负例由单元验证，未执行真实 Review Owner 状态迁移。首次测试驱动捕获启动进程的管道造成等待，修正驱动并复跑；首轮残留已停止的隔离临时目录单独清理。
- 兼容/升级/回滚：无 ORM Schema、Migration、公开 API、权限矩阵、新依赖或历史数据变化；新增 Owner 尚未装配公开 Trace 创建路由，可撤新端口/桥接回滚，旧版本和 Trace 历史不动。
- 已知问题/下一项：真实受限状态迁移、SectionVersion 目标 Owner、`IMPLEMENTS` 当前有效覆盖、SOL-06、章节固定 Spec 引用、正式信任/性能/Server2025、Gate 3/Pilot 均未通过；Debian13 实机按用户指令跳过。下一项 `TRC-01-A03-P02` SectionVersion Trace 目标受权证明。
