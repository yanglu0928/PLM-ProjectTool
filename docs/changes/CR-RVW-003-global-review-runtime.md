# CR-RVW-003：补齐 GLOBAL Review 运行合同

日期：2026-10-05。状态：依据 `CR-EXEC-001` 持续授权批准实施。Gate 2 原冻结提交 `64cdf09` 保留；本 CR 不修改既有 PROJECT API，也不把 Review 结果冒充 Capability 正式事实。

## 来源与冲突

冻结架构和数据模型要求 Review Root 同时支持 `GLOBAL` 与 `PROJECT`，Review 只持有审批状态，Subject Owner 在同一事务内锁定、验证并消费终态。现有 Schema0034/0035、ORM 与只读快照仓储已经实现两种 Scope；但创建、开轮、决策命令、持久服务、仓储以及 Subject DTO 将 `project_id` 固定为必填 UUID，并显式拒绝非 `PROJECT`。

CAP-01 CapabilityBaseline 是 GLOBAL Root。若沿用 PROJECT 命令，必须伪造 ProjectId 或错误要求项目角色；若 Capability 直接写 Review 表，则破坏 Owner 边界；若绕过 Review 直接把 Version 标记为 APPROVED，则无法证明真实评审、主题锁和结果消费。

## 方案比较与选择

- 不选伪造“系统项目”承载 GLOBAL Review：会混淆 Scope、权限、审计和幂等域，并产生并不存在的项目依赖。
- 不选 Capability 直写 `rvw_*` 表：违反 Review 独占写入和同事务 Subject Port 合同。
- 不选复制第二套 Capability 专用评审表：会造成两套审批状态机与 Gate 2 模型漂移。
- 选择在 Review 内核补齐已有 GLOBAL 数据合同：通用持久 DTO/仓储接受显式 `scope` 与可空 `project_id`；新增仅供受信 GLOBAL Owner 编排的内部创建、开轮、决策入口；现有 PROJECT service/router/URL/权限语义保持不变。GLOBAL 入口仍必须执行 Session、CSRF、License、DeploymentAdmin、当前 Reviewer 资格、幂等和 Audit，并要求已注册 Subject Owner。

## 实施分解

1. `CAP-01-A04-A01`：完成差距核查并登记本 CR，固定兼容、迁移、回滚和验证边界。
2. `CAP-01-A04-A02`：泛化 Review 内部持久 DTO/仓储为显式 Scope，并新增默认不挂 HTTP 的 GLOBAL Review 编排；PROJECT 回归必须全量通过。
3. `CAP-01-A04-A03`：实现 Capability Subject read/start/transition Port，以 Version 和来源当前事实作为真实主题锁与访问证明。
4. `CAP-01-A04-A04`：新增最小 Capability 状态守卫，终态消费与 Review 决策、Audit、幂等在同一事务中原子完成；仅 APPROVED 更新正式指针并 SUPERSEDE 旧正式版，RETURNED/WITHDRAWN 保留旧指针。

每项只解决一个明确边界。A02 不开放 Capability 正式状态；A03 不自行推进 Review；A04 不开放公开 HTTP。后续 CAP-01-A05 再接冻结 API 与生产组合。

## 兼容、迁移与回滚

- A02 优先复用现有 Schema0034/0035 已有 GLOBAL 列与约束，不修改表结构；现有 PROJECT 方法保留兼容包装，既有 `/api/v1/projects/...` 合同不变。
- GLOBAL 幂等域使用部署级 Scope，不借用或伪造 ProjectId；Audit 使用 GLOBAL scope 且 `target_project_id=NULL`。
- A04 如需 Schema0093，只替换 Capability 状态守卫，不改不可变内容列；有正式化历史时拒绝物理降级并采用向前修复。
- 可通过不装配 GLOBAL 编排/Capability Subject Owner 停止新流量；已提交 Review、Audit、Version 和正式指针历史保留，不删除回滚。

## 验证计划

- Review PROJECT 全量回归，证明既有创建/开轮/决策/撤回/读取语义未变。
- Win11/PostgreSQL 18.6 覆盖 GLOBAL 创建、开轮、多人决策、RETURNED/WITHDRAWN、幂等回放、并发冲突、撤权、License、Audit 回滚和 Scope 隔离。
- Capability 覆盖 Draft 锁定、锁期间禁止替换/修改、来源失效、APPROVED 原子指针、旧版 SUPERSEDED、RETURNED 后新 Version/新 Round、终态重放和故障全回滚。
- wheel 隔离回归和 migration drift 必须通过；Windows Server 2025 与 Debian 13 不在本 CR 当前验证证据中，仍为发行前独立目标。

## 风险与边界

GLOBAL Review 允许部署管理员组织评审，不代表管理员可单人绕过 reviewer 决策。Reviewer 当前资格必须来自 Auth Owner，不从历史 assignment 推断。Review APPROVED 也只有在 Capability Owner 成功消费且提交后才形成正式 Capability；任何中途异常整事务回滚。Gate 3、客户内容正确性、AI 质量、正式信任和三平台发行不因本 CR 自动通过。

## 实施进度

- 2026-10-05 / `CAP-01-A04-A02`：新增Review-owned GLOBAL submit/transition事务内核与仓储，双Scope Subject DTO按冻结合同开放；真实PG18.6完成两人APPROVED、WITHDRAWN、Audit、锁释放和Scope隔离，PROJECT回归不变。该内核仍要求受信caller提供认证/资格/License/幂等和真实Subject，未挂HTTP。下一项A04-A03。
