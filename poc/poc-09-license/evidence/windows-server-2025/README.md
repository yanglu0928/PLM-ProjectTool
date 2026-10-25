# POC-09 Windows Server 2025 证据

- Windows Server 2025 Datacenter 10.0.26100 x86-64，Python 3.13.15，cryptography 50.0.1。
- 使用 POC-01 嵌入式 Python 与 wheelhouse 完成全离线依赖安装，离线包 7 个文件逐项 SHA-256 复验 PASS。
- 实机枚举 1 个 MAC 候选，只保存候选数量；License Request 不包含原始 MAC。
- 26/26 单元测试、10/10 验收场景、8/8 非法授权拒绝 PASS。
- 私钥与原始 MAC 落盘数均为 0；验证后已删除来宾机 `C:\POC-09` 临时目录并保留虚拟机原运行状态。
