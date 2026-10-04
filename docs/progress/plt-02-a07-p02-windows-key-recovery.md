# PLT-02-A07-P02：Windows 主密钥供给与独立加密恢复

- 日期：2026-09-25；状态：Windows 11 合成丢失/恢复 PASS；异账户/Windows Server 2025/正式部署 NOT VERIFIED。
- Phase/WBS：Phase 2 Platform Core / PLT-02-A07-P02。输入：冻结密文/主材料分离、CR-PLT-003、P01 Windows 只读来源。前置满足本项。
- 涉及 Platform 基础设施和本机交互入口；无实体、Schema、Migration、公开 API 或权限变更。验收：首次供给生成备份后写入且不主动覆盖 Vault；已有键可导出新备份；备份凭独立口令恢复到空目标；错误口令、篡改、目标已存在、非法长度与覆盖备份均失败关闭；恢复后旧密文可解。
- 方案：32 字节随机主密钥仅存当前账户 Windows Credential Manager Generic Credential。独立文件保存 `PLM-SECRET-KEY-BACKUP-V1` 加密信封：随机 16 字节 salt、scrypt N=65536/r=8/p=1、随机 12 字节 nonce、AES-256-GCM、绑定 `key_ref` 的 AAD。运维人员必须将备份与至少 16 字符的恢复口令分别离线保管。文件创建使用独占模式，不覆盖已有备份；恢复只允许目标不存在。此文件不能放入 Git、普通配置或应用数据目录。
- 本机入口（由目标运行账户在交互终端执行，路径必须为绝对路径）：`python -m plm_assistant.entrypoints.secret_key_recovery provision <key-ref> <backup-path>`；已有键额外备份用 `export`；目标 Vault 丢失后用 `restore <backup-path>`。口令与确认仅隐藏输入，不接受命令行或环境变量口令。`key_ref` 仅允许英数字开头及后续英数字、点、下划线、连字符，最长 80 字符。
- Windows 11/Python 3.13 验证：后端 335/335 PASS；UUID 命名合成 Vault 凭据经供给、删除、恢复后原密钥一致，恢复前创建的 AES-GCM Secret 密文可解；错误口令、篡改及重复恢复失败；临时 Vault 条目和临时文件已清理。wheel 构建 PASS。没有处理真实主密钥或客户资料。
- 限制：同一测试账户模拟丢失后的恢复，不等于异账户或异机演练；运维人员若丢失备份或口令，历史密文无法恢复。Windows Vault 的读后写无跨外部工具的原子 compare-and-create；需要目标账户专用、受控运维窗口，不得并行操作同一 `key_ref`。Server 2025 目标账户、HTTPS 代理与发行验证仍待；Debian 13 按用户要求暂不验证。Secret 管理 API 仍未公开，Gate 3/Release 未通过。
