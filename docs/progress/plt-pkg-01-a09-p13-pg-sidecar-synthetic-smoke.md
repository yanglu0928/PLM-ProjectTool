# PLT-PKG-01-A09-P13：最小数据库旁包隔离功能烟测

日期：2026-10-01；状态：`WINDOWS11_SYNTHETIC_PG18_PGVECTOR_PASS / RELEASE_BLOCKED`。

编码前检查：Phase 2/Gate 3 开放；P12 非发行旁包经ZIP与新 ASCII Temp 目录逐件核验。只新增隔离验证脚本及安全边界单测；不改Schema/Migration/API/产品装配，不接已有数据库或正式客户数据。输入是 `C:\Users\17231\AppData\Local\Temp\plm-pg18-stage-c04fe5ea354b`，脚本再次全量验1,629件Hash，只接受ASCII Temp子目录，`initdb` 在另一个唯一临时目录建立纯合成实例；仅 `127.0.0.1` 随机端口、临时 `trust`，不是生产认证配置。回滚撤本工具和历史测试记录；正常退出停机后只清理由工具本轮创建的临时目录，不触及原包/其他实例。

首次运行时 Windows 上 PostgreSQL 子进程继承 `pg_ctl start` 的被捕获 stdout/stderr 管道，造成 Python 等待 EOF 直至超时；实例日志显示仅 loopback 启动，SQL 尚未执行。使用本次临时目录的 `pg_ctl -m fast -w stop` 正常停机，确认子进程退出且临时数据目录清理后，改为启动命令不捕获可被子进程继承的管道，重新从同一已核旁包完整执行。此为测试入口偏差，不改PG二进制、项目代码或正式安装方案。

复验结果：`initdb --encoding=UTF8 --locale=C`、PostgreSQL 18.6 启动、`CREATE EXTENSION vector` 回读0.8.6、两条纯合成三维向量、HNSW索引及最近邻 `origin` 均通过；退出时 `pg_ctl -w stop`、状态检查及临时数据清理通过。定向单元5/5（P13安全边界2项、P12筛选3项）。本轮没有留下运行中的合成PG进程或 `plm-pg18-synthetic-*` 数据目录。

本项只证明该Windows11新旁包的合成最小功能链，不包括业务Schema/全迁移、备份恢复、并发/性能、正式服务账户/ACL/认证、Windows Server2025产品包验收、Debian13或法律发行审查；不能关闭Gate 3。下一任务将只做 P12 PG旁包与已核统一候选的可追溯组合输入/冲突计划，不直接安装或替用户建立服务。
