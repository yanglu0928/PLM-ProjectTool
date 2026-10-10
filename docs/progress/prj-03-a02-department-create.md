# PRJ-03-A02：Department 创建命令

- 日期：2026-09-25；结果：PASS（内部命令，非公开 API）。
- 当前 Phase：Phase 2 Platform Core；WBS：PRJ-03-A02。
- 输入基线：Gate 2 冻结 DM-02 Department、SC-02/03 部门代码部分唯一索引、API-02 `PROJECT_DEPARTMENT_CREATE`；前置 PRJ-01-A01～A06、PRJ-02-A01～A04、PRJ-03-A01 PASS。
- 涉及模块：Project Application/Infrastructure，复用 Auth-owned 当前 Session/CSRF Port 与 AuditService；涉及实体：Department、ProjectMember；API：仅内部创建命令，无公开路由。
- 涉及权限：当前 ProjectManager、Session/CSRF、License、项目 ACTIVE；跨项目及其他角色拒绝。
- 验收标准：NFKC+trim 展示编码/名称、casefold 规范化编码、长度/控制字符验证、同项目活动编码唯一、并发冲突、Audit 同事务及回滚、Windows 11/PostgreSQL 验证与 wheel 构建。
- 风险：公开 POST 的持久幂等和生产 License 接线未实现。DM 的“项目内唯一”与 SC 的 partial unique 描述粒度不同；本项依据更具体的冻结 SC-03 索引将唯一性解释为同项目 ACTIVE Department，停用历史保留且允许代码复用，见 DEC-20260925-024。

Changed：新增内部 Department 创建 Service/Repository。创建前即时校验当前管理角色、项目与 Session/CSRF；使用 PostgreSQL 部分唯一索引的冲突目标防并发重复，冲突返回 `CONFLICT_DUPLICATE`；创建与 `PROJECT_DEPARTMENT_CREATED` Audit 同事务。展示 code/name 与项目创建使用相同 NFKC/trim、casefold 语义；不读取或修改其他项目部门。

Files：Project Department 创建 Service/Repository、单元测试、一次性 PostgreSQL 验证脚本、决策/进度/版本记录。Migration：无；升级无需数据操作。API：无新公开路由或 Breaking Change。

Tests：Windows 11/Python 3.13 后端 294/294 PASS；创建服务覆盖率 93%；PostgreSQL 18.6 临时库规范化、权限/CSRF/合成 License、跨项目、同项目冲突、双并发仅一成功、停用编码复用、Audit 回滚、归档拒绝 PASS；wheel 构建 PASS。Windows Server 2025、Debian 13 本项未验证。

Known Issues：生产 License Guard、公开 POST 幂等、安全运行配置和发行平台复验仍待后续；合成 Guard 不代表生产许可可用。

Next：`PRJ-03-A03 Department 名称/编码修改命令`，随后部门停用及 AUT-03-A07、PLT-02-A07 前置收口。
