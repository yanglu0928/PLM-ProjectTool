# ADR-013：Windows SCM 原生服务宿主与进程身份

日期：2026-09-30；状态：`PARTIALLY_IMPLEMENTED / NOT_SCM_VALIDATED`；关联 `CR-PLT-004`、`ADR-012`、`PLT-MAINT-01-A06-P02-P03`。本 ADR 不追写 Gate 2 冻结提交 `64cdf09`。

## 背景

Windows 三个现有生产入口为前台 Python CLI。它们可以做受控准入和自报标记，但还没有向 Service Control Manager（SCM）注册、响应 `SERVICE_CONTROL_STOP` 或报告真实 `RUNNING/STOP_PENDING/STOPPED`。`sc.exe create` 只登记命令行，不会把普通 CLI 变成可管理的服务；将现有 `python -m ...serve_windows` 直接安装为服务不能满足停机证明。当前开发会话非管理员，仓库内也没有正式 PLM 服务；本 ADR 不是实机 SCM 验收。

## 方案比较与决定

| 方案 | 结果 | 原因 |
|---|---|---|
| 直接 `sc.exe create` 指向现有 CLI | 拒绝 | CLI 没有 SCM dispatcher/handler/状态回报，服务启动与受控停止合同不成立。 |
| 引入 WinSW/NSSM 等外部包装器 | 暂不选择 | 增加二进制供应链、许可清单和离线发行维护；包装器 PID 与 Worker PID 分离，仍需子进程退出证明。若原生方案 PoC 失败，再通过正式 CR 比较。 |
| Python 3.13 标准库 `ctypes` 实现独立 SCM 宿主 | 选择，待验证 | 不增加运行依赖；每个 API/Audit/Parser 角色使用单独 `SERVICE_WIN32_OWN_PROCESS`，宿主在同一 PID 内组合并运行现有业务循环，便于 SCM PID 与运行标记交叉核对。 |

## 运行合同

1. 三个固定服务名分别对应 API、Audit Worker、Parser Worker；服务宿主的命令行只包含绝对 Python 解释器、模块、角色及非敏感 bootstrap YAML 路径，不接收密码、API Key、License 私钥或数据库 URL。正式安装时账户由实施流程独立供给，不默认 LocalSystem，也不把开发者当前账户当成目标账户。
2. 宿主主线程在受控短时窗口内调用 `StartServiceCtrlDispatcherW`；`ServiceMain` 立即注册控制处理器。`RUNNING` 仅在配置、信任源、准入组合和实际服务就绪后报告。启动失败报告 `STOPPED` 与非零错误；不得把配置可解析当作 API 已监听或 Worker 已就绪。
3. STOP 回调只设置协作停止标志并尽快返回，绝不在回调内做数据库、OCR、文件 I/O 或等待。API 令 Uvicorn 完成真实停止/ASGI lifespan 清理；双 Worker 复用 `request_stop()`、已知工作排空与 `quiescent()` 之后释放数据库。`STOP_PENDING` 期间可按 SCM 要求更新 checkpoint/wait hint；仅进程与持有的非 daemon 工作线程、OCR 子进程及资源确认退出后报告 `STOPPED`。超时/无法静止不得伪报 `STOPPED`、强杀或自动备份。
4. 安装器只在明确的发行/目标环境任务中创建或修改精确服务名；先验证绝对本地安装路径、解释器/包版本/代码摘要、账户、ACL 和 SCM 配置。卸载前检查服务归属与状态；本 ADR 不授权对用户现有服务做清理。首次采用手动启动模式，自动启动和失败恢复策略另行验收。
5. 停写核验同时读取 SCM 状态、服务 PID/账户/二进制路径、OS 进程快照与本产品标记；任何旧版/未知入口、不可读进程、残留句柄或 DB 会话仍阻断备份/迁移。服务 `STOPPED` 只是一项证据，不取代实际进程、文件句柄和数据库会话收敛。

## 分阶段验收

- P03-P01：最小 SCM dispatcher/handler/状态状态机，注入式单元/故障测试；不能因仅测试桩而宣称服务可运行。
- P03-P02：同 PID 接入三角色的配置、准入、进程标记与协作停止；验证 API 实际监听就绪、Worker 排空、错误与资源释放。
- P03-P03：Windows11 隔离安装服务并执行 SCM 启动/停止/重启、PID/账户/命令行/标记交叉检查；长 I/O、失联与异常不得误报静止。当前会话非管理员，此验证需受控管理员环境，未取得前状态为待验而非 PASS。
- P03-P04：Windows Server 2025 目标账户与离线安装/升级/恢复演练。Debian 13 沿用户既有暂缓实机验证，但仍是正式发行目标。

## 迁移、回滚与来源

没有 DB Migration 或 `/api/v1` 变化。旧 CLI 保留为受控诊断/手工模式，服务宿主在实机验收前不取代它们；回滚可停用未投产的新宿主与精确服务定义，保留数据库、运行标记和审计。目标账户 Credential Manager/权限、OCR 子进程树、TLS 代理与网络监听仍须独立验收。任何服务安装/卸载不在本设计任务执行。

Microsoft 官方接口依据：[Service entry point](https://learn.microsoft.com/en-us/windows/win32/services/service-entry-point)、[ServiceMain](https://learn.microsoft.com/en-us/windows/win32/services/service-servicemain-function)、[Service state transitions](https://learn.microsoft.com/en-us/windows/win32/services/service-status-transitions)、[Control handler](https://learn.microsoft.com/en-us/windows/win32/services/service-control-handler-function)、[Service programs](https://learn.microsoft.com/en-us/windows/win32/services/service-programs)。这些文档规定了 dispatcher、状态回报及快速返回的 STOP 处理器；具体 Python 宿主可行性仍需本项目实测。

2026-09-30 进展：P03-P01 状态机骨架与 P03-P02-A01 API runner 已内部验证。API 用 Uvicorn 0.53.0 实际监听完成状态发 ready，合成 FastAPI Windows11 HTTP/lifespan/停止/标记退出 PASS。Audit/Parser runner、真实 SCM 注册/账户/目标信任源/长连接和 Server2025 仍未验，不能因 API 合成结果提升整个 ADR 状态为运行时 PASS。

2026-09-30 后续进展：P03-P02-A02/A03 已接 Audit 与 Parser runner，Windows11 合成 STOP/工作排空/heartbeat 静止/DB 释放及标记结果通过；Parser daemon heartbeat 静止风险按 CR-PLT-004 先记后修。P03-P03-A01 新增只读三角色 binary path 命令计划（`PLAN_ONLY`），未修改 SCM。当前非管理员会话仍无法完成 P03 真实安装/启停/账户/资源静止验收；本 ADR 保持 `PARTIALLY_IMPLEMENTED / NOT_SCM_VALIDATED`，不得以内部测试或命令计划替代实机证据。

2026-09-30 安装器进展：P03-P03-A02-P01 新增显式单角色手动安装入口，原生 CreateServiceW 从交互提示取得密码，不放入 `sc.exe` 命令行；模拟 SCM 与原生 API binding 内部验证通过，未调用真实 SCM 写入。Windows11 开发会话无管理员权限，本机仍无三款 PLM 服务；目标账户 ACL/Vault/License、服务启动/停止与资源静止仍未验，ADR 状态不提升。API 合同依据：[CreateServiceW](https://learn.microsoft.com/en-us/windows/win32/api/winsvc/nf-winsvc-createservicew)、[OpenSCManagerW](https://learn.microsoft.com/en-us/windows/win32/api/winsvc/nf-winsvc-openscmanagerw)。

2026-09-30 只读诊断进展：P03-P03-A02-P02-A01 使用固定服务名调用原生 SCM 查询，读取安装配置、当前状态及报告 PID；CLI 不输出配置路径/账户，且仅把 RUNNING 的非零 PID 作为观察值而非归属证明。本机三服务均未安装，真实已安装服务正向、目标账户与资源静止仍待；ADR 状态不提升。接口依据：[QueryServiceConfigW](https://learn.microsoft.com/en-us/windows/win32/api/winsvc/nf-winsvc-queryserviceconfigw)、[QueryServiceStatusEx](https://learn.microsoft.com/en-us/windows/win32/api/winsvc/nf-winsvc-queryservicestatusex)。

2026-09-30 后续验证：P03-P03-A02-P02-A01-R1 在不改动服务的条件下，将内部只读查询用于本机已安装的 Windows EventLog 服务；原生配置/状态成功路径通过，公开产品查询仍严格限三个固定角色。此结果仅验证 Win32 适配器正向读取，不替代 PLM 服务安装、目标账户、PID 归属或资源静止验收，ADR 状态继续 `PARTIALLY_IMPLEMENTED / NOT_SCM_VALIDATED`。

2026-09-30 配置对账：A02-P02-A02 将 P03-A01 期望启动命令与 SCM 保存配置的服务类型、启动方式、错误策略、binary path 和账户逐项精确比较；缺失/不匹配仅出固定码，绝不把配置相同当作当前运行进程或静止证明。当前 PLM 服务未安装，故只通过合成匹配/差异与原生缺失路径；正式目标账户的实机对账仍待，ADR 状态不提升。

2026-10-02 后续增量 CR-AI-003：Provider Test 不得复用 Audit/Parser 服务角色；选择第四独立 AI Provider Worker 固定角色，原三角色保持。A01 已在隔离 PG18 组装未发布的维护循环并验证本机合成任务链；尚未加入 SCM 名单/命令计划/安装器/盘点，也未验目标账户或真实外发。本 ADR 仍 `PARTIALLY_IMPLEMENTED / NOT_SCM_VALIDATED`，原三角色合同不追写；A02/A03 才更新运行/运维证据。
