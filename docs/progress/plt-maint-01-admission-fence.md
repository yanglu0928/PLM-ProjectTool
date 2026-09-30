# PLT-MAINT-01 维护模式停写栅栏

日期：2026-09-30；Phase 2；A01 设计与编码前检查。

当前 Phase：Phase 2 Platform Core。当前 WBS：PLT-MAINT-01-A01 可靠停写栅栏设计；后续 A02 Schema、A03 Platform Port、A04 生产 API、A05 双 Worker、A06 跨进程验收。
输入基线：ADR-007/008、Gate2 原冻结 `64cdf09`、DOC-03-A03-P04-P04 阻塞证据、现有 Windows 生产组合、Audit/Parser Worker。
前置任务：Parser 独立进程合成 OCR 内部验证已通过；正式维护停写之前不得执行生产清理/升级。涉及模块：Platform、Audit/Parser Worker、Document 上传窗口和生产入口；设计阶段不改代码。
涉及实体：拟新增单行维护状态与 Audit 操作历史，须正式 Migration。涉及 API：不破坏 `/api/v1`；生产请求外层 admission，普通业务响应合同保持。涉及权限：仅受控部署账户启停维护；普通用户不能切换。
验收标准：CR 记录证据、方案比较、完整覆盖矩阵、迁移/回滚与真实并发验收门槛；任何未覆盖入口保持 BLOCKED。风险：会话级共享锁跨长 OCR/上传窗口增加数据库连接占用，需容量/超时测试；部分旧进程绕过门禁会使证明无效。

结果：A01 设计已登记 `CR-PLT-004`，尚无代码、Migration 或并发证据；A02 及整体 PLT-MAINT-01 均未通过。下一步先做 Schema 及最小状态源，不能用本设计文档解开 DOC-03 停写前置。

## A02 编码前检查：持久维护状态 Schema

当前 Phase：Phase 2 Platform Core。当前 WBS：PLT-MAINT-01-A02。输入基线：`CR-PLT-004`、Gate2 原0050增量链、Platform 现有 Base/Alembic。前置 A01 设计已登记；真实 admission 尚未实现。
涉及模块：Platform ORM 与 PostgreSQL18 Migration 0051；只新增一个系统单行状态表。涉及实体：维护状态/版本/数据库时间，不复制业务 Job、Upload 或 Audit。涉及 API/权限：无 `/api/v1` 与角色变化；写状态的正式命令属后续 A03。
验收标准：空库及含既有业务数据从0050升至0051，单行 RUNNING/v0；ORM parity、约束/不可删除和合法单步状态版本转换；原始数据不变；全新未使用状态可 down/re-up，有维护历史时 down 拒绝且原状态保留；Python3.13 全量回归、wheel。
风险：此表单独不能阻止并发请求/Worker，直到共享/排他锁与所有生产入口挂载后才可作为停写证明。只改 Schema，迁移前需人工备份并停写；回滚仅无历史的隔离环境可测试，生产不承诺自动降级。

结果：A02 Windows11 隔离 PostgreSQL18 Schema PASS。新 `20260930_0051` 增量只增单行 `plm.plt_maintenance_state`，默认 RUNNING/v0；数据库约束及触发器拒绝第二行、跳版/同态更新、DELETE/TRUNCATE，允许 RUNNING→MAINTENANCE→RUNNING 每次版本+1；有历史的 downgrade 拒绝且状态/迁移版本保留。空库 head→0050→head、有原 Auth 数据0050→head、ORM parity、后端全量1657（3既有跳过）、wheel 含 ORM/Migration PASS。隔离数据库删除、PoC PG 恢复停止；未迁移生产库。没有 admission Port、生产路由或 Worker 接线，此单行状态绝非维护静止证明，整体 PLT-MAINT-01/DOC-03 前置/Gate3仍未通过。

## A03-P01 编码前检查：只读共享准入 Port

当前 Phase：Phase 2 Platform Core。当前 WBS：PLT-MAINT-01-A03-P01。输入基线：`CR-PLT-004` 含连接丢失修订、DB0051/ORM、ADR007/008。前置 A02 Schema 内部 PASS；正式 API/Worker 未接入。
涉及模块：Platform PostgreSQL 专用短连接/会话级共享 advisory 锁与状态读取 Port；不写状态、不打开维护操作。涉及实体：只读 `plt_maintenance_state`。涉及 API/权限：无公开 API，不授权操作员切换。
验收标准：PG18/0051 RUNNING 下取得共享锁并保持至调用者外部窗口退出；MAINTENANCE/缺行/错库/锁竞争/DB失联失败关闭；释放共享锁与连接，不把连接丢失解释为静止。真实 PG18 双连接并发及单元回归、wheel。
风险：持有独立连接增加容量；长 I/O 中连接断开可使锁提前释放，完整静止证明须后续进程退出门禁，不能凭本项关闭维护模式。无 Schema/API/依赖变化，回滚停用未接入 Port。

结果：A03-P01 Windows11 内部 PASS。`PostgresMaintenanceAdmission` 仅接受 PG18，并在专用会话取共享 advisory 锁、读 DB0051 RUNNING 行后结束事务、保持会话锁贯穿调用者窗口，退出显式解锁/关闭；MAINTENANCE、排他锁竞争、旧 Schema/错库拒绝。隔离 PostgreSQL18 双连接验证两个共享并行、排他不可取得、释放后可取得、调用者异常不被遮盖且连接池不遗留锁；模拟杀死持锁 backend 时退出报错并证明排他方可取得锁，故不能以锁释放声称外部 I/O 已停止。单元2、后端全量1659（3既有跳过）、wheel PASS，随机库清理且 PoC PG 恢复停止。尚无排他状态命令、Audit、生产 API/Worker 接线或 OS 进程退出证明；A03 整体/维护模式/Gate3不通过。

## A03-P02 编码前检查：排他状态转换内部 Port

当前 Phase：Phase 2 Platform Core。当前 WBS：PLT-MAINT-01-A03-P02。输入基线：CR-PLT-004、DB0051、A03-P01 共享准入、现有 AuditService/UnitOfWork。前置 A03-P01 内部 PASS；全部生产入口尚未接线，因此本项只能是不可对外开放的内部能力。
涉及模块：Platform 状态转换 Port 和 Audit 写入；不改 API、Schema、Worker 或生产装配。涉及实体：单行维护状态和不可变 AuditEvent。权限：Port 仅接受由后续受控入口提供的非零已认证操作员 UUID；本项不伪称完成操作员认证/授权。
验收标准：PG18 专用会话排他锁限时等待、共享窗口未释放时拒绝；状态转换与 Audit USER 成功事件同事务；重复请求、反向状态、超时/数据库错误失败关闭且不泄漏锁；真实 PG18 双连接、后端回归和 wheel。
风险与回滚：锁被失联连接释放不证明 OS 进程退出，转换即使成功也不构成备份许可；上线前需全入口接线和进程退出证明。无 Schema/API/依赖变化；回滚不装配此 Port，测试库按隔离生命周期删除。

结果：A03-P02 内部 PASS。`PostgresMaintenanceTransition` 在 PG18 专用会话有限等待排他 advisory 锁，事务内更新 DB0051 状态/版本并经 AuditService 写 USER 成功事件，随后显式解锁；旧版本/同态重复拒绝，审计失败回滚。隔离 PG18 双连接验证未结束共享窗口时 50ms 超时拒绝、状态仍 RUNNING；释放后进入 MAINTENANCE/v1 并阻止新准入，再退出 RUNNING/v2；两条 Audit 前后态/操作员一致，审计故障零状态变化且连接池无锁泄漏。验证脚本三次通过，单元2、后端全量1661（3既有跳过）、wheel PASS；随机库清理且 PoC PG 恢复停止。操作员 UUID 在本 Port 中尚未认证/授权，无生产 CLI/API 装配、双 Worker 接线与 OS 退出证明，维护模式/Gate3不通过。

## A03-P03-P01 编码前检查：转换事务内操作员权限

当前 Phase：Phase 2 Platform Core。当前 WBS：PLT-MAINT-01-A03-P03-P01。输入基线：CR-PLT-004、A03-P02 转换 Port、Auth 已有 `SqlAlchemyLicenseImportAccess` 的 Session+CSRF+当前 DeploymentAdmin 核验。前置 A03-P02 内部 PASS；尚无受控 CLI/生产装配。
涉及模块：Platform 转换 Port 与 Auth 既有访问适配器，不新建权限规则。涉及实体：原状态与 Audit，Auth User/Session 锁定读取。涉及 API：无公开 API 变化。权限：将外部传入任意 UUID 改为同一状态转换事务内从当前 Session+CSRF 解析操作员，拒绝停用/撤权/过期/改密待处理账户。
验收标准：真实 PG18 合成 Admin Session 可进入/退出，错误 CSRF、非 Admin、停用/撤销等拒绝且状态/Audit 零变；共享锁超时、审计回滚和旧版本合同回归，全量后端、wheel。
风险与回滚：认证只验证应用内 Admin，不证明当前 OS 部署账户或旧版进程静止；CLI/部署限制和 OS 退出证据后续独立处理。无 Schema/API/依赖变更；回滚不装配 Port，保留历史变更记录。

结果：A03-P03-P01 内部 PASS。排他转换 Port 不再接受调用方自称操作员 UUID；在同一 Session 状态/Audit 事务中复用 Auth 的当前 Session+CSRF+DeploymentAdmin 锁定核验，解析真实 USER actor。隔离 PG18 合成管理员能进 MAINTENANCE/v1 与恢复 RUNNING/v2；错误 Session/CSRF、非管理员、停用账户、撤销 Session 均拒绝且状态/Audit 无新增；共享锁超时、旧版本与 Audit 故障回滚复验通过。后端全量1661（3既有跳过）、wheel PASS，随机库清理、PoC PG 恢复停止。尚无 OS 部署账户限制或受控 CLI，不能让运营侧执行切换；后续 A03-P03-P02 和 A04/A05/A06 继续。

## A03-P03-P02 编码前检查：Windows 本机受控操作入口

当前 Phase：Phase 2 Platform Core。当前 WBS：PLT-MAINT-01-A03-P03-P02。输入基线：CR-PLT-004、A03-P03-P01 同事务 Auth 证明、现有 Windows 当前账户 DB Credential Manager 来源及 LoginService/SessionService。前置内部排他能力/身份核验 PASS；生产 API/Worker 未接 admission，故不允许据本入口判定备份可开始。
涉及模块：本机 Windows 运维 CLI 组合，不改登录、状态、Audit、DB Schema 或公开 API。涉及实体：短期 Session、维护状态/Audit 复用。涉及权限：仅交互式当前 Windows 账户可读取其自身已配置 DB Vault 凭据，操作员另输入当前应用管理员用户名/隐藏密码；不接收 URL/密码/Token 的 CLI 参数或环境变量。OS 账户独占凭据的部署 ACL 须在正式账户验证。
验收标准：CLI 参数/非交互输入拒绝；短期 Session 不输出 Token，现时管理员身份在转换事务重验；状态冲突/共享锁/登录失败固定错误且无切换；成功进入/退出的返回值和 Session 收口；隔离 PG18 真实合成账号执行链、后端回归与 wheel。
风险与回滚：独立 CLI 即使可切换状态，尚无全部 API/Worker admission 与 OS 退出证据，不构成备份/迁移许可；正式账户 Vault 隔离、Windows Server 2025 与 Debian 入口仍待。无新 Schema/API/依赖；停用未启用 CLI 可回滚程序，维护历史状态不能删除。

结果：A03-P03-P02 Windows11 内部组合 PASS。`maintenance_windows` 仅本地交互、仅当前账户 Vault DB 凭据；运维用户名与隐藏口令经既有 scrypt/限流 LoginService 取得五分钟 Session，再经排他 Port 当前管理员同事务复验。隔离 PG18 正式 scrypt 初始管理员合成链验证 enter v0→MAINTENANCE/v1、旧版本拒绝、exit v1→RUNNING/v2，两条 USER Audit，错误口令无状态变化、全部创建 Session 已撤销，密码 bytearray 擦除。CLI 非 Windows/额外 Secret 参数先于 Vault 读取拒绝；后端全量1663（3既有跳过）、wheel 含 CLI PASS；随机库清理、PoC PG 恢复停止。未验证指定 OS 部署账户 Vault 独占、Server2025/Debian 工具、生产进程全覆盖及静止，故仅内部 PASS；生产切换/备份仍禁止。
