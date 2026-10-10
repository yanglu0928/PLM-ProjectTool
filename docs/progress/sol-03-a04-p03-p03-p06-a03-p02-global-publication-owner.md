# SOL-03-A04-P03-P03-P06-A03-P02：GLOBAL 候选发布/撤回内部 Owner

日期：2026-10-09。结果：`SOL_03_A04_P03_P03_P06_A03_P02_GLOBAL_PUBLICATION_OWNER_PASS`；仅内部管理员写链，不代表公开 API 或项目成员候选可用。

## 编码前检查

- 当前 Phase/WBS：Phase 2 Platform Core / 本任务。输入为 Gate 2 GLOBAL Reference 规则、CR-SOL-018、DEC-1148/1149、0157 封闭账本、既有 Auth DeploymentAdmin、License、来源资格、Audit 与持久收据。
- 前置已满足：ReferenceRoot/Version 复合身份、HUMAN 资格事件、脱敏确认及 Document/Evidence 真实证明均已具备；DB 写入口原封闭，故本项同时实施线性 Guard 0158。
- 单一问题：只允许管理员对当前合格 GLOBAL 版本显式审定非敏感标签，或对最新同版发布追加撤回；历史不更新/删除。
- 涉及模块/实体：Solution `ReferenceSolution`、`ReferenceVersion`、资格事件、GLOBAL 发布事件；Auth/License/Document/Evidence/Audit/收据仅使用既有受控端口。无公开 API、角色或依赖变更。
- 验收：版本/事件号并发控制，资格/来源/脱敏确认现时性，管理员/License 拒绝，同键原响应重放、Audit/收据同事务、受限 SQL Guard、空/有数据迁移升降重升、后端回归。
- 风险：原始名称误发布、旧版或失效确认继续可见、重复事件、审计失败留下半写。标签只能由管理员单独输入且此处不从原始名称回填；消费端仍须独立重证发布最新性和来源。数据库不承担管理员 Session 认证，必须经 Owner；公开路由尚未安装。

## 实施与验证

`GlobalReferencePublicationService` 在第一事务重验管理员 Session/CSRF，再校验 License；写事务再次重验管理员、按操作/请求指纹预留持久收据、锁 GLOBAL Root，读取当前 Version/最新 HUMAN 资格事件与发布事件。PUBLISH 要求当前 ELIGIBLE 并以同一事务重证固定 Document/Evidence 内容、来源指纹及最新有效人工脱敏确认；REVOKE 要求同版最新 PUBLISH，资格已限制时仍可补记撤回。操作必须给出预期固定版本和最新事件号；同键重放只返回原不可变事件，不新增 Audit。事件、单条 Audit、收据同事务提交。

线性 `0157→0158` 将发布事件 Guard 从全拒改为只允许当前 GLOBAL 版本、严格逐号、PUBLISH/REVOKE 状态图及 PUBLISH 最新 HUMAN ELIGIBLE 事件的 INSERT；UPDATE/DELETE/TRUNCATE 继续拒绝。空表可降回 0157 恢复全拒；有事件时拒降，需关闭入口并前向修复，不清除历史。

Windows 11 / 隔离 PostgreSQL 18.6：Guard 脚本验证空/有数据 up/down/re-up、drift、资格/版本/事件顺序、不可变 DML 和非空拒降退出 0；Owner 脚本使用真实 Session、License、Document/Evidence 文件与确认、SQL 仓储/Audit/收据，覆盖非管理员/旧版、物理文件篡改、发布/撤回/受限后重发拒绝、首次结果重放、Audit 故障原子回滚与同键并发重放，退出 0。定向单元 13 通过/4 子例；后端全量 3478 通过、3 跳过、5337 子例通过。现有 Alembic HNSW/计算默认值比较警告保留，`command.check` 无新增 upgrade 操作。

兼容/回滚：不改原冻结 API、旧数据或既有资格规则；迁移到 0158 后内部 Owner 才可写，默认应用尚不暴露路由。发布事件一旦存在，禁止逆向删除历史。下一项 `SOL-03-A04-P03-P03-P06-A03-P03` 建立管理员可选发布/撤回 HTTP 合同及真实 ASGI/PG 验收；随后 Windows 显式装配、项目端最小候选读面与浏览器。Gate 3 仍 BLOCKED；Server 2025/正式账户未在本项运行，Debian 13 实机按用户指令跳过。

TraceLink：Gate 2 DM-05/API-04 → CR-SOL-018 → DEC-1148/1149 → 0157/0158 → 本 Owner/PG → 管理 API → 项目候选读取。
