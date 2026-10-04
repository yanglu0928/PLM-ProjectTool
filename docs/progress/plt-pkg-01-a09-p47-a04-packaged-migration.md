# PLT-PKG-01-A09-P47-A04：当前非发行候选随包 PG18 迁移

日期：2026-10-02；Phase 2；结果：`SYNTHETIC_CURRENT_APP_PACKAGED_PG18_MIGRATION_PASS`。

编码前检查：CR-PKG-008、P47-A03 新 ZIP SHA/21,178项清洁解包、固定迁移0052、既有一次性 PostgreSQL 演练工具均具备。范围只新增非发行候选独立迁移烟测及测试，不修改产品模块/API/ORM/Migration/权限、现有数据库、安装根或运行服务；实体涉及现有 `plm.plt_system_configurations` 与 `plm.evd_evidence_records`。验收为包内 Python/PG18/pgvector、0052空库/有数据升级、保留已有行、受控降级/再升、一次性资源清理。风险是临时集群残留或把任意行保留误称 Evidence 历史迁移完整覆盖；因此限定直接 ASCII Temp 清洁暂存、唯一临时数据目录、停止检查与精确表述。

以 ZIP SHA `eb2494be5de85b64a7ac64ce02112ed52454d0423d2a7e8406f120a126e14ed7` 和 P47-A03 暂存为唯一输入，启动包内 PG18 临时回环集群。库一先用包内 Python Alembic 升到 `20260930_0051`，插入一条纯合成 `poc.current_app` 配置记录，升到 `20261001_0052` 并确认行保留、新 `source_parse_record_id` 列及触发器存在；再降回0051并再次升至0052，行仍保留。库二为空库，直接升至0052。扩展 `vector` 为0.8.6。实际脚本退出0，新失败关闭边界测试1/1；临时 PG 已停止、数据目录已删除，未接触既有数据库。

本项仅是**隔离合成迁移演练**，不是有真实 Evidence 旧记录的升级测试、正式数据库升级或生产安装。没有验证 HTTPS、正式 TLS/License 信任、Server2025/Debian、法律/NOTICE、AI质量、UAT及 Gate 3；`release_eligible=false`。下一项 P47-A05 验证同一候选隔离 HTTPS/License 链；回滚为弃用测试脚本/候选，原 P45 ZIP及正式数据不变。
