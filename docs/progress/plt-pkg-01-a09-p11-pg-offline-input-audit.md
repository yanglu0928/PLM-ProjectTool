# PLT-PKG-01-A09-P11：PostgreSQL18/pgvector Windows离线输入核查

日期：2026-10-01；状态：`OFFLINE_INPUT_BYTES_VERIFIED / RELEASE_PACKAGE_OPEN`。机读结果见 [PG离线输入清单](plt-pkg-01-a09-p11-pg-offline-inputs.json)，SHA-256 `15c01027e6e6feeefb3ae91c4e77d5c158d6f1bf395c4e1ba5160ec15572d0ee`。

编码前检查：Phase 2 / 本WBS；输入为POC-02已登记的PostgreSQL18.6、pgvector0.8.6与Windows11/Server2025隔离验证历史。只读核离线制品、源码提交、运行DLL/SQL/许可文本和旧PoC bundle，不启动/安装PostgreSQL、不接触正式数据库。实体/API/权限/Migration：无。本项验收为精确字节与版本核对、报告是否可直接用于发行；坏Hash/版本必须拒绝。回滚只撤新审计工具/报告，既有制品和数据库不改。

本机四份已下载输入与POC-02清单逐件大小/SHA-256一致：PostgreSQL18.6 Windows installer、Windows二进制ZIP、pgvector0.8.6源码ZIP及当时构建用的VS Build Tools引导程序。运行目录`D:\POC-02\postgresql-18.6\pgsql`的`pg_config --version`为18.6；`vector.dll`、`vector.control`、`vector--0.8.6.sql`、`server_license.txt`四项Hash固定；pgvector源码工作树HEAD为`8ee86c96f0fd72390f890aa8a336fda6d3ab4c6c`且其`LICENSE`文本Hash匹配。旧Windows Server2025 PoC bundle及其中53,165,988字节的内层运行ZIP Hash一致。定向单元3/3通过。

审计首次运行因新脚本抄录内层ZIP SHA-256漏两个字符而按设计拒绝；对照原PoC manifest/实际值修正常量后完整重跑PASS，未改历史制品或放松核验。旧PoC bundle包含5个`__pycache__`/`.pyc`测试缓存条目及PoC测试代码，**不能直接改名为客户发行包**。VS Build Tools引导程序是构建输入，不等于目标运行时可直接分发依赖。旧PoC的Windows Server2025断网验证是POC-02特定功能链的历史证据，不等于本产品正式账户/安装/License/Gate验收。PostgreSQL[官方Windows下载页](https://www.postgresql.org/download/windows/)列出EDB安装器与高级用户二进制ZIP；本轮只核本地已锁制品，不重新下载或替换版本。

下一任务应从已锁运行目录构建全新、无PoC测试缓存/数据目录的**非发行最小数据库运行包**，含精确许可文本/来源Hash、全量清单与新目录解包验证；仍需独立完成安装器、ACL/目标服务账户、备份/升级、三平台与发行审查。Debian13按用户现指令暂缓验证但保留兼容目标。`release_eligible=false`。
