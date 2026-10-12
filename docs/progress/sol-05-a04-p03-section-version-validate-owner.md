# SOL-05-A04-P03：SectionVersion VALIDATE 内部 Owner

- 日期/版本：2026-10-12 / `0.1.0-dev.0`。承接 A04-P01 前置核查、A04-P02 报告合同、冻结 API-04 与 CR-SOL-003；实施选择记于 `DEC-20261012-1189`。
- 范围：补冻结操作 `SOL_SECTION_VERSION_VALIDATE` 的项目经理/实施成员授权映射；在有效 License、Session/CSRF、项目及 ACTIVE Section、固定 Version 成立后，复用 Document/Requirement/Evidence 的现时来源证明。固定版本读仓库要求版本/首响应及引用集合一致。缺失的 Trace/Spec 可信 Owner 与含糊来源故障均记 `UNAVAILABLE`，不声称可评审。
- 一致性：首次验证同事务追加 `SOL_SECTION_VERSION_VALIDATED` Audit 和持久 Idempotency Receipt；Audit SUCCESS 只表示命令执行，是否有效/可评审由六维报告另述。同 Key 重放仍重查权限和 License，但从绑定的 Audit 原因码恢复首次观察，不重采来源。审计失败整事务回滚；版本内容、Review 和批准指针均不修改。
- 验证：定向单元角色、失效来源、重放、审计缺失及故障回滚；Windows 11 可弃 PostgreSQL 18.6、真实 Auth/Document/Requirement/Evidence 与物理文件合成链通过，验证原结果、现时 Evidence 失效、新 Key `UNAVAILABLE`、原 Key 稳定以及 Audit/Receipt 数量与原子性。完整后端回归结果见根目录 `STATUS.md`。
- 兼容/升级/回滚：无 Schema、Migration、冻结 API 路径或依赖变化；仅补冻结角色操作映射和未装配内部 Owner。可撤可选 Owner 代码与策略，已有 Audit/收据历史不能删除。当前无公开 VALIDATE HTTP 或 Windows 装配。
- 限制/下一项：Trace/StructuredSpec 章节证明、HTTP、Windows 组合与实际浏览器、正式目标账户/HTTPS/公钥、Server 2025、性能、Gate 3、Pilot 均未因此通过。下一项 `SOL-05-A04-P04`：可选 HTTP 合同，保持默认路由关闭，验证真实 Owner 错误和报告映射。
