# Entrypoints

保留给 FastAPI 与 Worker 的进程入口和 Composition Root。入口只负责装配、生命周期和适配，不承载业务规则，也不直接写其他模块数据。

Windows 维护进程候选诊断：`python -m plm_assistant.entrypoints.process_inventory_windows <deployment-account-SID> <absolute-runtime-root>`。只读报告不会包含进程命令行或 Secret；`DIAGNOSTIC_ONLY` 不授予备份、迁移或升级许可。正式停写仍须服务/进程退出、版本、文件句柄和数据库会话等独立证据。
