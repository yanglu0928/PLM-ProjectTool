# CR-EXEC-021：补齐 A17 上游客户评审员合成成员夹具

- 日期：2026-10-29
- 状态：已记录，待实施与托管验收
- 来源与证据：hosted run 40816002432 的基础 9 个 jobs、父包 PostgreSQL 生命周期、A17 投影、Caddy HTTPS、Workflow HTTP/CSRF/Audit、ASCII 输出、Document 来源证明、SectionVersion 校验及 Section Review 提交/批准均通过。随后上游 `validation/sol-03-a06-p03-a05-p03-a05-p02-full-source-pg/verify.py::_approved_requirement_v2` 在查询活动 `CUSTOMER_MEMBER` 后对空结果取值。A17 的上一层 browser fixture 为 `Synthetic Handover Customer`，但未保证其 ProjectMember 角色满足该上游 Requirement Review 场景。该问题是 synthetic reviewer setup 缺项，不是业务 API 错误；A27 尚未通过。
- 方案比较：A. 在 A17 合成 Section Review 已完成后，为隔离项目的同一合成 reviewer 明确准备 `CUSTOMER_MEMBER` 角色，供后续上游 Requirement Review 探针使用；B. 将上游验证改为任意成员并移除客户角色覆盖，弱化既有审批角色验收。选择 A，补齐测试的预期角色，不放宽被测业务检查。
- 基线差异：仅修改 A17 synthetic PostgreSQL fixture 的测试成员角色准备；不改产品授权逻辑、API、Schema、License 或用户数据。
- 影响与风险：角色变化限定在 disposable A17 数据库内，并安排在该 reviewer 已完成 Section Review 之后，减少对先前检查的影响；若数据库约束阻止，则停止并按实际角色模型调整 fixture。
- 回滚：删除该 synthetic role adjustment，只影响托管一次性数据。
- 验证计划：hosted Windows 2025 复跑；确认上游 Requirement Review 能找到活动 CUSTOMER_MEMBER、继续完成 PlanVersion Edge 和 PostgreSQL 状态，且服务停止、临时数据清理及候选完整性 markers 全部满足。否则 A27 保持未通过。
- 执行边界：仅 GitHub hosted runner，不在用户本机或 C 盘执行项目代码；不外发客户数据或 Secret。
