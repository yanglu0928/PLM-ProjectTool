# PRT-01-A11-A05-P04-P20：受控连接池资源前置核算

2026-10-08 / 状态：`PRECHECK_COMPLETE_TARGET_BUDGET_UNVERIFIED`。

编码前检查：Phase2；输入为CR-PRT-005、P19三轮默认/临时池交错诊断及现有Windows生产组合。仅读取代码、一次性PG18.6设置和VM硬件配置，不修改生产池、Schema、API、权限、目标服务或数据。验收为列清最大可能连接消费者与可核实的PG上限，并明确目标Server的未知项；静态资源计算不替代负载验收。无升级/迁移，撤前置记录不影响历史。

本机Win11隔离PostgreSQL18.6脚本退出0：`max_connections=100`、`superuser_reserved_connections=3`、`reserved_connections=0`、`shared_buffers=16384`个8kB块（约128MiB）、`work_mem=4096kB`。这些是本次`initdb`临时实例设置，不代表用户Windows Server 2025上的实际PostgreSQL配置。当前Windows API为一个Uvicorn Worker；业务Runtime默认池5+10（上限15），独立Maintenance Admission池20+0；Audit、Parser、AI Provider三个Worker各默认业务池4+0及准入池1+0。假设每类服务各一个、都达到各自上限且无其他进程，当前静态合计15+20+3×(4+1)=50；候选业务池20+0则为20+20+3×5=55。按本机临时库非保留连接额度97计算，候选留下42个连接名额，但不包含Bootstrap/维护CLI/探针、监控、人工DB会话、其他实例或未来Worker，也不证明内存安全；`work_mem`可由单连接内多个操作分别使用，不能简单按55×4MiB认定上界。

已发现本地VMware Windows Server 2025虚拟机配置16GiB内存/16 vCPU，本轮`vmrun list`显示未开机；宿主Win11当时可用内存约13.6GiB，少于VM标称16GiB，故本项不为性能核算强行启动虚拟机。VM内实际PG版本、`max_connections`、其他连接消费者、内存/交换、发行服务和真实20并发均未验证。不得从Win11或VMX配置推断Server 2025 PASS。

P21候选：在CR-PRT-005中先定义仅显式部署选择的有界API池配置（20+0候选）、单Worker/连接预算启动校验、原5+10回滚及负例；保持默认配置和Prototype入口关闭。只有目标实例连接/内存预算与重复20并发业务P95≤500ms客观证据成立，才考虑将其作为正式发行参数。当前性能FAIL、Gate3/UAT/可用包未通过。

TraceLink：CR-PRT-005 → P19 → P20 → DEC-20261008-1093 → P21。
