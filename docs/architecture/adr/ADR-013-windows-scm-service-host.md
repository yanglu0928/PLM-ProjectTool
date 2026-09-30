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
