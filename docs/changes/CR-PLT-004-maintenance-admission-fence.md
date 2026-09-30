# CR-PLT-004：跨 API/Worker 的可靠维护停写栅栏

状态：A02 Schema 内部 PASS，整体 OPEN；日期：2026-09-30；Phase 2 / PLT-MAINT-01。原 Gate2 冻结提交 `64cdf09` 保留；本 CR 作 Schema V1 增量，不追写原冻结文件。A03 前置复核发现会话锁连接意外断开时的静止证明缺口，按下文修订验收，不视为已关闭。

## 来源、现状与必须解决的冲突

ADR-007/008 和冻结安全边界要求升级顺序为人工备份→维护模式拒绝新任务→收敛 Worker→Migration。`DOC-03-A03-P04-P04` 已因缺生产停写证明登记 `BLOCKED_PRECONDITION`。2026-09-30 核对：Windows 显式生产应用有登录/管理/上传/Job 写入口；上传独立本地锁仅按 UploadId 防同一文件并发，不是全局维护栅栏。Audit Worker 与新 Parser Worker 都有协作式停止，但进程停止不阻止仍运行的 API 接受新写入，也不能证明所有跨事务文件 I/O 已结束。不能用“停止进程”或静态配置当作维护模式 PASS。

## 方案比较

- A：仅停 API/Worker 进程。拒绝；多个进程的停止顺序有竞争，重启时无持久状态，文件与数据库窗口不能证明已静止。
- B：只增加 DB 布尔状态，各请求/Worker 在起点读取。拒绝；检查后、维护写入前仍可跨事务继续发布，存在 TOCTOU。
- C：PostgreSQL 固定键的会话级共享/排他 advisory lock + 持久维护状态行。选择。生产 API 所有非只读请求及各 Worker 单轮在外部 I/O/多短事务完整窗口持共享 admission；维护命令独占排他锁、等待已准入窗口收敛后写持久状态。新 admission 持共享锁读状态，维护中失败关闭；命令崩溃后持久状态仍阻止写入。无需新基础设施或长数据库事务。

## 实施边界与顺序

1. 增量 Migration `0051` 与 ORM：单行 `RUNNING`/`MAINTENANCE`、版本和变更时间；空库/有数据升级、down 安全拒绝、原 `0050` 保留。单行不是单独充分的并发证明。
2. Platform 内部 admission Port：独立受限 PG 连接上的会话级共享锁、状态读取及原连接生命周期；不能只用事务锁或释放连接后继续文件 I/O。维护操作以同一键排他锁等待收敛、同事务更状态与 Audit，失败关闭。固定锁键和状态读写仅本产品实例使用；多实例同库是否支持需验证，不据此扩展为多节点架构。
3. 显式生产 API 模式全部覆盖非只读请求，从 ASGI 请求进入到响应/后台任务结束保持 admission，包括上传 content/commit/abort、登录/Session 写与管理命令。健康检查与 GET 不当作数据写，但内部 GET 若存在副作用须单独审计。普通开发 `create_app` 默认模式不冒充生产维护门禁。
4. Audit/Parser Worker 每个领取/恢复/发布单轮持 admission，不在空闲轮询期间持锁；信号只请求停止。其他独立写入工具/清理器逐一登记并接门禁，未覆盖前不执行维护切换或给 DOC-03 清理生产授权。
5. 维护命令可重复、超时、权限及历史审计、关闭/恢复；在跨进程活跃上传和 Worker、旧版进程、崩溃后重启、数据库断开、锁竞争、停写后新请求/Job 等场景做 Windows11/Server2025/目标环境验证。

## 安全、迁移与回滚

增加 DB Schema 与运维状态，不变 `/api/v1` 业务合同、角色、License 或技术栈；任何写入窗口无法取得共享锁/读状态时拒绝，绝不默认为 RUNNING。运维命令仅允许当前受控部署账户/受控 SystemActor 与可审计操作，不通过公开普通用户接口开放。上线前人工备份、先部署全部参与进程的门禁再允许维护操作；混跑旧版进程时禁止宣布静止。回滚为停写、人工备份恢复匹配版本的 DB/代码；带维护历史的 Schema 不盲目降级，保留原版本和审计。正式入口未全覆盖时 CR 保持 OPEN，Gate3/Release 不通过。

## 验收证据门槛

须有真实 PostgreSQL18 多进程并发证明：排他维护必须等待已准入的上传/Worker I/O 完成，维护状态提交后新写/领取为零；进程/连接崩溃锁自动释放但持久 MAINTENANCE 不丢；状态/锁/DB 来源错误失败关闭。再验证 Migration 空/有数据 up/down、ORM parity、生产路由矩阵、Worker 双 Owner、超时/恢复、全回归与版本说明。单元桩、进程仅停止或一条业务链成功都不足以关闭本 CR。

2026-09-30 A02 进展：Migration `0051` 与 ORM 已在隔离 PG18 空/有数据升级、无历史降级再升级、历史降级拒绝及触发器约束通过；后端1657（3既有跳过）、wheel包含通过。仅持久状态，尚无共享/排他锁或生产入口全覆盖；维护操作仍不可启用。

## A03 前置风险修订：连接丢失不等于 I/O 静止

会话级共享锁在 PostgreSQL 连接断开时自动释放，但 API/Worker 进程可能仍处于文件写入或 OCR 窗口；排他锁取得不证明这些进程已退出。因此方案 C 的锁+状态仅作为“健康连接下的并发准入协调”，不得单独出具备份/迁移静止证明。维护状态切换后还必须停止所有已登记的生产 API/Worker/清理进程并取得 OS 服务管理器/进程退出及文件句柄收敛证据；无法枚举或旧版进程仍在时拒绝进入备份/迁移步骤。新的生产写入在状态 MAINTENANCE 或 DB 失联时失败关闭；已在运行的操作须在持久化/发布前重核连接与状态，失联后拒绝提交，但外部 I/O 是否已结束仍由进程退出证明。此修订增加运行手册和跨平台进程清单验收，不增加新技术组件；原“仅靠锁保证静止”的解释撤销。回滚/升级流程保留人工备份与受控停服务，不自动强杀生产进程。

2026-09-30 A03-P01 进展：只读共享 admission Port 在隔离 PG18 双连接证明共享/排他锁竞争、无长事务、状态拒绝和显式解锁；杀死持锁 backend 后调用者退出报错，但排他锁已可被其他连接取得，实证上述静止风险。后端1659（3既有跳过）、wheel PASS。此 Port 未接生产入口/Worker，维护操作仍不可启用。

2026-09-30 A03-P02 进展：内部排他状态转换 Port 在隔离 PG18 双连接证明有限等待、状态与 AuditService USER 成功事件同事务、旧版本拒绝和 Audit 故障回滚；后端1661（3既有跳过）、wheel PASS。调用者提供的操作员 UUID 只作为内部输入，生产入口的认证/授权及 OS 退出证明仍未完成，故 Port 不得单独暴露或作为备份/迁移许可；整体 CR 继续 OPEN。

2026-09-30 A03-P03-P01 后续修订：移除 A03-P02 原调用方 UUID 输入，在排他锁与状态/Audit 同一事务复用 Auth 当前 Session+CSRF+部署管理员核验。隔离 PG18 管理员成功、错误凭据/非管理员/停用/撤销拒绝且零状态/Audit 变化，后端1661（3跳过）、wheel PASS。原提交保持历史可追溯；受控 OS 部署入口及全进程静止证明未完成，仍禁止生产切换/备份。

2026-09-30 A03-P03-P02：Windows 本机交互工具复用当前 OS 账户 DB Vault 来源和现有 scrypt/限流登录，短期 Session 经转换事务现时重验并撤销；隔离 PG18 管理员 enter/exit、错误口令/旧版本及审计证明、后端1663（3跳过）、wheel PASS。目标部署账户 Credential Manager 独占和 Server2025/Debian 未验，未接所有生产入口；工具成功输出也明确不授予备份/迁移许可。架构追溯 `ADR-012`，整体 CR 继续 OPEN。

2026-09-30 A04-P01：可选纯 ASGI 共享 admission 中间件在隔离 PG18 真实并发 HTTP 窗口和合成响应流/后台任务验证，MAINTENANCE 下写请求先于业务拒绝、GET/健康保持；后端1667（3跳过）、wheel PASS。正式 Windows 生产组合尚未注入；同步准入性能、GET 副作用与连接丢失后外部 I/O 仍待，整体 CR OPEN。

## A04-P02 前置差异：两个 GET 下载族具有错误路径 Audit 写入

2026-09-30 路由审计发现 `Document` 版本正文 GET 的 `_record_integrity_failure` 与 Audit Export 正文 GET 的 `record_content_failure` 可在完整性/内容故障时写 Audit。A04-P01 原“全部 GET 只读”假设对此不成立；若这些 GET 绕过 admission，维护状态下仍可能新增审计事件。选择在 ASGI 外层将上述四个现有 GET content 路由一并视作有写副作用的窗口，其他经审计的 GET/健康仍可读取。基线差异仅为内部准入策略，不改冻结 GET 业务合同/Schema；性能影响限于文件流下载并须实测。回滚不装配生产中间件；验证需覆盖四个路径的锁、MAINTENANCE 拒绝、非 content GET 放行，以及真实服务组合。未完成前不能宣称 A04 全覆盖。

2026-09-30 A04-P02：四个 GET content 路由已准入，Windows 三种显式生产组合都注入独立有界 PG18 Engine 并在 lifespan 清理；隔离 PG18 合成信任源下 RUNNING 真实管理员登录200、MAINTENANCE 登录/上传/四 GET content 503，而健康/Session GET 仍可用。后端1668（3跳过）、wheel PASS；旧无数据库路由契约测试显式注入准入替身，真实 PG 验证独立保留。目标账户/Server2025/Debian、20并发 P95、失联后的外部 I/O 与双 Worker/OS 静止仍未验证，CR OPEN。

2026-09-30 A05-P01：Audit Loop 可选单步 admission 在隔离 PG18 合成 Step 证明 step 持锁/idle 不持锁、排他竞争与 MAINTENANCE 拒新 claim，后端1669（3跳过）、wheel PASS。尚未 Windows Audit Worker 组合和真实导出 I/O 验收，不可宣称双 Worker 已覆盖或取得静止。

2026-09-30 A05-P02：Windows Audit Worker 从当前账户 Vault URL 构造专用单连接准入 Engine，向 Loop 注入并随 Worker 释放；隔离 PG18 临时 Vault/合成 License 的真实导出 Step 持共享锁、排他竞争拒绝，MAINTENANCE 不领取且业务快照不变。后端1671（3跳过）、wheel PASS。正式公钥/部署账户 ACL、长 I/O 失联、Server2025、Parser Worker 与 OS 退出未验证，CR 继续 OPEN。

2026-09-30 A05-P03：Parser Loop 可选单轮 admission 已把取消到期扫描及 OCR Step 纳入同一共享锁窗口，idle wait 不持锁；隔离 PG18 排他竞争/MAINTENANCE 在扫描前拒绝、后端1673（3跳过）与 wheel PASS。尚未 Windows Parser 进程接线、长 OCR I/O/连接失联/OS 静止验证，CR OPEN。

2026-09-30 A05-P04：Windows Parser 从当前账户 Vault URL 装配准入 Engine 并传 Loop；隔离 PG18 合成信任、独立 Windows 进程真实 PP-OCRv5/扫描 PDF 下，MAINTENANCE 保持 Job PENDING，恢复后成功 OCR，父进程观察到共享锁。后端1673（3跳过）、wheel PASS。中文路径模型加载失败另记 CR-PAR-005；正式目标账户/Server2025、连接意外释放及 OS 静止/性能仍未验，CR OPEN。

2026-09-30 A06-P01：生产入口静态矩阵记于 `docs/progress/plt-maint-01-entrypoint-inventory.md`。正式 Windows API 三模式与双 Worker 已装共享门禁；首次 Admin 初始化与 Alembic 仍是独立特权写入口，OS Vault/Secret 变更不受 PG 锁管。缺正式服务定义、版本/PID 进程清单、受控 Migration 执行器与旧版进程拒绝证据，不能把 A05 双 Worker PASS 当作停写证明，CR OPEN。

2026-09-30 A06-P02-P01：Windows 只读进程候选诊断按部署 SID、运行根与产品入口分类并脱敏输出，约380进程本机采样、后端1678（3跳过）、wheel PASS。曾因逐进程 CIM Owner 超时失败关闭，改用一次 CIM+只读 Token SID。该诊断恒不授予备份/迁移，缺目标账户/SCM/版本/句柄/DB会话证明，CR OPEN。

2026-09-30 A06-P02-P02-P01：Windows 三常驻入口增加自报进程身份标记，API 配置验证后、双 Worker 组合成功后登记；异常保留、正常仅清理自有标记。Windows11 原生双子进程交叉核对实际 Python PID/Token SID/包版本/完整代码摘要，后端1684（3跳过）、wheel PASS。首轮代码摘要根目录错误已修正并复验。标记可陈旧或被同账户伪造，仅作诊断，不能推断 OS 静止或允许备份/迁移；下一项只读交叉核验，SCM/目标账户 ACL/Server2025/句柄/DB 会话仍待，CR OPEN。

2026-09-30 A06-P02-P02-P02：只读交叉核验在同一 Windows OS 快照中比对标记 PID/进程创建时间/SID/路径/已知入口与当前包版本/摘要；陈旧、冲突、不可见或不匹配均拒绝确认。合成正向/负例、Windows11 原生未知入口负例、后端1690（3跳过）及 wheel PASS。此项不调整共享准入或发行流程；即使匹配也不能当作停写证明，SCM/ACL/句柄/DB 会话验收仍独立，CR 保持 OPEN。

2026-09-30 A06-P02-P03：正式 SCM 服务身份前置发现现有三个 Windows CLI 无 dispatcher/handler/状态回报，不能只用 `sc.exe create` 包装成服务。ADR-013 比较直接 CLI、外部包装器及无新增依赖的 Python3.13 原生宿主，选最后者进入分阶段可行性验证；每角色单独 SCM 进程，同 PID 对账与协作停止，不能在就绪前报告 RUNNING 或资源未静止时报告 STOPPED。原 CLI 保留，服务账户/安装器/Windows11 与 Server2025 SCM 实测、OCR 子进程/句柄/DB 会话待验；当前非管理员环境只完成方案，不安装服务，CR 保持 OPEN。

2026-09-30 A06-P02-P03-P01：原生 SCM dispatcher/handler/status 的未公开基础设施骨架和显式就绪状态机已通过单元5、Windows11 非 SCM 子进程拒绝、后端1695（3跳过）及 wheel。此时尚无三角色 runner/正式服务注册与进程静止验收，绝不将骨架或 `STOPPED` 单独作为备份/迁移许可；当前非管理员环境无法实机安装，CR 继续 OPEN。

2026-09-30 A06-P02-P03-P02-A01：API SCM runner 与 full platform-write 组合接线，合成 FastAPI 在 Windows11 真实 loopback socket/lifespan 就绪后才报告 RUNNING，STOP 后完成 Uvicorn shutdown 并移除自有标记；错误角色、非 loopback 和工厂异常拒绝。后端1699（3跳过）、wheel PASS。原生 SCM 实装/正式账户/License/长流和双 Worker 未验，仅内部链路，不能授予备份/迁移或关闭 CR。

2026-09-30 A06-P02-P03-P02-A02 前置差异：SCM 骨架只首次报告 `STOP_PENDING`/30 秒 wait hint，Audit 导出与 heartbeat 可能更久；不能靠一次状态更新推断正常停止。选择在停止等待期间周期性更新 checkpoint，Audit runner 仅在原 Loop 返回 `STOPPED`、heartbeat `quiescent` 且 DB 已释放后完成；未证实静止不清理标记、不授权备份。实施/验证结果后补，CR 保持 OPEN。

2026-09-30 A06-P02-P03-P02-A02 结果：Windows Audit SCM runner 已接现有专用 Worker 组合；STOP 唤醒轮询/已知工作 drain、心跳 `quiescent` 与 DB dispose 后才正常退出，长待停状态每10秒续报 checkpoint。Windows11 合成活跃工作、心跳延迟/失败启动和标记对账定向20、后端1704（3跳过）、wheel PASS。未实装 SCM/正式目标账户，未验证真实长导出/失联或 Server2025；Parser runner 及 OS/句柄/DB 会话静止证据仍缺，不能触发生产备份/迁移，CR 继续 OPEN。

2026-09-30 A06-P02-P03-P02-A03 前置差异：Parser Step 续租 heartbeat 当前为 daemon 且 `quiescent()` 仅检查 Step 锁；`close()` 超时后 Step 可释放锁，单凭 Loop 静止可能误报。修订为非 daemon 续租线程并记录当前线程，Step 静止检查拒绝活线程；服务入口仅在 Loop/线程静止、DB 已释放后结束。兼容性：不改 API/Schema/Job 语义，异常时进程保持可见而非后台线程被强退；可能延长服务停止时间，SCM 待停续报。回滚保留原 CLI/不启用新服务入口，不能回退安全检查后仍宣称静止。验证计划：活跃/延迟心跳、异常路径、服务状态与全量回归；正式 OCR 子进程/目标账户/Server2025 后验，CR OPEN。

2026-09-30 A06-P02-P03-P02-A03 结果：Parser 续租 heartbeat 改为非 daemon，并由 Step `quiescent()` 额外拒绝存活线程；Windows SCM Parser runner 复用现有可信源/离线模型组合，协作 STOP 后等待 Loop、heartbeat 与 DB 静止才返回。Windows11 合成活跃解析、延迟 heartbeat、启动失败/标记及角色对账定向32、后端1708（3跳过）、wheel PASS。首次全量旧测试将 Parser 误视为未开放角色，按新接线修正预期后全量通过。未实装 SCM、未实测目标账户/真实长 OCR/子进程及 Server2025；不触发生产备份/迁移，CR 保持 OPEN。
