# PRT-01-A11-A05-P04-P21：显式有界API业务连接池档位

2026-10-08 / 状态：`OPTIONAL_CONFIGURATION_INTERNAL_PASS_PERFORMANCE_FAIL`。

编码前检查：Phase2；输入为CR-PRT-005 P21实施前计划、P19连接取得路径及P20连接预算。仅扩非Secret Bootstrap配置和Windows生产API业务Runtime装配，不改数据库Schema、公开API、权限、维护准入/Worker池、Prototype开关或数据。验收：旧配置无感保持5+10；只接受`DEFAULT`/`TWENTY_FIXED`两档，20+0须在实际PG启动时验证连接名额；非法配置/不足/异常失败关闭并释放Runtime；真实临时PG、定向与后端全量通过。风险：静态连接额度不等于动态内存/目标Server性能证明，不能自动放行。

实现：`api_database_pool_profile`非Secret设置缺省`DEFAULT`，可由既有Bootstrap YAML或受控`PLM_`环境源显式给出`TWENTY_FIXED`。旧默认路径仍调用原`create_database_runtime(database_url)`，保持5+10；仅显式档位传`DatabaseEngineOptions(pool_size=20,max_overflow=0)`。生产装配在该档位完成DB连通及Schema检查后，读取实际PostgreSQL 18的版本号及`max_connections`、`superuser_reserved_connections`、`reserved_connections`，要求版本号及三项齐全且普通连接额度≥80（候选已知池上限55+运维缓冲25）；缺项、非数字、不足或查询异常均以固定启动错误拒绝并dispose。维护准入池20及三个Worker各5未改。配置档位只改变API池选项，不能开启Prototype资格或Gate。

验证：Bootstrap/生产前置定向20通过、46子例，覆盖缺省/YAML/环境覆盖、未知/大小写/空白档位、可用额度83与82边界、缺项/非数字、启动失败固定错误与Runtime清理。Windows11一次性PG18.6实测100最大/3超管保留，显式预算函数正向接受，完整旧PROJECT Workflow脚本退出0。后端全量3259通过/3跳过/4815子例。未运行正式Windows API服务、未在Server2025启用此档位，也未以该配置在正式信任源与发行拓扑下测20并发；P19独立诊断第三轮仍超500ms。因此性能FAIL、Prototype正常入口/Gate3/UAT/可用包继续阻塞。

升级/回滚：无迁移、新依赖或数据改写。部署旧配置保持原行为；显式档位可删除或设`DEFAULT`并重启回到5+10，历史不动。启动前还必须核对目标PG连接、其他进程与内存，不能把本机临时PG≥80作为Server2025验收。TraceLink：CR-PRT-005 → P19/P20 → P21/DEC-1094 → 后续目标环境与稳定性能验收。
