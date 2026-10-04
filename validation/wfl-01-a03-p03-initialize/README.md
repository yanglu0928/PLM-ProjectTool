# 内部 Workflow 初始化隔离验证

`verify.py` 使用 Windows 11/Python 3.13/PostgreSQL 18.6 本地 55432 测试环境。先启动已有 PoC 数据库并配置项目 src/数据库依赖搜索路径，再运行脚本；不使用生产库。脚本自建随机 `wflinit_*` 库，finally 删除，仅保存合成用户/Project/Workflow/Audit。

覆盖顺序/并发去重、初态与唯一审计、Audit/提交失败/调用方取消回滚、已有进度重试不重置。调用方是合成内部调用方；没有 Session/License/真实 Project 授权或 HTTP，因此不是权限或 UAT 验收。

2026-09-26 实际执行 PASS；后端 623 项无失败（2 项环境跳过），开发 wheel PASS。生产 Project 创建/既有项目初始化尚未接线。
