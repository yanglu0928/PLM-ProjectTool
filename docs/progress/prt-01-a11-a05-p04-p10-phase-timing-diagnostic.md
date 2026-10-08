# PRT-01-A11-A05-P04-P10：资格请求阶段墙钟诊断

2026-10-08 / 状态：`DIAGNOSTIC_COMPLETE_PERFORMANCE_FAIL`，尚未证明可安全实施的生产调参。

编码前检查：Phase2；输入为CR-PRT-005、P09后约58条SQL/资格及真实Uvicorn20并发P95>500ms；前置Windows11隔离PG18.6/pgvector、正式合成Requirement/Prototype/Review/Trace/本地文件夹具已通过。仅在隔离验证脚本临时包装Application/Repository方法，不改生产程序、Schema、API、权限或连接池。验收为正常请求结果和临时资源清理不变、打印分段P50/P95与峰值重叠；风险是并发方法墙钟包含等待/调度，且嵌套分段不可相加，不能据此宣称发行SLA。

无SQL事件计时器的隔离ASGI20并发三轮近秩P95中位，默认5+10池两项约645/637ms；只在测试进程临时换20+0池后约550/553ms，仍大于500ms。真实Uvicorn loopback本轮三次阶段诊断分别约598/596、584/565、580/574ms；健康端点对照第三次P95约91ms，不能直接从业务P95扣除。方法计时仅包装网络负载阶段，122次正式资格读取结果仍200/强ETag/PROTOTYPE，退出0。代表性第三次：`WorkflowChecklistQualificationPreviewService.get` P50/P95约63/87ms，峰值重叠5；Prototype Owner约55/77ms，峰值5；Requirement Owner约25/38ms，Prototype制品/Review约17/26ms；Session validate约3/5ms，项目授权约1/2ms。嵌套计时不可相加；与端到端约574–580ms的差距发生在这些方法计时之外或请求分批进入之前。可能涉及Uvicorn接入、AnyIO线程调度、连接获取、Windows loopback客户端等，现有证据不足以区分，不宜改生产池/服务并发参数或放宽500ms目标。

兼容性/升级/回滚：只新增隔离工具`--phase-diagnostic`，无生产代码、依赖、配置、数据或迁移；撤工具包装可回滚，业务历史不变。工具上下文退出即恢复原方法，Uvicorn/PG临时实例按原流程清理。下一独立项应在同一负载下记录每轮客户端发起、服务端ASGI进入、`run_in_threadpool`方法开始/结束、响应完成的时间差，并对照健康请求；只有定位真实瓶颈且不削弱授权/文件/Review后才提出调参或代码修订。当前Prototype生产入口保持关闭，Gate3/UAT/可用包未通过。
