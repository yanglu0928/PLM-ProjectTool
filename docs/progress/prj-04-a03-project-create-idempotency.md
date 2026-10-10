# PRJ-04-A03：Project 创建同事务持久幂等

- Phase/WBS：Phase 2 Platform Core / PRJ-04-A03。输入：冻结 API-01 可重试 POST 幂等、API-02 `PROJECT_CREATE`、PRJ-01-A04 内部原子创建、通用收据 Migration `0015`；决策 `DEC-20260925-055`。正式 HTTP 前置原不满足，按项目 Skill 暂缓路由，先补内部事务能力。
- Changed：保留原内部 `create` 语义，新增要求合法 `Idempotency-Key` 的 `create_idempotent`。规范化 code/name/默认或显式部门与初始负责人形成请求指纹；按管理员 actor/操作/Key 预留收据，将 Project、首个 Department/Manager、Audit 与 ProjectId 收据同事务提交。相同请求重放返回最初 201 ProjectView 语义，不重复写入/审计；不同载荷拒绝 409。首次响应的 `created_at` 取不可变 Project 创建时间，code/name 用规范化原请求，state/ETag 固定首次 `ACTIVE`/`"v0"`，不会被后续 Project 更新污染。
- Files：Project 创建应用/SQL 只读创建时间、单元与临时 PostgreSQL 验证、决策/状态/版本记录。
- Migration：无；目标库需已有 `0015`。API：无新公开路由；旧内部调用不变。
- Tests：Windows 11/Python 3.13 后端 386/386 PASS；PostgreSQL 18 临时库并发同 Key 仅一 Project/审计、原响应重放、异载荷冲突、Audit 失败全事务回滚及原 Key 后续成功 PASS；开发 wheel PASS。临时库已删除，数据库服务停止。
- Result：Project 创建持久幂等前置 PASS；公开 POST、正式发行信任源、Windows Server 2025/Debian 13 与 Gate 3 未完成。
- Known Issues：通用收据只存一个非敏感 ProjectId，因此重放仅针对冻结 HTTP ProjectView；原内部 `CreatedProject` 的初始 Department/Member ID 不通过此方法重放。
- Next：PRJ-04-A04 Project 创建 HTTP 请求边界/管理员/CSRF/错误投影，再接显式平台组合。
