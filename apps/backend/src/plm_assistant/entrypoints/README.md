# Entrypoints

保留给 FastAPI 与 Worker 的进程入口和 Composition Root。入口只负责装配、生命周期和适配，不承载业务规则，也不直接写其他模块数据。
