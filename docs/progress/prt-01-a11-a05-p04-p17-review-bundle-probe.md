# PRT-01-A11-A05-P04-P17：Review 六类子表合并读取隔离探针

2026-10-08 / 状态：`PROBE_COMPLETE_PRODUCTION_EQUIVALENCE_PENDING`；业务20并发P95仍`FAIL`。

编码前检查：Phase2；输入为P16连接/SQL分布、P15锁语义核查与CR-PRT-005。仅扩隔离验证脚本，使用同一Windows11隔离PG18.6中的合成Approved Prototype Review和完整Workflow；六类子表保持原`review_id`/`round_id`参数及逐表排序，比较六次顺序`to_jsonb`读取与单条`UNION ALL`/JSONB结果。根/目标轮共享锁仍由原生产仓储取得；不改生产代码、Schema、API、权限、事务锁或安全证明。JSONB只是微基准结果格式，尚未证明Native类型还原/篡改负例等价。

两次独立隔离脚本均退出0，六类子表逐行JSONB结果相等，完整原PG/HTTP Workflow链继续通过。单连接交替60轮顺序/合并P50约0.403/0.166与0.648/0.262ms，P95约0.845/0.315与1.116/0.416ms。20独立连接、三轮近秩P95中位顺序/合并约17.785/4.966与15.356/5.558ms。结果支持继续验证合并只读子表的候选；这些微基准不覆盖生产SQLAlchemy事务、原生UUID/bytea/timestamptz转换、全部Review负例，也不等于业务端到端P95收益。

P18生产实现前必须在CR-PRT-005记录并验证：Review根`FOR SHARE`及全部轮次一致性先行，目标轮`FOR SHARE`仍先于子表读取；合并结果对六类逐表精确分组/顺序，原生类型严格还原，不接受缺行、重复、错scope/project/round、篡改事件、快照、受审锁或异常类型；保留原`get_round`返回DTO和错误语义。先用定向及真实PG污染负例，再跑完整后端及独立客户端20并发，只有两项≤500ms且其他Gate证据齐全才能放行。无Schema/API/权限/数据迁移；如等价性或性能回归失败，恢复原六查询路径，历史不变、入口仍关闭。

TraceLink：CR-PRT-005 → P07/P15/P16 → P17 → DEC-20261008-1090 → P18。
