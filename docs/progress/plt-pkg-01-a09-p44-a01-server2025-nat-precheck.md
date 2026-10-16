# Windows Server 2025 虚拟机 NAT 连通前置核查

日期：2026-10-01；任务：PLT-PKG-01-A09-P44-A01；结论：`HOST_NAT_ADDRESS_MISMATCH / SERVER_INSTALL_PRECONDITION_BLOCKED`。本核查为发行前的只读环境诊断，不是 Windows Server 2025 安装或兼容性验收。

固定目标 VMX 在 VMware Workstation Pro 中存在，配置 NAT、16 GB 内存和 16 vCPU。检查前 `vmrun list` 为 0 台运行 VM；指定 VM 启动成功，VMware Tools 状态 `running`，返回来宾 NAT 地址 `192.168.27.129`。宿主对该地址 TCP 3389/RDP、5985/WinRM、5986/WinRM TLS、445/SMB 的短时连接均失败。测试后执行正常关机，运行 VM 数恢复为 0；未在来宾安装或更改服务、防火墙、账户和数据。

追加宿主检查发现 VMnet8 网卡虽为 Up，实际 IPv4 却是 `169.254.190.187/16`，而 VMware DHCP/NAT 配置要求宿主 `192.168.27.1/24`、网关 `.2`；当前 PowerShell 令牌没有管理员权限。因路由前置不匹配，端口失败不能可靠归因于来宾服务或防火墙。恢复方案、影响与回滚已登记在 [CR-ENV-001](../changes/CR-ENV-001-vmnet8-host-address-recovery.md)，尚未实施。

本项只验证 VM 可启动/正常关闭、Tools 可报告地址及宿主 NAT 地址偏差。没有证据证明目标服务账户、ACL、数据库、HTTPS、正式 License、离线安装、重启、OCR 或业务链在 Server 2025 可用。无程序、发行包、API、Schema、Migration 或生产环境变更；版本仍 `0.1.0.dev0`，`release_eligible=false`。待有宿主管理员权限及影响范围确认后按 CR 恢复网络并重验；期间转入不依赖该虚拟机的发行证据任务。
