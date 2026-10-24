# PRT-01-A11-A05-P01：隔离 PostgreSQL 与 Prototype 制品物理证明

日期：2026-10-08。状态：`PRT_01_A11_A05_P01_PHYSICAL_PG_PASS`；仅 Document 物理证明边界，不代表完整 Workflow 资格通过。

编码前检查：遵循 Gate 2 冻结 Schema、`CR-PRT-005` 的磁盘完整性修订、A11-A03 Document公开Port与A04显式可选组合。本项只验证真实 Windows11/PG18.6/磁盘情况下固定 DocumentVersion 的可访问性与字节一致性；不修改生产逻辑、权限、API或数据库结构。共享测试端口55434当前未运行且旧数据目录归属未知，不启动/清理旧实例；采用本轮创建的ASCII Temp隔离实例、随机loopback端口与仅本轮的临时trust认证。

验证脚本复制本仓库既有PG18.6与pgvector运行件到唯一临时目录，初始化空库、迁移至当前head并运行Alembic drift检查；创建合成PROJECT Document、真实文件与对应数据库版本，调用正式`SqlAlchemyPrototypeWorkflowArtifactIntegrityProof`和`LocalFileStorage`。结果：真实匹配通过；跨项目、磁盘字节篡改、文件缺失均返回无证明；两次运行退出0。单次合成证明耗时约216.42ms/194.80ms，只是本机样本，不是20并发或SLA证明。Alembic对既有向量表达式索引及计算默认值发出比较警告，但`No new upgrade operations detected`。脚本检查服务停机后才限定删除本轮目录，事后无该前缀目录或PostgreSQL进程。

兼容性/升级/回滚：仅增加验证脚本和说明；无迁移、依赖或生产程序变化。下一项 A05-P02 需完整Prototype Owner和HTTP/PG真实验收，之后再测并发与开启生产路由/页面；Gate3仍BLOCKED。

TraceLink：`CR-PRT-005` 物理完整性修订 → A11-A03 Document证明 → A11-A05-P01真实PG/文件 → A05-P02完整Owner/HTTP → 生产显式启用。
