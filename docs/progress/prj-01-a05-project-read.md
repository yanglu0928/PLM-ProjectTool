# PRJ-01-A05：Project 列表与详情读取

- 日期：2026-09-25；结果：PASS（内部查询链路，非公开 API）；依据：冻结 API-01 `Page<T>`/强 ETag、API-02 `PROJECT_LIST`/`PROJECT_GET`、DM-02 单有效成员约束、DEC-20260925-017。
- Changed：License Guard 后在同一查询事务验证当前 Session/User/凭据版本，再由 Project 模块重新读取 ACTIVE 且已生效成员与 ACTIVE Department；列表仅包含当前有权 Project，详情把不存在/跨项目/无成员统一隐藏。ARCHIVED 对授权成员保持可读。ProjectView 返回 code/name/state/created_at 与 `"v<lock_version>"` 强 ETag；单有效成员不变量下列表最多 1 项，Page 的 `next_cursor` 为 null。
- Files：Auth-owned Session 只读身份 Port、Project 查询 Service/SQL Repository、单元测试、一次性 PostgreSQL 验证脚本、决策/进度/版本记录。Migration：无。API：未挂公开 GET 路由；后续 HTTP 层仍需 Envelope/trace/error 映射。Permission：不复用登录摘要，DeploymentAdmin 不因部署身份自动看见项目。
- Tests：Windows 11/Python 3.13 后端 252/252 PASS；查询服务覆盖率 98%；PostgreSQL 18.6 临时库多用户隔离、归档可读、成员暂停/未来生效/部门停用即时过滤、Session 撤销、强 ETag 递增、合成 License 拒绝 PASS；wheel 构建 PASS。Windows Server 2025、Debian 13 本项未运行。
- Known Issues：生产 License/安全运行配置未接线，公开路由仍不存在；合成 Guard 不代表生产授权可用。列表由当前冻结单有效成员模型最多返回一项，若将来正式变更为多项目成员，必须补齐 API-01 不透明 keyset cursor，不得直接暴露原始 UUID 游标。
- Next：`PRJ-01-A06 Project 元数据修改与归档内部命令`；随后成员/部门管理及公开 API 安全装配。
