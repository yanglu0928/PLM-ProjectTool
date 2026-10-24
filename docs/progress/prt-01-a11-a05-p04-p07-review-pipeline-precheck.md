# PRT-01-A11-A05-P04-P07：Review 同事务流水线前置探针

2026-10-08 / 状态：`PROBE_COMPLETE_NO_SAFE_OPTIMIZATION_SELECTED`，20并发资格读取性能仍 `FAIL`。

编码前检查：Phase 2；输入为 P04-P06 每次资格约18条 Review 查询及 CR-PRT-005；前置为 Windows 11 隔离 PostgreSQL 18.6、正式批准的合成 Prototype/Review/Trace/文件/Link 夹具。仅修改验证脚本，不碰生产模块、实体、Schema、API、权限或客户数据。验收为同一事务中六类子表顺序查询与 psycopg pipeline 返回逐表相同，随后完成完整 Workflow 链；风险是探针不等于共享 SQLAlchemy 仓储的锁序/篡改负例证明，不能直接移植。

以 Review 正式批准轮次，在同一隔离库内按仓储既有次序读取 Assignment、Decision、Snapshot、SnapshotRef、SubjectLock、Event 六类子表。保持参数化 `review_id`/`round_id` 和主键或 reviewer 排序；顺序与 pipeline 在同一连接/事务内逐表结果相等。预热五次后交替测60轮：顺序 P50/P95约0.336/0.645ms，pipeline约0.262/0.335ms。20个独立连接各预热后同步启动，三轮每轮第19个完成时间作为近秩 P95：顺序为13.029/11.612/13.762ms（中位13.029ms），pipeline为19.588/16.095/15.208ms（中位16.095ms）。脚本退出0，完整真实 PG/HTTP Workflow 链继续通过，临时库/实例清理。

单连接微小收益不能解释上一轮真实 Uvicorn 两项约594/632ms 的整体 P95；20连接对照更无稳定收益。因此不修改共享 Review 仓储，不移动根/轮 `FOR SHARE` 锁，不删除事件、快照、受审锁或计数一致性校验。当前探针仅覆盖六类子表相等与正常路径，未证明生产 SQLAlchemy 事务混用 pipeline 后的锁序和篡改失败关闭；不得标记生产优化或性能 PASS。无迁移；撤探针脚本即可回滚，原冻结版本和业务历史不变。下一独立项从剩余 Requirement/Prototype 查询中选单一可证明重复往返，先记录偏差与安全验证再改；若无可安全收益，继续转其他 Phase 2 工作。Prototype 生产入口、Gate 3、可用程序包仍未通过。
