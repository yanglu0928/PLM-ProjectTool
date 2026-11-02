# Windows 非发行父包云端离线暂存

本项目自动验收在 GitHub hosted Windows sandbox 中运行，不要求开发者电脑执行程序。自动化使用云端同一 workflow run 的候选 ZIP 和验证摘要，把文件暂存在 hosted runner 的非 C 盘工作目录，核对逐文件 SHA-256，再运行只读就绪报告和包内阻断诊断。

A40 工具位于 tools/stage_windows_parent_candidate_offline.py。回执要求：
- HOSTED_WINDOWS_CANDIDATE_STAGING_PASS_LIMITED
- installation_performed=false
- services_started=false
- release_eligible=false
- legal_clearance=false

该流程只用于云端验证非发行候选的接收、校验和隔离暂存。它不安装或启动产品、不注册服务、不连接数据库，也不代表 Windows 11 实机、Pilot 或正式 Release 通过。hosted Windows Server 2025 结果不能推定 Windows 11 兼容。
