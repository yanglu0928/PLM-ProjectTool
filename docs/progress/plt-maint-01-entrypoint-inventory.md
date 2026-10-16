# PLT-MAINT-01-A06-P01：生产写入口与进程静止清单

日期：2026-09-30；范围：当前仓库 `apps/backend/src/plm_assistant` Composition Root 与 Alembic env 的静态盘点。证据定位在所列文件；这不是目标机器进程枚举，也不是备份/迁移许可。

| 入口/进程 | 潜在写入 | 当前维护准入 | 运行与静止边界 |
|---|---|---|---|
| `entrypoints/serve_windows.py` → `production_login.py` 三种 Windows API 模式 | HTTP 非安全方法及四个有错误审计副作用的 GET content；数据库/本地文件 | 三种显式组合都注入 ASGI admission，覆盖正文、响应和后台任务；其余 GET 以只读为前提 | Uvicorn 单 worker。需要实际服务/子进程 PID、版本、配置及退出证据；仅连接释放不能证明文件 I/O 已停 |
| `entrypoints/worker_windows.py` Audit Worker | Job 领取/心跳、Audit Export 文件与结果发布 | 当前账户 Vault URL 的独立 PG18 admission，单步扫描/执行持锁，idle 不持锁 | 协作信号与 `quiescent()` 后释放；需确认真实 OS 进程与非 daemon 心跳线程全部退出 |
| `entrypoints/parser_worker_windows.py` Parser Worker | 取消到期恢复、Job 领取/心跳、OCR 与解析结果文件发布 | 同上，取消扫描与 Parser Step 同一锁；idle 不持锁 | 协作信号/静止后释放；OCR 子进程/外部依赖及断线后文件 I/O 仍需进程级证据 |
| `entrypoints/maintenance_windows.py` 本地维护命令 | 维护状态与 USER Audit；短期 Auth Session | 独占同一 advisory key，事务内重验当前 DeploymentAdmin 与 CSRF，状态/Audit 同事务 | 这是有意的转换入口，不是业务共享准入；命令成功不等于全部生产进程已退出，不直接授权备份/迁移 |
| `entrypoints/bootstrap_admin.py` 首次管理员初始化 | 初始 User 与 Audit | 未接共享门禁；`InitialAdminService.claim_empty()` 限定空用户库 | 只允许首次部署、启动生产进程前执行；不能作为现网恢复/维护期间写入工具。后续需安装流程限制与验证 |
| `migrations/env.py` Alembic online | 任意受版本脚本定义的 DDL/DML | 未接共享门禁；维护状态由运维流程约束 | 必须先人工备份、排他状态与 API/双 Worker 的 OS 退出证明，之后单独执行并复核；直接 Alembic 命令有越过编排的能力，正式发行入口仍缺 |
| `entrypoints/provision_database_credential.py`、`secret_key_recovery.py` | 当前 OS 账户 Credential Manager/备份文件，不直接写业务 DB | 不适用 PG 准入 | 配置/密钥轮换必须在受控维护且所有使用旧值的进程退出后执行；恢复/备份文件权限与目标账户待验 |
| `entrypoints/api.py` 裸 `create_app` 与 `parser_worker.py`/`audit_worker.py` 纯组合 | 取决于注入的 Router/Step | 默认为不启用，专供测试/内部组合 | 不得作为生产启动入口；发行须只暴露显式 Windows 组合，Debian 正式组合尚不存在 |
| `verify_release_key.py` 等只读 codec/探针 | 不写业务 DB/文件；可能读取 OS 信任源 | 不需要业务共享准入 | 不能据此证明生产进程静止 |

## 差异与下一验收

源码可见的正式常驻写进程为 API、Audit Worker、Parser Worker，Windows11 内部组合均已注入共享准入；首次初始化与 Alembic 是独立的特权写入口，不应被误判为“所有写操作都自动受栅栏保护”。`secret_key_recovery` 等 OS 凭据变更不受数据库锁约束，需要在进程停止之后执行。当前仓库未发现正式 Windows 服务定义、可核验的安装/卸载与版本/PID 清单、Debian systemd 组合或统一受控 Migration 执行器；PoC 脚本不等于发行服务定义。任何历史版本或用户自行启动的 Python 进程也可能绕过新准入。

下一 WBS 应先制定受控进程清单与版本握手，再在 Windows11/Server2025 对服务停止、子进程/线程退出、文件句柄收敛及排他状态做真实演练；对旧版/未知 PID/失联窗口失败关闭。迁移必须只有在上述证据满足后进入，且回滚为停服、人工备份恢复匹配代码/DB，不能盲降有维护历史的 Schema。Server2025 远程通道及正式部署账户尚未验证，Debian13 当前按用户要求暂不实机验证，但仍是正式兼容目标。A06-P01 是静态清单，不关闭 CR-PLT-004、Gate3 或发行门槛。

2026-09-30/A06-P02-P01：新增只读 Windows 候选进程诊断 `python -m plm_assistant.entrypoints.process_inventory_windows <deployment-account-SID> <absolute-runtime-root>`。仅在当前账户有足够读取权限时收集 PID/拥有者 SID/路径/命令行，报告只包含候选 PID/匹配原因及不可读计数，恒为 `DIAGNOSTIC_ONLY` 且明确 `backup_or_migration_authorized=false`。Windows11 开发账户约380进程本机快照 PASS，但因不是独立部署账户、无正式 SCM 服务/版本/句柄/DB会话证明，不得用本工具零候选输出替代停写验收。

2026-09-30/A06-P02-P02-P02：新增只读交叉核验入口 `python -m plm_assistant.entrypoints.process_identity_inventory_windows <deployment-account-SID> <absolute-runtime-root> <absolute-data-root>`。它读取自报标记并与一次 OS 候选快照比对 PID、创建时间、SID、可执行路径、入口命令行、包版本及代码摘要；只输出 PID/角色/状态和未匹配候选，不输出原命令行或路径。未知/冲突/无标记仍是诊断；`OBSERVED_MATCH` 也不证明快照后进程仍运行或已静止，不授权备份/迁移。后续必须核验正式 SCM 身份、账户 ACL、文件句柄/DB 会话和 Server2025。

2026-09-30/A06-P02-P03-P02-A01：新增未安装的 `python -m plm_assistant.entrypoints.service_windows API <absolute-bootstrap.yaml>`。仅 API 角色已接 SCM 状态机与 full platform-write runner；Windows11 合成 ASGI 真实 loopback HTTP/停止验证，Audit/Parser 角色仍静态拒绝。此入口不能替代原三个正式 CLI 的生产清单，直到隔离 SCM 安装、目标账户/信任源、长流与进程静止验收完成；只读候选/标记识别新增 API 服务命令行，报告仍无备份许可。

2026-09-30/A06-P02-P03-P02-A02/A03 后续状态：API/Audit/Parser 三角色均已接入 `service_windows`，Audit/Parser 的 Windows11 合成 STOP、工作/heartbeat 静止、DB 释放与标记对账内部通过；上段“仅 API 已接”的表述是其当时历史检查点，不代表当前状态。P03-P03-A01 只读命令计划不安装 SCM，三角色仍未在目标账户或 Server2025 实机运行。旧 CLI 与服务入口均须列入正式进程/版本/句柄/DB 会话静止检查；不能据内部测试授权备份或迁移。

2026-09-30/A06-P02-P03-P03-A02-P01 新增显式单角色原生 SCM 安装器，仅用于后续受控管理员验收，不是运行进程或停写证据。当前非管理员会话未运行安装，本机三固定服务名仍不存在；入口清单的实际生产 PID/版本/账户及句柄/DB 会话列仍待目标环境填写，旧版 CLI/未知进程不能因此忽略。
