# PLT-PKG-01-A09-P18-A01：随包迁移在隔离空库上执行

日期：2026-10-01；状态：`BUNDLED_EMPTY_DB_MIGRATION_PASS / RELEASE_BLOCKED`。

编码前检查：Phase2/Gate3开放；输入为P15固定组合ZIP（SHA-256 `c54a7862872d402a6c9763287a508dc63dd602049f93aa6097e5a8e8e0766ef2`）、P17隔离安装布局及现有冻结/增量Schema至0051。此任务只验证**已打包**Alembic代码能否在全新临时PG18上初始化空库，不修改任何Migration/ORM/API/权限、正式安装根、服务或已有数据库。验收：固定ZIP与目标21,103件逐件Hash一致，空库升至0051、vector0.8.6、完整表集存在，实例停机并清理；失败不得宣称初始化可用。风险：临时`trust`仅在随机loopback端口可用，不能作为生产认证/升级方案。回滚仅弃用本轮合成临时库/验证工具，未修改原候选。

本机实测：从`C:\Users\17231\AppData\Local\Temp\plm-install-rehearsal-38b12260d10a`逐件复核固定ZIP/安装布局，随后在唯一ASCII Temp数据目录执行`initdb --encoding=UTF8 --locale=C`，仅监听127.0.0.1。由随包嵌入式Python调用项目`upgrade_database(..., head)`，SQL回读`plm.alembic_version=20260930_0051`、`pg_extension.vector=0.8.6`、`plm` schema 72张表。`pg_ctl -w stop`与状态检查后清理本轮数据目录；复核无`plm-package-migration-*`临时目录/进程，`C:\PLMTool`仍不存在。定向单元3/3。无Secret、客户数据或正式DB URL进入命令行/环境；测试代码只在子进程内部构造无密码的合成loopback URL。

此项不含有数据升级/降级、四类备份恢复、目标账户与Windows服务、正式License/第三方合规、业务API/前端联动、Server2025或Debian13验收。下一项在同一隔离布局验证仅公共健康HTTP与前端静态资产的可逆本机链；正式写组合缺发行信任源仍失败关闭，不以默认应用HTTP替代产品UAT。`release_eligible=false`。
