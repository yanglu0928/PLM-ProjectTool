# PLT-PKG-01-A09-P12：Windows PG18/pgvector 最小运行旁包

日期：2026-10-01；状态：`NON_RELEASE_RUNTIME_INTEGRITY_PASS / RELEASE_BLOCKED`。

编码前检查：Phase 2/Gate 3 开放；P11 四份离线输入、pgvector 源码提交和运行核心文件的字节证据已固定。本项仅新增非发行打包/清洁解包工具与测试，不改业务代码、冻结 API、ORM/Migration、权限、现有数据库或正式安装。验收为精选目录、必要许可、版本/核心文件 Hash、ZIP 全量回读与新 ASCII 目录逐件复核；失败即放弃新候选。回滚保留 P11 和历史 PoC，只弃用新 Git 忽略 ZIP、撤新工具，不触碰数据。

从 `D:\POC-02\postgresql-18.6\pgsql` 只选 `bin/lib/share`（1,626 件），另带 `server_license.txt`、PostgreSQL 命令行第三方许可文本和 pgvector 源码 `LICENSE`，共 1,629 件。明确排除 `doc/include/pgAdmin 4/StackBuilder/data/logs`，不复用旧 PoC bundle 的测试源码、`__pycache__` 或 `.pyc`。输入先核 P11 报告 SHA-256 `15c01027e6e6feeefb3ae91c4e77d5c158d6f1bf395c4e1ba5160ec15572d0ee`、`pg_config` 18.6、`vector.dll`/control/SQL/服务器许可固定 Hash 和三个附加许可文本固定 Hash；逐件在写 ZIP 前后核源，ZIP 内全部载荷和三份顶层清单逐件回读。

本机新非发行 ZIP（Git 忽略）`artifacts/package-prep/windows11/pg18-runtime-candidate-65021fa555cd/NOT-FOR-RELEASE-windows-pg18-pgvector-runtime.zip`：56,565,724 字节，SHA-256 `d0e038b43240369f7cd66396c34cd8e56d5a7a5a51ae3bc6f5fc41783baa7fd9`，`release_eligible=false`。新 ASCII 临时目录 `C:\Users\17231\AppData\Local\Temp\plm-pg18-stage-c04fe5ea354b` 清洁解包 1,629/1,629 Hash 和完整文件集合 PASS；`pg_config --version` 输出 `PostgreSQL 18.6`，`vector.dll`/`vector--0.8.6.sql` 与 P11 固定值一致；`payload/pgsql/data` 和 pgAdmin 目录不存在。单元 3/3 PASS。首次打包因新增命令行许可 SHA 常量漏两位被拒；与实际文件核对、修正后重新打包/回读/解包，未改输入或放松核验。

这是数据库**运行旁包，不是完整程序包或安装器**。尚未在此新目录执行 `initdb`、启动数据库、`CREATE EXTENSION vector`、服务账户/ACL/SCM、正式备份升级，也未完成法律审查/源码交付或 Windows Server 2025 产品安装验收；Debian 13 依用户指令暂缓但仍是目标。下一项可在隔离新目录对纯合成数据库做 `initdb`/启动/vector 烟测，严格不接现有数据库；完成后仍不能把 Gate 3 或 Release 标记 PASS。
