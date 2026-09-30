# Entrypoints

保留给 FastAPI 与 Worker 的进程入口和 Composition Root。入口只负责装配、生命周期和适配，不承载业务规则，也不直接写其他模块数据。

Windows 维护进程候选诊断：`python -m plm_assistant.entrypoints.process_inventory_windows <deployment-account-SID> <absolute-runtime-root>`。只读报告不会包含进程命令行或 Secret；`DIAGNOSTIC_ONLY` 不授予备份、迁移或升级许可。正式停写仍须服务/进程退出、版本、文件句柄和数据库会话等独立证据。

Windows 服务安装分两步：先运行 `python -m plm_assistant.entrypoints.service_plan_windows <absolute-python.exe> <absolute-bootstrap.yaml>` 得到 `PLAN_ONLY` 三角色命令计划；其结果并不证明目标解释器/模型内容/账户可运行。受控管理员在已供给目标账户 Vault、ACL、License 后，须用目标 Python 3.13 x64 解释器本身启动安装器，并交互执行 `python -m plm_assistant.entrypoints.service_install_windows --install {API|AUDIT_WORKER|PARSER_WORKER} <absolute-python.exe> <absolute-bootstrap.yaml> <account>`。安装器要求参数中的解释器与当前进程为同一文件、已安装包版本匹配；密码仅通过交互提示读取，不放 argv。每次只登记一个手动启动服务，不自动启动/覆盖/卸载。安装后须独立核对 SCM 配置、账户/PID、实际启停、运行标记和资源静止；目前真实 SCM 验收未完成，不得用于生产备份或迁移许可。
