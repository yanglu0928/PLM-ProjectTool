# Workflow 四表隔离验证

Windows 11 / Python 3.13 / PostgreSQL 18.6，本机端口 55432、测试用户 poc_admin（测试环境，无真实业务数据）。运行 `verify.py` 前将后端 src 和项目已安装的数据库依赖加入 Python 搜索路径；测试库名为随机 `wfl01a03_*`，由脚本创建，在 finally 删除，只操作脚本自己创建的库。

脚本：空库全量升级/ORM parity/0030 down；创建合成既有 Project；升级/空 Workflow down/re-up；核对 Project 未变；完整/半套实例、未知版本/错误 fingerprint、定义防改写、跨项目归属、状态/指针/锁、BLOCKED 恢复和终态防复活；非空 downgrade 拒绝。

阶段完成路径使用纯 SQL 合成结构，**故意不证明客户确认、Evidence、Review 或业务 Gate**。不得用这些结果宣称正式阶段通过。尚无业务写 API 或生产初始化接线。

2026-09-26 已运行 PASS；后端 619 项无失败（2 项既有符号链接环境跳过）。Server 2025 未运行，Debian 13 暂不验证。
