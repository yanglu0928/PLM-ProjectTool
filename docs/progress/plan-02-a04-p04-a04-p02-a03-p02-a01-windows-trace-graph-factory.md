# PLAN-02-A04-P04-A04-P02-A03-P02-A01：Windows Trace 图受控组合工厂

日期/版本：2026-10-19 / `0.1.0-dev.0`。状态：受控组合工厂及隔离真实HTTP/PG验收通过；启动模式待P02-A02。

|项目|结论|
|---|---|
|当前 Phase / WBS|Phase 2 / `PLAN-02-A04-P04-A04-P02-A03-P02-A01`|
|输入基线|冻结API-02图查询、CR-PLAN-001、P02-A01/A02 Plan WBS证明/桥、P02-A03-P01可选图HTTP合同|
|前置任务|0177 Schema、Plan读取及Trace图/游标服务已验；Windows当前账户`trace-graph-cursor-v1`读取器已存在但未正式供给|
|涉及模块/实体|Windows Trace图组合工厂、Owner注册和隔离验证夹具；不改业务Schema或冻结API|
|涉及API/权限|仅返回显式注入的可选GET路由；Session/License、TRACE_GRAPH_READ及每节点Owner当前授权，默认和现有平台模式不变|
|验收标准|真实Win11/PG18.6/ASGI固定WBS反向链、跨项目/撤权/License拒绝、页游标现时重证、缺依赖失败关闭、全量回归|
|风险|生产模式突然要求新Key导致现有平台不可启动、合成WBS/Trace误当客户正式事实、未注册类型被误称完整图|

此片只装配可复用路由工厂并用隔离合成数据验收，不改现有服务启动模式。下一片P02-A02接入显式受控启动模式与专用当前账户游标Key；缺真实目标账户/正式License信任不宣称生产发行。

实现/验收：组合固定Document、Requirement、SectionVersion、StructuredSpec、WbsItem五类受权Owner与Trace图分页链；尚无Owner的资源类型失败关闭或在受权限深图中省略并标`truncated`。Win11/PG18.6隔离合成版本/边及真实Session/ASGI，验证两页WBS反向边、跨项目/错版本/匿名/当前成员撤权后旧游标、License拒绝、缺游标依赖拒装配与零读取Audit。定向9项/17子例；最终全量3843通过/3跳过/6021子例。首轮全量在并行隔离PG验收期间，既有`test_windows_launcher_write_mode_is_explicit`单项失败（3842通过/1失败）；单项隔离复跑通过，停止并行后全量通过，未把首轮记为PASS。无Migration/冻结API/现有启动模式变化；撤工厂即回滚。开发wheel、正式账户Key、真实License信任、Server2025/Debian及完整Owner类型/UAT仍待。
