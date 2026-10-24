# SOL-06-A11-P05：结构化专项列表 Windows 组合与真实 HTTP/PG 验收

- 日期/版本：2026-10-16 / `0.1.0-dev.0`。TraceLink：冻结 `SOL_SPEC_LIST` → A11-P02 内部读取 → A11-P03 专用游标 → A11-P04 可选 HTTP → 本项。当前 Phase 2。
- 编码前检查：A11-P04 已提供默认关闭的可选 Router；Windows 平台已有显式只读/读写模式、当前账户 Credential Manager 密钥模式、Session/License/Project read trust 与可弃 PostgreSQL 验收先例。本项只完成 Windows 组合和验收，不改 Schema、冻结 API、项目角色、License 权益或外部依赖。
- Changed：新增当前账户专用密钥引用 `project-structured-spec-version-list-cursor-v1`，密钥缺失、类型错误或读取异常均拒绝启动；在 Windows 显式只读和读写模式装配专项列表，默认模式仍为 404。组合复用真实 Session、License、项目成员授权和 PostgreSQL Repository，不暴露 payload/ref 正文。缺密钥启动失败时统一隐藏底层异常并释放数据库运行时。
- 验证：定向 `50 passed, 55 subtests passed`；后端全量 `3648 passed, 3 skipped, 5745 subtests passed`。Windows 11 可弃 PostgreSQL 18.6 + 真实 HTTP 通过 CREATE 后两版本、两页签名游标、当前成员读取、跨项目 404、缺 Session 401、未知查询 400、License 403，并回归原 CREATE/真实来源链。当前账户 Credential Manager 临时失密及加密备份恢复通过。开发 wheel 1399 条目且包含 Windows 专用密钥入口、组合与列表路由，SHA-256 `22c0109ba36e9d529de142481ad77023c37f1a4760ead13f2aacb9dd28b96ad3`。
- 验证偏差：首次后端全量出现 17 个生产入口合同失败，原因是已有测试公共装配未替代新增密钥工厂，生产代码按设计提前 fail-closed；补齐测试装配并增加“密钥缺失时双模式拒启且释放运行时”回归后全量通过，未放宽产品安全约束。
- 兼容性/升级/回滚：无 Migration、冻结 API Breaking、外部依赖或旧数据变化。Windows 升级前必须为实际服务账户安全供给并备份新密钥，且在目标账户验证恢复；未满足时应用按设计拒绝启动。回滚可恢复旧程序并保留无害的密钥项，业务历史不删除。Windows Server 2025/Debian 13 未实测。
- 限制：本次账户、License、公钥和游标密钥均为可弃合成验收条件，不构成正式信任或正式安装证据。前端列表/Edge 尚未完成；摘要不证明来源现时有效或 Review 已批准。专项修订/验证/送审、OutputArtifact、章节六维、Gate 3/Pilot/正式 Release 仍待。
- Next：`SOL-06-A11-P06` 新增项目内专项历史列表页与详情导航，明确 DRAFT/固定版本和最小摘要；随后以 Windows 11 Edge 连接真实 HTTP/PG 验收。
