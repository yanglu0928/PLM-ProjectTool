# PRT-01-A11-A05-P04-P18：Review 子表单查询读取与等价性验证

2026-10-08 / 状态：`INTERNAL_PASS_PERFORMANCE_FAIL`。

编码前检查：Phase2；依据Gate2冻结Review资格/锁语义、CR-PRT-005 P17候选、DEC-1090及两轮隔离PG微基准。只改Review仓储目标Round已`FOR SHARE`锁定之后的六类子表读取和定向测试；不改Review根/全轮次/目标轮读取、六类一致性校验、公开DTO/API、Schema、权限、迁移、生产连接池或Prototype开关。验收为严格还原UUID/bytea/timestamptz/整数/文本/NULL，拒绝缺字段/多字段/错bucket/重复、正常及篡改Review真实PG、混合/隔离/多原型负例、全量后端及独立客户端20并发。风险是JSONB转换成本、非合成大型Review、GLOBAL nullable scope及测试计时扰动。

实现：六类子表按原`review_id`/`round_id`过滤，在一个`UNION ALL`查询中按类别及原键排序；使用固定ORM表名和绑定ID，不拼接用户输入。对JSONB逐列按既有表元数据还原原生类型、核对字段集合与非空、项目/轮次及主键重复；然后原样调用Review仓储既有快照、事件、受审锁、决策计数及最终DTO验证。Review根、全轮次、目标轮共享锁的取得顺序不变，无跨请求/事务缓存。正常读取不向外暴露JSONB或数据库路径。

验证：定向单元11通过/33子例，后端全量3256通过/3跳过/4806子例。Windows11隔离PG18.6真实批准Review/Workflow脚本退出0；仅在该临时库里以`SET LOCAL session_replication_role='replica'`注入错误Decision事件Actor，读取拒绝，恢复原值后再次读取与完整Workflow通过（普通更新先被既有不可变触发器拒绝）。混合范围含缺决定/文件损坏/冲突、跨项目Link/撤权、多原型部分覆盖及正式并集PG/HTTP脚本分别退出0。合成资格122次请求SQL由P16的7076降至5856条，约58→48条/请求。独立客户端默认→临时20+0→默认交错两轮，临时池两项P95约533/533及540/512ms；默认前约629/604及614/611ms、默认后约673/611及656/634ms。两项均未同时≤500ms，且计时器/主机负载与P16不完全等价；不能据此宣称发行SLA或生产池调参。

兼容性/升级：仅内部Review仓储及验证工具/测试，无API/Schema/权限/依赖/配置或数据迁移，同步部署代码即可。回滚为恢复原六次子表查询，保持根/轮锁和历史不变；若后续发现JSONB类型或一致性缺陷，应先保持Prototype入口关闭再回滚。未验证Server2025、GLOBAL真实Review、所有可能规模的Review和发行环境20并发；Gate3/UAT/可用包仍未通过。下一项应定位剩余业务P95成本，只有客观达标及其他Gate证据齐备才可开启入口。

TraceLink：CR-PRT-005 → P17/DEC-1090 → P18/DEC-1091 → P19。
