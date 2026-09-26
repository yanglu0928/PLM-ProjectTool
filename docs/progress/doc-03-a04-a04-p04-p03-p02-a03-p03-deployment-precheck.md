# CR-DOC-008/A03-P03：生产停写与 Windows Server 2025 演练前置核查

- 日期：2026-09-26；Phase 2 Platform Core；结果：`PRECONDITION_BLOCKED`，不得挂载或执行生产物理清理。
- 输入：Gate 2 冻结提交 `64cdf09`、ADR-007/008、CR-DOC-008，以及 A01/A02/A03 的 Windows 11 隔离验证记录。此项仅核查部署/账户证据，不改变 Schema、公开 API 或清理代码。
- 本机只读证据：官方 Windows 组合已经接入 `LocalUploadOperationGate`；当前 Windows 11 没有运行中的 PLM/Python 写进程，且 `C:\PLMTool`、`D:\PLMTool` 不存在。这仅说明当前本机状态，不能证明任何旧版生产进程已停写。
- Windows Server 2025：VMware 清单中存在 `D:\Virtual Machines\Windows Server 2025\Windows Server 2025.vmx`；本轮从关机状态正常启动，VMware Tools 报 `installed`，NAT 来宾地址可取得。来宾的 WinRM 5985 与 RDP 3389 TCP 检查均未连通；尚未建立目标服务账户、私有数据根、数据库、旧版进程清单或部署基线。检查后已通过 VMware Tools 正常关机并确认运行 VM 数为零，恢复原关机状态。虚拟机能启动不等于应用兼容或恢复演练 PASS。
- 缺失的生产前置：确认唯一受控数据根及账户 ACL；列出并停用所有旧版/无栅栏写入口与 Worker，并证明没有遗留活跃上传；隔离备份与恢复演练；在目标账户下验证跨进程同 ID 锁、数据库资格复核、逐路径清理及崩溃重试；确认部署拓扑仍为单机本地文件系统，网络共享/多实例必须重新评估。
- 风险与控制：旧版进程可能在清理后继续写文件；未知账户或数据根可能导致越权、错误路径或无法恢复。内部清理命令保持未挂载，`CLEANUP_PENDING` 记录保留。不得把本机无进程或 VM 启动当成全局停写证明。
- 下一步：获得可验证的目标部署/账户材料后在 Server 2025 逐条演练；期间继续不依赖该生产前置的 Phase 2 工作。Debian 13 按用户当前指令暂不验证。
