# CR-AI-003：Provider Test 独立 Windows Worker 角色

日期：2026-10-02；状态：A01～A02 限定范围已验证／A03 未实施，未获生产 SCM 验收。来源：CR-AI-002、`AI-01-A05-P05-A03-P04-P02-A03`、ADR-007/012/013；原 Gate 2 冻结提交 `64cdf09` 保留。

## 冲突与证据

A02 前 `SERVICE_NAMES`、Windows 服务计划/安装/只读盘点/配置对账、运行进程标记仅承认 API、Audit Worker、Parser Worker。Provider Test 已具备专属 Job 领取、Secret 审计、固定网络探针、维护准入循环，但当时没有可被 SCM 独立停止和盘点的进程角色。若将探针塞入 Audit/Parser Worker，将混合当前账户 Vault 主钥与对外网络权限，且维护停写证据无法区分哪个 Worker 在执行外发；若只把第四个名称加进 `SERVICE_NAMES`，计划会生成尚不能运行的服务命令。

## 方案、差异与决定

1. 复用现有 Worker 角色：不选，跨职责/账户出站边界，不满足独立诊断和停写证明。
2. 新增三方服务包装器：不选，扩大供应链且与 ADR-013 的原生宿主方案不一致。
3. 选择 `AI_PROVIDER_WORKER` 第四个固定 `SERVICE_WIN32_OWN_PROCESS` 角色、独立服务名 `PLMProjectToolAIProviderWorker`；先完成现有可信源 Worker+维护循环装配，再把真实可运行宿主与固定角色、进程标记、服务计划/安装/盘点/对账同步接线。最终只有明确配置与目标账户材料可用才报告 RUNNING。原三角色命令与身份保持不变。

此为 ADR-013 三角色运行合同的可追溯后续增量，不回写原版本。无新基础设施、外部依赖、DB Schema 或 `/api/v1` Breaking Change。第四角色本身不授权真实厂商出站，外发仍须本轮明确范围/用途授权。

## 顺序、迁移、回滚

- P03-A01：从已验证 Windows 单次工厂组装维护准入循环，暂不注册服务或打开 Test 路由。
- P03-A02：在同一改动中接 SCM 宿主 runner、第四固定角色、进程标记及全部服务计划/安装/只读盘点/配置对账；不能只修改允许列表。仅实现/合成验收，不实际安装或启动服务。
- P03-A03：Windows 11 受控目标账户 SCM 安装/启动/停止、PID/账户/路径/标记与失联/长 I/O 静止核验；Server 2025 目标账户与离线恢复另行验收。条件缺失保持 `NOT_SCM_VALIDATED`。
- P04：生产提交/激活路由须在同源策略与 Worker 服务就绪证据后才可挂载；默认 404 不变。

无迁移脚本。若新服务未投产，撤第四角色/入口可回退；若已投产，先受控停新任务和服务，人工核对存量 Job/结果/Audit，保留历史并向前修复，不自动删除 SCM 定义或生产数据。升级手册需列第四角色停写/备份/恢复与版本兼容检查；旧服务不可被新名称替代。

## 验证与剩余风险

单元覆盖缺策略/License/Vault/维护准入失败关闭、四角色唯一性、错误入口、受控 STOP 排空和数据库释放；隔离 PG18 验证共享锁覆盖真实单次 Worker Job→Secret→本机 TLS→结果；合成 SCM 宿主仅作功能证据。真实目标账户 Vault/ACL/CA、SCM 安装/重启、Windows Server 2025 和 Debian、正式外发、Gate 3/UAT/可用发行包仍为开放项，不以合成通过替代。

2026-10-02 A01 进度：Windows 未发布工厂从既有受控单次 Worker 取得同一数据库的维护准入并生成固定格式的唯一 WorkerRef；缺准入关闭并释放所有权，构建不领取 Job。Win11 定向9项、新隔离 PG18 共享锁覆盖真实单次 Job/Secret/本机 TLS/结果及后端2025运行/3跳过、wheel通过。尚未新增 SCM 名称、计划或安装入口；A02/A03 保持开放。

2026-10-02 A02 进度：按 DEC-663 增加独立固定服务名、进程标记、SCM 宿主 STOP 排空、只读盘点和配置对账；合法受控探针策略不存在时计划仍仅列原三角色，AI 安装和对账拒绝。未修改原三角色命令。Windows11 定向模拟与后端全量2032项/3跳过、开发 wheel `daf5c7ceae5e3925d4986bf0ef0e9440732e6e2576aa8599975373c67fd57aee` 通过；只读本机盘点四服务均未安装。无 Schema/API/依赖变化、无需迁移。尚未进行真实 SCM 写入、目标账户/ACL/Vault/License/信任、服务重启/失联/长 I/O 静止或厂商外发；A03、正式路由、Gate 3 仍开放。回滚如未投产可撤第四角色/入口；已投产则须先停止受理并对账 Job/Audit，不自动删除服务或历史。

2026-10-02 A03 前置审查：当前 Windows11 会话为 Medium Integrity，Administrators SID 标记为 deny-only，不能据此执行受控 SCM 写入。仓库可见配置只有 `bootstrap.example.yaml`；没有已确认的独立目标账户受保护 Bootstrap/Vault/License/ACL/CA 证据。原生只读盘点四服务均未安装。故真实安装/启动/停止、目标账户 PID/标记及长 I/O 静止均标记 `PRECONDITION_BLOCKED / NOT_SCM_VALIDATED`，不尝试提升权限或以开发账户代替目标账户，也不触发厂商出站。材料和受控管理员会话具备后重新执行 A03；其间转向不依赖 A03 的工作项。
