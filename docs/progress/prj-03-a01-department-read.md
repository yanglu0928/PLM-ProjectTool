# PRJ-03-A01：Department 授权列表读取

- 日期：2026-09-25；结果：PASS（内部查询链路，非公开 API）。
- 当前 Phase：Phase 2 Platform Core；WBS：PRJ-03-A01。
- 输入基线：Gate 2 冻结 DM-02 Department 与成员权限、API-01 Page/不透明 cursor、API-02 `PROJECT_DEPARTMENT_LIST`；前置 PRJ-01-A01～A06、PRJ-02-A01～A04 PASS。
- 涉及模块：Project Application/Infrastructure，复用 Auth-owned 当前 Session/User 证明及 ProjectAuthorizationService；涉及实体：Department、ProjectMember；API：仅内部部门列表查询，无新公开路由。
- 涉及权限：当前所有四种 ProjectMember 角色在 ACTIVE 成员与 ACTIVE Department 条件下可读所属项目；归档项目保留授权只读；暂停/移除成员、失效 Session 与跨项目访问拒绝。
- 验收标准：只读所属项目 ACTIVE/INACTIVE Department 历史、强 ETag、稳定内部 keyset 分页、1～200 page size、越权失败关闭、Windows 11 后端与 PostgreSQL 验证、wheel 构建。
- 风险：内部 after_department_id 不能直接暴露给 HTTP 客户端；API-01 要求后续公开路由封装范围和查询指纹绑定的不透明 cursor。

Changed：新增 Department 列表 Service/Repository。Project Repository 仅按 project_id 查询部门行，不访问 Auth 数据；Auth Port 在同一事务验证当前 Session。按 department_id 升序做稳定内部 keyset，返回活动与停用部门及强 ETag；所有角色权限以当前 ProjectMember/Department 状态判定，不使用 Session 缓存角色。

Files：Department 只读 Service/Repository、单元测试、一次性 PostgreSQL 验证脚本、决策/进度/版本记录。Migration：无；升级无需数据操作。API：无新公开路由或 Breaking Change。

Tests：Windows 11/Python 3.13 后端 289/289 PASS；Department 读服务覆盖率 95%；PostgreSQL 18.6 临时库四种角色、ACTIVE/INACTIVE 历史、两页 keyset、跨项目/暂停成员/Session/合成 License 拒绝、归档只读 PASS；wheel 构建 PASS。Windows Server 2025、Debian 13 本项未验证。

Known Issues：生产 License Guard、安全运行配置和公开 GET 未接线。只读服务当前将非业务异常统一映射为 `PROJECT_UNAVAILABLE`，合成 License 故障不会原样外泄；正式 License 错误映射需在公开 API 接线时复核。

Next：`PRJ-03-A02 Department 创建命令`；随后部门修改/停用、AUT-03-A07 与 PLT-02-A07 前置收口。
