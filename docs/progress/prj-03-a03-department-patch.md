# PRJ-03-A03：Department 名称/编码修改命令

- 日期：2026-09-25；结果：PASS（内部命令，非公开 API）。
- 当前 Phase：Phase 2 Platform Core；WBS：PRJ-03-A03。
- 输入基线：Gate 2 冻结 API-01 强 ETag 与 API-02 `PROJECT_DEPARTMENT_PATCH`，DM-02 Department、SC-03 活动部门编码部分唯一索引；前置 PRJ-03-A01～A02 PASS。
- 涉及模块：Project Application/Infrastructure，复用 Auth-owned 当前 Session/CSRF Port 与 AuditService；涉及实体：Department；API：仅内部 PATCH 命令，无公开路由。
- 涉及权限：当前 ProjectManager、Session/CSRF、License、项目 ACTIVE、目标部门归属与 ACTIVE 状态；跨项目、其他角色、归档写入拒绝。
- 验收标准：名称/编码至少提供一个、NFKC+trim 与 casefold、强 expected_version、活动编码冲突、并发仅一成功、无变化不增加版本/审计、Audit 同事务回滚、Windows 11/PostgreSQL 与 wheel 验证。
- 风险：冻结模型没有 Department 字段级历史表；本项 Audit 记录操作人、目标和动作，不保留旧/新名称及编码。若后续要求逐版字段恢复，需单独 Change Request 和 Schema 增量，不能声称当前具备。

Changed：新增内部 Department PATCH Service/Repository；只允许 ACTIVE 部门修改，单次可修改名称、编码或两者。规范化与创建命令保持一致；锁定目标行并检查预期版本，检查同项目活动编码重复，数据库部分唯一索引作并发最终防线。真实变更版本+1并同事务写 `PROJECT_DEPARTMENT_PATCHED` Audit，无变化返回原 ETag 不制造事件。

Files：Project Department PATCH Service/Repository、单元测试、一次性 PostgreSQL 验证脚本、决策/进度/版本记录。Migration：无；升级无需数据操作。API：无新公开路由或 Breaking Change。

Tests：Windows 11/Python 3.13 后端 299/299 PASS；PATCH 服务覆盖率 93%；PostgreSQL 18.6 临时库规范化、权限/CSRF/合成 License、跨项目/重复编码/旧版本/停用/无变化、并发争用、Audit 回滚、归档拒绝 PASS；wheel 构建 PASS。Windows Server 2025、Debian 13 本项未验证。

Known Issues：生产 License Guard、公开 PATCH If-Match/安全运行配置未接线；字段级旧值历史未存储，Server 2025/Debian 13 本项未验证。

Next：`PRJ-03-A04 Department 停用命令`，随后完成 Project 模块公开安全接线所需前置。
