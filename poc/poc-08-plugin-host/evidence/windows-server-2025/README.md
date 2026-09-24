# POC-08 Windows Server 2025 证据

- Windows Server 2025 Datacenter 10.0.26100 x86-64，Python 3.13.15。
- 使用 POC-01 已验证的嵌入式 Python 与 wheelhouse 完成全离线依赖安装。
- 离线包 22 个文件逐个 SHA-256 复验 PASS。
- 13/13 单元与集成测试、10/10 验收场景和 20/20 并发调用 PASS。
- crash 与 timeout 后 FastAPI 仍健康；敏感环境变量可见数为 0。
- 验证完成后已删除来宾机 `C:\POC-08` 临时目录；虚拟机在本轮开始前已运行，因此保留原运行状态。
