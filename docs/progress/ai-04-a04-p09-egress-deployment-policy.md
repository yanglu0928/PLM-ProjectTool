# AI-04-A04-P09：Egress 正式部署策略来源与 Windows 写平台挂载

- 日期：2026-10-03
- 结果：PASS（Windows 11 / PostgreSQL 18.6；无真实外发）
- 依据：CR-AI-013、DEC-713、AI-04-A04-P08

Changed：Bootstrap 新增最多16条非敏感、版本化 `ai_egress_policies`。每条策略严格固定 Preview 的operation/data category、TTL、记录/字节/Token/重试上限和风险代码，并固定批准角色与数据区域；不允许URL、API Key、正文或任意扩展字段。启动时将配置快照转换为不可变 Preview Registry 与 Approval Policy，畸形配置以固定消息失败关闭。

Windows 组合只在显式 `--platform-write` 且策略非空时创建 Egress Router。默认应用、登录模式和只读平台即使配置存在也不挂载四条 Egress 路径；写模式无策略时只关闭 Egress，不影响其他已批准的平台写能力。策略存在但构造或组合失败时，整个写平台启动失败，避免部分发布。

Tests：新增部署策略单元6项，覆盖YAML、严格形状/边界、重复/秘密字段、语义值、角色/区域允许与拒绝、缺失关闭和组合依赖；生产组合合同32项 PASS，明确只读404、写模式挂载；Windows 11/PG18.6 使用Bootstrap生成的正式策略对象完整复跑P08真实Session/Project/Document Owner、Preview/Authorization/Audit/Receipt、重放/隔离/撤销/License拒绝链；后端全量2136项运行、3项既有环境跳过、零失败。

Migration/API/依赖：无Schema/Migration或新依赖；不修改冻结四条API，只改变满足部署配置时的Windows写平台可达性。开发wheel SHA-256 `7eeafd306f5d45efd283fdc3c1d9919090afa585ece13f4737bf99d1be6cfe5e`，不是最终交付包。

升级/回滚：受控编辑Bootstrap、验证非敏感策略并重启写平台即可启用；删除全部 `ai_egress_policies` 后重启即恢复四路由404。既有Preview/Authorization/Audit历史不删除、不改写。策略版本或边界变化应使用新reference，旧历史继续按不可变快照审计。

Known Issues：正式发行License/目标运行账户信任材料、Server 2025、真实Provider调用、发送前撤销重验、Gate 3/UAT/最终程序包仍未由本项关闭；Debian 13按用户要求暂不验证。Next：`AI-04-A05-P01` 核对冻结AI Task公开创建/读取合同与现有内部原子创建、Job及Egress Owner的组合差异。
