# PLT-PKG-01-A08-P09-P05-P03-A07-P03-P04：FileObject 升级前 TIFF 全量预检

日期：2026-10-01；状态：`ISOLATED_FILEOBJECT_PREFLIGHT_PASS / UPGRADE_WORKFLOW_OPEN`。

## 编码前检查

- 当前 Phase/WBS：Phase 2 / P04，仅解决已登记 FileObject 在维护窗口内的 JBIG TIFF 兼容检查。
- 输入基线：Gate 2 已冻结，CR-PKG-004 许可无JBIG隔离技术候选；A07-P03-P03 只读 TIFF 标签扫描。正式离线升级流程为“人工备份→维护模式→升级→Migration→启动→健康检查”，失败由实施团队人工恢复。
- 前置任务：`plt_maintenance_state` 与共享/排他 advisory fence 已存在；`doc_file_objects` 元数据与 `LocalFileStorage.open_verified_snapshot` 已存在；正式目标账户、升级器及完整 Release Gate 尚未通过。
- 涉及模块：仅离线升级预检工具及 TIFF 只读解析；不改运行中的 API、Parser、ORM、Migration、License、现有数据。
- 涉及实体：只读 `plt_maintenance_state` 与 `doc_file_objects` 的 `DOCUMENT` 项；不修改实体。
- 涉及 API/权限：无 HTTP API。运行方须持数据库只读授权及数据目录读取权限，工具自身拒绝非维护态；不能代替管理员备份或身份授权。
- 验收标准：完整枚举登记文档、精确文件 Hash/大小、TIFF 魔数/元数据与 JBIG 阻断；缺失/损坏/变更/非维护态/锁占用失败关闭；仅汇总计数，不输出文件名、路径、正文或数据库连接串。先合成验证，再隔离 PostgreSQL 与本地文件测试；不能以此宣称正式目标环境升级通过。
- 风险与回滚：长时间读锁/大文件扫描增加维护窗口，未登记磁盘孤儿不在 DB 清单；若实现/验证失败，不进入升级并撤工具，不对现有数据回滚操作。

## 实施与验证

`tools/scan_fileobject_jbig_upgrade.py` 在 PostgreSQL 18 会话持有与平台维护转换相同的 advisory 排他锁，确认 `MAINTENANCE` 后用只读 Repeatable Read 枚举全部 `DOCUMENT` FileObject，再次读取维护版本；通过 `LocalFileStorage.open_verified_snapshot` 逐项核大小/Hash与安全定位，用已核字节快照检查 TIFF/BigTIFF 魔数和 JBIG 压缩标签。`AVAILABLE`/`RESTRICTED` 内容必须可验证；`STAGED`/`FAILED`/`CLEANUP_PENDING` 阻断，`REMOVED` 计数跳过。结果仅有计数、阻断状态和 `upgrade_allowed`，不打印路径/名称/正文/连接串。遍历采用服务器端流式结果，无任意100k条硬截断；单 FileObject 仍遵循产品上传上限100MB，超过则阻断。

Windows 11 Python3.13定向单元6/6 PASS；安全存储合成涵盖 JBIG/非JBIG/非TIFF、篡改Hash、错定位、声明TIFF但魔数不符、不完整状态。独立 PostgreSQL18.6临时集群的最小关系表联调 `CLEAR / BLOCK_JBIG / BLOCK_UNKNOWN / 非维护态拒绝 / 排他锁冲突拒绝 / 文件篡改拒绝` PASS；另以全新数据库运行项目 Alembic 从空库至 `20260930_0051`，在真实 `auth_users`、`doc_file_objects`、`plt_maintenance_state` 约束下插入纯合成JBIG记录并获 `BLOCK_JBIG`。完整Schema演练结束后记录已删除、维护态恢复；临时集群已正常停止。未连接现有业务数据库或扫描客户数据。

首次从含中文路径启动 `initdb` 时发生 UTF-8/本地编码错误，隔离测试将固定 PostgreSQL18.6 的 `bin/share/lib` 复制至 ASCII 临时目录后成功；这不证明正式发行安装路径或 Server 2025 可用。测试用 `trust` 只绑定 127.0.0.1 的独立集群，非产品配置。含pgvector0.8.6的测试文件也仅放临时目录；不纳入 Git/正式安装。

## 边界与下一步

工具尚未纳入正式离线升级命令、备份凭据/服务静止核查和回滚流程；CLI 使用当前Windows账户数据库凭据入口，但本轮仅对核心函数做隔离库验证，未对正式目标账户运行CLI。维护锁不约束受管系统外的未知写入进程；备份、停写、ACL、进程静止、数据根完整性和人工恢复仍为独立门禁。`REMOVED` 历史记录与未登记孤儿磁盘文件不扫描；当前只证明数据库登记的可访问内容在快照时的兼容性。Debian13按用户指令暂缓实测，Server2025尚未验。不能据此声称升级可执行或包可发行，`release_eligible=false`。
