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

## A04-P01 编码前检查：ASGI 写窗口准入中间件

当前 Phase：Phase 2 Platform Core。当前 WBS：PLT-MAINT-01-A04-P01。输入基线：CR-PLT-004、ADR-012、A03-P01 共享 Port、现有 `create_app` 与 Trace/Error 响应合同。前置共享 Port PG18 内部 PASS；正式生产组合尚未接线，本项只做可选中间件与生命周期验收。
涉及模块：Platform ASGI middleware 与 `create_app` 可选注入；不更改业务 Owner 或生产组合。涉及实体：不新增，仅读维护状态。涉及 API：冻结 `/api/v1` 路由不变；非 GET/HEAD/OPTIONS 的 HTTP 请求在路由前取得共享锁，覆盖请求正文流与响应/后台任务结束；失败统一 503 `SYSTEM_UNAVAILABLE` 带 trace_id。涉及权限：不替代原 Session/CSRF/License/Project 授权。
验收标准：合成异步流/后台任务证明锁持续至 ASGI 完成、异常释放、GET/健康无锁，MAINTENANCE/排他竞争/DB 错误失败关闭；默认 app 无注入不改变行为；后端全量与 wheel。
风险与回滚：同步 PG 准入可能短时占用事件循环，须给独立 Engine 有界连接/池超时并在性能门槛验收；会话失联时外部 I/O 可继续，仍需进程退出证明。当前只做中间件，不宣称生产 API 已全覆盖；回滚不注入该中间件。

结果：A04-P01 可选 ASGI middleware 内部 PASS。`create_app` 仅显式注入才启用，Trace 外层保证失败响应仍有 trace_id；非安全 HTTP 方法的共享准入覆盖请求正文流、响应流及 Starlette 后台任务，异常时释放；MAINTENANCE 返回固定503 `SYSTEM_UNAVAILABLE`，GET/HEAD/OPTIONS 不占锁。隔离 PG18/ASGI 并发证明写请求阻止排他、完成后释放，MAINTENANCE 阻止业务调用而 GET/健康仍可访问。单元4、后端全量1667（3既有跳过）、wheel PASS；随机库清理、PoC PG 恢复停止。尚未生产组合接线、GET副作用矩阵/性能/DB失联外部I/O处理，不能声称 A04 整体或停写证明完成。

## A04-P02 编码前检查：生产组合与 GET 副作用覆盖

当前 Phase：Phase 2 Platform Core。当前 WBS：PLT-MAINT-01-A04-P02。输入基线：CR-PLT-004 的 GET 副作用修订、ADR-012、A04-P01 中间件、Windows 三种显式生产组合。前置中间件内部 PASS；正式信任锚/目标 OS 账户仍未供给，只能隔离合成验收。
涉及模块：Platform ASGI 路由准入策略与 Windows 显式生产组合；不改 Document/Audit 业务 Owner。涉及实体：无 Schema。涉及 API：保持冻结路径/响应；非安全方法及四个有错误路径 Audit 写的 GET content 下载持共享锁，健康与纯读 GET 放行。涉及权限：原 Session/CSRF/License/Project 继续为最终业务授权；维护状态先拒绝。
验收标准：路由矩阵与四 GET 下载准入、生产组合所有模式注入有界独立 PG18 Engine；MAINTENANCE 下登录、上传/管理写与下载拒绝、健康/纯读 GET 可用；RUNNING 下现有链不退化；资源在 lifespan 释放，真实 PG18/HTTP、回归和 wheel。
风险/回滚：独立连接池按并发/长下载容量规划，不能用一次性测试宣称 20 并发 P95；连接意外丢失后业务持久化前仍需额外复核，OS 进程退出证明保留。无新 Migration/公开 API/依赖；回滚不装配生产中间件，维护历史不删除。

结果：A04-P02 Windows11 隔离生产组合内部 PASS。修正中间件使 Document 版本正文和 Audit Export 正文四个 GET content 路由持共享锁，其他纯读 GET/健康不占锁；三个显式 Windows 组合均注入独立有界 PG18 Engine（最多20专用连接、2秒池/连接等待）并随 lifespan 清理。隔离 PG18 `0051`、合成信任源下，三组合 RUNNING 真实 scrypt 管理员登录200，MAINTENANCE 登录503/健康200/Session GET 可读；写组合上传 POST 与四种 GET content 均503。旧纯契约测试改为显式准入替身，真实 PG 验证保留；后端全量1668（3既有跳过）、wheel PASS，随机库清理且 PoC PG 恢复停止。正式目标账户与 Server2025/Debian、20并发性能、连接丢失后业务发布复核、双 Worker/OS 静止仍待，A04 整体及维护模式/Gate3不通过。

## A05-P01 编码前检查：Audit Worker 单步共享准入

当前 Phase：Phase 2 Platform Core。当前 WBS：PLT-MAINT-01-A05-P01。输入基线：CR-PLT-004/ADR-012、Audit Worker Loop/Step 与 A03-P01 PG18 共享 Port。前置 API 显式组合内部验证已通过；Audit Worker 可独立接线，但未装配生产 Windows 进程时只能内部 PASS。
涉及模块：Audit Worker 调度循环可选 admission Port，不改 Claim/Executor/Owner 业务事务。涉及实体：仅只读维护状态与会话锁。涉及 API：无。涉及权限：原 SystemActor/User/Project/License 不变。
验收标准：每次 step 领取/执行/扫尾期间持共享锁，idle 等待不占锁；维护状态/排他竞争拒绝下一步，停止及异常能释放；严格原 Loop 类型与既有执行回归；真实 PG18 竞态、后端全量和 wheel。
风险/回滚：若连接意外释放，当前文件 I/O 仍可能继续，OS 进程退出证明和持久化前连接复核另验；长导出持独立连接增加容量。无 Schema/API/依赖；未接 Windows 组合时回滚不注入 gate。

结果：A05-P01 Audit Loop 内部 PASS。新增可选 admission 协议，仅在 `step()` 的扫描/领取/执行窗口持锁；idle sleep 无锁，原 Loop/Step 类型不变。隔离 PG18 + 合成 Audit Step 并发验证当前 step 排他锁被拒、完成后可取得、MAINTENANCE 阻止新 claim；单元 idle 不持锁，后端全量1669（3既有跳过）、wheel PASS；随机库清理与 PoC PG 恢复停止。尚未 Windows Audit Worker 入口注入、真实导出长 I/O/失联/进程退出验证；整体 A05/维护模式/Gate3不通过。

## A05-P02 编码前检查：Windows Audit Worker 进程装配

当前 Phase：Phase 2 Platform Core。当前 WBS：PLT-MAINT-01-A05-P02。输入基线：CR-PLT-004/ADR-012、A05-P01 Audit Loop 可选准入、当前账户 Windows DB Vault 与 WorkerDatabaseRuntime 资源生命周期。前置 A05-P01 内部 PASS；Parser Worker 尚未接线。
涉及模块：Platform Worker runtime 的可选独立 PG18 admission Engine 资源所有权、Windows Audit Worker 装配；不改 Audit Owner 事务。涉及实体/API：无 Schema/公开 API 变更。涉及权限：SystemActor、License/User/Project 原检查保留；维护状态新增过程准入，不替代业务授权。
验收标准：Windows 显式 Worker 入口只从当前 OS 账户 Vault URL 建立受限准入 Engine，构造失败和静止退出均释放；RUNNING 下真实导出 Step/窗口、MAINTENANCE 拒绝新领取、并发排他竞争；现有 CLI 契约/真实 PG 回归、wheel。
风险/回滚：目标账户 Vault 独占、Server2025/长期导出/连接失联仍需验；Parser 独立进程尚无门禁，维护整体仍不可启用。无 Migration/公开 API/依赖；停用装配并恢复匹配版本程序，不清除维护历史。

结果：A05-P02 Windows11 隔离组合内部 PASS。WorkerDatabaseRuntime 仅显式请求时创建独立单连接准入 Engine，构造失败及静止退出释放；Windows Audit Worker 同一次当前账户 Vault URL 装配并向 Loop 注入。真实 PG18、临时 Windows Vault 凭据与 SystemActor、合成 License 下的实际导出 Step 验证共享锁覆盖文件发布窗口，排他锁不能进入；MAINTENANCE 下 Worker 拒绝下一步且业务表快照不变。后端全量1671（3既有跳过）、wheel PASS；临时凭据与随机库清理。正式发行公钥/目标部署账户 ACL、Server2025、长导出失联和 OS 进程退出未验，Parser 仍未接门禁，A05/维护模式/Gate3/发行包不通过。

## A05-P03 编码前检查：Parser Worker 单轮共享准入

当前 Phase：Phase 2 Platform Core。当前 WBS：PLT-MAINT-01-A05-P03。输入基线：CR-PLT-004/ADR-012、A03-P01 PG18 共享 Port、现有 Parser Loop 扫描/领取/执行/空闲等待语义。前置 Audit Worker 装配已内部 PASS；Parser Windows 进程仍未装配维护门禁，本项只做 Loop 可选 Port。
涉及模块：Parser 调度循环，不改 Document/Jobs/Audit Owner、OCR 引擎或公开 API。涉及实体：仅读维护状态，不增 Schema。涉及权限：现有 SystemActor/当前 User/Project/License 继续判断；共享准入不替代业务授权。
验收标准：一轮 expired-cancel 扫描及 parse step 均持同一共享锁，stop/异常释放，idle sleep 无锁；MAINTENANCE 与排他竞争拒绝新扫描/领取；原无注入行为不退化；隔离 PG18 并发、单元、全回归与 wheel。
风险/回滚：OCR 长 I/O 中连接意外丢失不会自动杀止进程，仍需发布前复核和 OS 退出证明；Windows 生产进程需后续独立接线。无 Migration/API/依赖；回滚不装配该可选 Port。

结果：A05-P03 Parser Loop 可选单轮共享准入内部 PASS。一次取消到期扫描与 Parser Step 处于同一准入窗口，停机/异常会退出窗口，idle wait 在锁外。隔离 PG18 双连接验证扫描及 Step 均拒绝排他锁、完成后释放；MAINTENANCE 下扫描/领取计数均不增加。单元新增2、后端全量1673（3既有跳过）、wheel PASS，随机测试库清理。Windows Parser 进程尚未注入，真实 OCR 长 I/O/失联、目标账户及 OS 静止未验；A05/维护模式/Gate3/发行包不通过。

## A05-P04 编码前检查：Windows Parser Worker 装配

当前 Phase：Phase 2 Platform Core。当前 WBS：PLT-MAINT-01-A05-P04。输入基线：CR-PLT-004/ADR-012、A05-P03 Parser Loop Port、A05-P02 WorkerDatabaseRuntime 专用准入 Engine、现有 Windows Parser 启动/模型信任链。前置 Loop 与 Audit 组合内部 PASS；正式公钥/部署账户及 Server2025 未供给。
涉及模块：Parser 显式组合与 Windows 进程入口；不改 OCR 引擎、Job/Document/Audit Owner 或公开 API。涉及实体：维护状态只读，无 Schema。涉及权限：当前账户 Vault、SystemActor、License/User/Project 原检查不变。
验收标准：入口从同一次当前账户 Vault URL 创建并拥有准入 Engine，向 Parser Loop 传递；构造失败/静止退出释放；真实隔离 PG18 与合成文件的 Worker 运行中持锁、MAINTENANCE 下不扫描/领取，原 CLI 合同和全量回归/wheel PASS。
风险/回滚：连接意外释放、OCR 长 I/O/正式公钥/目标账户 ACL/OS 进程退出与 Server2025 仍须单独验证。无 Migration/API/依赖；可通过停用组合装配回滚，不抹除维护历史。

结果：A05-P04 Windows11 隔离进程组合内部 PASS。Windows Parser 由同一次当前账户 Vault URL 装配专用准入 Engine，显式传入 Loop，进程静止后释放；单元入口传递/失败清理通过。隔离 PG18、合成 License/SystemActor、真实离线 PP-OCRv5 模型及独立 Windows 子进程下，MAINTENANCE 时待处理 Job 保持 PENDING，恢复 RUNNING 后扫描 PDF 产出唯一 OCR_LINE/ResultRef、Job SUCCEEDED；父进程观察到 OCR 子进程持共享锁。后端1673（3既有跳过）、wheel PASS，随机库清理。仓库中文路径模型初始化失败、ASCII 缓存路径成功的发行偏差另记 CR-PAR-005；正式公钥/目标账户/Server2025、连接丢失后 OS 静止和性能未验，A05/维护模式/Gate3/发行包不通过。

## A06-P01 编码前检查：生产进程与独立写入口清单

当前 Phase：Phase 2 Platform Core。当前 WBS：PLT-MAINT-01-A06-P01。输入基线：CR-PLT-004/ADR-012、A04 API 接线、A05 双 Worker 接线、仓库当前 Python Composition Root 与 Alembic env。前置双 Worker Windows11 内部 PASS；目标部署清单/服务管理器尚无正式发行配置。本项只出入口证据矩阵，不实施不受控停服或生产迁移。
涉及模块：Platform/Release 运行入口清单与维护流程，不改 Owner 事务/API/Schema。验收标准：以源码枚举 HTTP、两 Worker、运维 CLI、首次初始化、Alembic、Vault 工具及开发工厂，区分应用数据写/OS 凭据写/DDL/只读；每种说明门禁、运行条件、静止证据和未覆盖风险，供下一 WBS 装配/进程验收使用。
风险/回滚：静态扫描不证明实际部署进程、Windows Service/Server2025/Debian、外部脚本或旧版应用已退出；不把矩阵当 Gate3/备份许可。文档可追溯修订，无运行迁移。

结果：A06-P01 静态入口矩阵完成，详见 `docs/progress/plt-maint-01-entrypoint-inventory.md`。明确正式 Windows API 三模式与 Audit/Parser 两 Worker 已接共享准入，但首次管理员初始化和 Alembic 是独立特权写入口，OS Vault/Secret 变更也不受 PG 锁管；裸工厂不得当生产入口。仓库未见正式服务定义、进程/PID/版本握手、Debian 组合及统一受控 Migration 执行器；旧版/未知进程可绕过。该项只完成清单，不作真实进程静止证明，CR-PLT-004/Gate3/发行继续 OPEN。

## A06-P02-P01 编码前检查：Windows 只读进程候选盘点

当前 Phase：Phase 2 Platform Core。当前 WBS：PLT-MAINT-01-A06-P02-P01。输入基线：CR-PLT-004/ADR-012、A06-P01 入口清单及 Windows 当前进程只读 CIM 接口。前置静态清单完成；正式服务/目标账户/安装根尚未配置，本任务不得输出“备份许可”。
涉及模块：Platform Windows 只读诊断入口，不改 API/Worker 业务、维护状态或数据库。涉及实体：OS 进程观察值、候选 PID/理由的脱敏报告；不新增持久实体。涉及 API：无。涉及权限：当前 OS 调用者仅能读取其有权查看的进程；不可枚举/不可识别一律标记未知，不能宣称静止。
验收标准：按指定部署账户 SID、受控运行目录和已知入口模块识别候选，保留未知/不可见状态；报告不含命令行/环境/Secret；非 Windows 和 CIM 故障失败关闭；合成分类测试、Windows11 实际只读枚举与 wheel。
风险/回滚：CIM 不保证识别改名/移址旧版程序，任何零候选结果仍仅为诊断，不构成服务退出/文件句柄收敛/版本握手证明；不停止进程、不触碰生产数据。回滚删除独立诊断入口，无 Migration/API/依赖。

结果：A06-P02-P01 Windows11 只读诊断内部 PASS。CLI 从指定部署 SID、绝对本地运行目录及已知产品入口三路识别候选，仅输出 PID/理由与不可读计数，固定 `DIAGNOSTIC_ONLY` 和 `backup_or_migration_authorized=false`；命令行/路径不外发。首次逐进程 CIM Owner 查询超过30秒按预期失败关闭，改用一次 CIM 元数据快照+原生只读 Token SID 后，本机约380进程在0.7秒完成，当前开发账户的大量进程正确列为候选、不可读206；这不是目标专用部署账户验收。合成分类/脱敏/非Windows单元4，后端全量1678（3既有跳过）、wheel PASS。服务定义、目标账户/Server2025、版本/子进程/句柄/DB会话证明仍缺，不能据本项允许备份/迁移或关闭 CR/Gate3。

## A06-P02-P02-P01 编码前检查：进程自报版本身份

当前 Phase：Phase 2 Platform Core。当前 WBS：PLT-MAINT-01-A06-P02-P02-P01。输入基线：CR-PLT-004/ADR-012、A06-P02-P01 OS 候选枚举、Windows 三个显式常驻入口、当前 backend `0.1.0.dev0` 版本与 wheel。前置候选枚举仅诊断内部 PASS；正式 SCM/部署账户不存在，本项不能出具停写证明。
涉及模块：Platform 私有进程身份标记与三个 Windows 入口生命周期，不改业务 Owner、数据库或公开 API。涉及实体：运行时短期 JSON 标记（角色、PID、登记时间、包版本、代码树 SHA-256、OS SID、可执行路径；无 Secret）。涉及 API：无。涉及权限：继承已受控 data_root 目录 ACL；本项不声称目标账户 ACL 已验。
验收标准：三个入口在配置验证后、运行窗口开始前登记（Worker 在组合成功后；API 的 Uvicorn 应用工厂在窗口内执行），正常静止退出删除；异常/崩溃留下可识别陈旧标记；不可写/目录重解析点/元数据不符失败关闭。合成双进程和真实 Windows 11 PID/SID/版本/摘要交叉验证，单元、全回归、wheel。
风险/回滚：自报标记可陈旧/伪造，代码树摘要不能证明服务身份或文件句柄收敛；正式安装目录 ACL、SCM 服务名与二进制签名/版本握手后续独立验收。无 Migration/API/依赖；回滚停用标记组合并保留已有诊断文件供人工核查，不盲删用户数据。

结果：A06-P02-P02-P01 Windows11 内部 PASS。API、Audit、Parser 三入口在运行窗口登记角色/PID/UTC/包版本/代码树 SHA-256/当前 SID/可执行路径/随机 nonce；正常退出仅删除本次内容和 inode 均匹配的标记，异常退出保留对账。不可用/重解析目录、版本不符和非法角色拒绝。原生双子进程验收实际 Python PID（虚拟环境启动器 PID 可能不同）、Token SID、版本、摘要与可执行路径，正常退出删除、模拟崩溃残留；后端全量1684（3既有跳过）、wheel PASS。测试首轮发现代码摘要根目录误指 modules，改为完整 plm_assistant 包后复验通过。此项仅为自报诊断；同账户可伪造/篡改、运行中代码可变，尚无正式 SCM/目标账户 ACL/Server2025/文件句柄/DB 会话证明，不能允许备份或迁移，CR-PLT-004/Gate3/发行继续 OPEN。

## A06-P02-P02-P02 编码前检查：Windows 自报标记与 OS 候选交叉核验

当前 Phase：Phase 2 Platform Core。当前 WBS：PLT-MAINT-01-A06-P02-P02-P02。输入基线：CR-PLT-004/ADR-012、A06-P02-P01 只读 OS 候选、A06-P02-P02-P01 进程自报标记。两前置均为 Windows11 内部 PASS；正式 SCM/目标账户/Server2025 不具备，仍不得出具备份或迁移许可。
涉及模块：Platform Windows 只读诊断；不改 API/Worker 业务或数据库。实体：进程观察值与不可信本地 JSON 标记，不新增持久业务实体。API：无。权限：调用者只读 OS 进程和其有权读取的受控 data_root；任何不可见、重解析、畸形或冲突均保持未知/失败关闭。
验收标准：受限读取标记目录，核对 schema/文件名/PID/角色/SID/可执行路径/包版本/当前代码摘要，与同次 OS 快照的 PID、SID、路径和已知入口命令行交叉；输出仅脱敏状态/计数，恒 `DIAGNOSTIC_ONLY` 和 `backup_or_migration_authorized=false`。测试涵盖匹配、陈旧、PID 复用/篡改、不可见、目录异常及 Windows11 活子进程；后端全量与 wheel。
风险/回滚：快照与标记不是原子且同账户可伪造，当前代码文件也可能变化；本项绝不证明 SCM 身份、句柄/DB 会话或静止。无 Migration/API/依赖，回滚移除只读交叉核验入口并保留标记供人工对账。

结果：A06-P02-P02-P02 Windows11 内部 PASS。新增独立只读 CLI 和有界严格标记读取器；OS CIM 快照补采 UTC 创建时间，核对 PID/SID/路径/已知入口命令行/版本/代码摘要，识别陈旧、PID 复用、冲突、不可读和不匹配。报告不输出路径或命令行，恒 `DIAGNOSTIC_ONLY`/`backup_or_migration_authorized=false`；合成正向匹配及负例、原生 Windows 子进程使用未知 `-c` 入口时真实拒绝匹配，正常退出标记移除。后端全量1690（3既有跳过）、wheel PASS。原生已知入口正向握手尚待正式服务配置；快照竞态、同账户伪造、SCM/目标账户 ACL/Server2025/句柄/DB 会话未验，CR-PLT-004/Gate3/发行继续 OPEN。

## A06-P02-P03 编码前检查：Windows SCM 服务身份与受控启停方案

当前 Phase：Phase 2 Platform Core。当前 WBS：PLT-MAINT-01-A06-P02-P03。输入基线：CR-PLT-004、ADR-012、三 Windows 常驻入口及 A06-P02-P02 标记/OS 诊断。前置仅为诊断内部 PASS，正式服务定义不存在；本项是架构/实施合同，不安装生产服务。
涉及模块：Platform/Release 的 Windows 服务宿主与生命周期，不改业务 Owner、数据库或公开 API。涉及实体：SCM 服务配置、服务状态/PID/账户与原运行标记；无新业务持久实体。涉及 API：无。涉及权限：正式服务账户/ACL 待目标环境供给；当前开发会话非管理员，不能宣称 SCM 安装验收。
验收标准：比较直接 CLI、外部包装器和原生宿主；固定服务名与 PID 归属、配置/就绪/协作停止/错误/回滚合同、Windows11/Server2025 分阶段验收及未知进程失败关闭；形成可追溯 ADR/CR 与下一编码任务。风险：Python 原生 SCM 调用、Uvicorn 就绪、OCR 子进程与服务账户凭据尚未实测；无 Migration/API/依赖，本项不出具备份/迁移许可。

结果：A06-P02-P03 方案与边界已记录于 ADR-013。官方 SCM 文档确认普通 CLI 不具备 dispatcher/handler/状态合同；选择不引入新组件的 Python 3.13 `ctypes` 原生独立服务宿主作为待验证实现路线。当前账户非管理员且本机无 PLM 服务，本项只完成设计，不把 P03-P01～P04 编码和实机验收写为 PASS。下一 P03-P01 实现可注入的最小状态机；CR-PLT-004/Gate3/发行仍 OPEN。

## A06-P02-P03-P01 编码前检查：最小 SCM dispatcher 与生命周期状态机

当前 Phase：Phase 2 Platform Core。当前 WBS：PLT-MAINT-01-A06-P02-P03-P01。输入基线：ADR-013/CR-PLT-004、Python3.13/Windows11、现有三角色入口。前置 ADR-013 已记录并同步；正式安装/目标账户不具备，本项不得注册服务或宣称 SCM 实机 PASS。
涉及模块：Platform 基础设施 Windows 原生服务接口；不接 API/Worker 业务。实体：内存服务状态/停止事件，不新增持久实体。API：无。权限：仅读取当前系统接口，不修改 SCM 服务数据库；以后安装器和账户 ACL 单列任务。
验收标准：固定三角色服务名、标准库 Win32 dispatcher/handler/状态结构；注册后报告 START_PENDING，只有 runner 显式就绪才 RUNNING；STOP 回调仅请求停止并快速返回，STOP_PENDING 可更新 checkpoint，runner 完成才 STOPPED；未就绪、意外退出与报告失败不能伪报正常。单元验证状态顺序/重复 STOP/异常，Windows11 非 SCM 调用预期拒绝、后端全量与 wheel。
风险/回滚：Python `ctypes` 回调和真实 SCM 交互仍须管理员隔离安装验证；本项测试桩与错误路径不足以证明服务可运行。无 Migration/API/依赖；回滚不装配该未公开宿主，保留原 CLI、标记与审计。

结果：A06-P02-P03-P01 Windows11 最小接口内部 PASS。标准库 `ctypes` 实现固定三角色名的原生 dispatcher/handler/ServiceStatus 骨架，状态机仅在 runner 显式就绪后报告 RUNNING，STOP 控制请求设置协作事件、STOP_PENDING 可递增 checkpoint，未就绪/意外返回/runner 或状态报告故障均不能报正常停止。单元5包含真实 Windows 非 SCM 子进程调用预期拒绝；后端1695（3既有跳过）、wheel PASS。未实现 API/Worker runner、SCM 安装/启动/停止，也未验证目标账户、非 daemon/OCR 子进程和资源退出；此结果不是正式服务或停写 PASS，下一 P03-P02 接入三角色并验证实际就绪/收敛。

## PAR-01-A05-P06-P01 编码前检查：Windows OCR 模型路径可诊断限制

当前 Phase：Phase 2 Platform Core。当前 WBS：PAR-01-A05-P06-P01。输入基线：CR-PAR-005 方案 A、现有 `OfflinePaddleOcr` 模型四文件指纹与 Windows Worker 启动链。前置同字节模型中文/ASCII 路径差异与底层异常已在本机复现；正式安装器/目标账户仍缺。
涉及模块：Parser OCR Adapter 的 Windows 启动前路径检查，不改 OCR 结果、业务权限、数据库或 API。验收标准：Windows 非 ASCII 模型目录在 Paddle 初始化前固定错误码拒绝、无网络下载或 Job 领取；ASCII 原链与真实 OCR 保持，通过后端全量与 wheel；非 Windows 平台不受此 Windows 专属限制。
风险/回滚：本项是显式限制，不是任意中文路径支持；正式发行须安装于受控 ASCII 目录并核权限/内容/Server2025，CR-PAR-005 未因此关闭。回滚移除路径检查将恢复不可诊断的 Paddle 初始化失败，不建议单独回滚；无 Migration/API/依赖。

结果：PAR-01-A05-P06-P01 Windows11 内部 PASS。两套模型 det/rec 的四个指纹文件逐一 SHA-256 相同；直接 PaddleOCR 对中文路径在 `create_predictor` 抛空 JSON parse error，ASCII 路径成功。Adapter 现在对 Windows 非 ASCII 绝对模型路径在模型指纹/Paddle 初始化前固定 `OCR_MODEL_PATH_UNSUPPORTED`；单元证实不调用预测器，ASCII 路径真实合成 PNG 与原生/扫描混合 PDF OCR PASS。后端全量1674（3既有跳过）、wheel PASS。此项仅使限制显式可诊断，正式受控 ASCII 安装目录 ACL/模型校验、Server2025 和全离线包未验，CR-PAR-005/Gate3/发行继续 OPEN。
