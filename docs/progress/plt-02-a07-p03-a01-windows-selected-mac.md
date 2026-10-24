# PLT-02-A07-P03-A01：Windows 选定 MAC 本机来源

- 日期：2026-09-25；状态：Windows 11 本机来源 PASS；生产 License 装配与 Server 2025 NOT VERIFIED。
- Phase/WBS：Phase 2 Platform Core / PLT-02-A07-P03-A01。输入：Gate 2/ADR-006 MAC 规范化→SHA-256→Ed25519、CR-LIC-001、现有 `SelectedMachinePort` 与非敏感 Bootstrap。前置满足。
- 涉及 License 基础设施、Platform Bootstrap 和测试；无实体、Schema、Migration、公开 API 或权限变更。验收：配置显式选定一个 MAC，运行时每次与本机网卡列表核对；匹配返回规范化 MAC，缺失/虚构/异常失败关闭，不回显本机网卡信息。
- 实现：新增可选 `selected_mac` Bootstrap 字段，仅限非秘密的人工选择值；`WindowsSelectedMachine` 通过 Windows IP Helper `GetAdaptersAddresses` 读取本机所有接口的 6 字节物理地址，规范化后精确匹配。配置值单独不能证明机器身份，不自动选择第一块网卡。参考 Microsoft [GetAdaptersAddresses 文档](https://learn.microsoft.com/en-us/windows/win32/api/iphlpapi/nf-iphlpapi-getadaptersaddresses)。
- 验证：Windows 11/Python 3.13 后端 339/339 PASS；真实本机网卡枚举、其中一个地址的显式选择、虚构地址拒绝、合成枚举故障、配置缺失/非法长度均通过；wheel PASS。测试不打印或提交本机 MAC。无数据库或外部数据操作。
- 风险/下一项：本地管理员控制的虚拟网卡/MAC 仍可伪造，沿用冻结的机器绑定安全水平，不宣称硬件不可克隆。Server 2025 未验证；Debian 13 按用户要求暂不验证。生产公钥、可信时间密钥与初态、License Guard 的组合根仍待完成，公开受许可业务保持关闭。
