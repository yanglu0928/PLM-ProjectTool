# Entrypoints

保留给 FastAPI 与 Worker 的进程入口和 Composition Root。入口只负责装配、生命周期和适配，不承载业务规则，也不直接写其他模块数据。

Windows 维护进程候选诊断：`python -m plm_assistant.entrypoints.process_inventory_windows <deployment-account-SID> <absolute-runtime-root>`。只读报告不会包含进程命令行或 Secret；`DIAGNOSTIC_ONLY` 不授予备份、迁移或升级许可。正式停写仍须服务/进程退出、版本、文件句柄和数据库会话等独立证据。

Windows 服务安装分两步：先运行 `python -m plm_assistant.entrypoints.service_plan_windows <absolute-python.exe> <absolute-bootstrap.yaml>` 得到 `PLAN_ONLY` 三角色命令计划；其结果并不证明目标解释器/模型内容/账户可运行。受控管理员在已供给目标账户 Vault、ACL、License 后，须用目标 Python 3.13 x64 解释器本身启动安装器，并交互执行 `python -m plm_assistant.entrypoints.service_install_windows --install {API|AUDIT_WORKER|PARSER_WORKER} <absolute-python.exe> <absolute-bootstrap.yaml> <account>`。安装器要求参数中的解释器与当前进程为同一文件、已安装包版本匹配；密码仅通过交互提示读取，不放 argv。每次只登记一个手动启动服务，不自动启动/覆盖/卸载。安装后须独立核对 SCM 配置、账户/PID、实际启停、运行标记和资源静止；目前真实 SCM 验收未完成，不得用于生产备份或迁移许可。

SCM 只读检查：`python -m plm_assistant.entrypoints.service_inventory_windows {API|AUDIT_WORKER|PARSER_WORKER|ALL}`。仅查询固定服务的安装、类型、启动方式、状态及 RUNNING 时报告的 PID；不输出二进制路径或账户，查询错误不输出部分报告。结果恒为 `DIAGNOSTIC_ONLY`，不证明运行进程身份或资源静止，不授权备份/迁移。

安装定义只读对账：`python -m plm_assistant.entrypoints.service_assessment_windows --assess {API|AUDIT_WORKER|PARSER_WORKER} <absolute-python.exe> <absolute-bootstrap.yaml>`，交互输入预期服务账户，不在命令行或报告中显示。工具严格比较 SCM 保存的类型、手动启动、错误策略、完整 binary path 与账户；不匹配时仅给固定原因码，返回码 1。配置匹配也仅是诊断，不说明进程身份、实际停写或可备份/迁移。
