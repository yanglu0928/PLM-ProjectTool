# CR-EXEC-038：SUR-07-A08 目标布局 PostgreSQL 装载差分诊断

日期：2026-11-07  
状态：实施前记录；Hosted 复验中，A08 尚未通过。

## 证据与差异

Hosted Windows Server 2025 run [42278965171](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42278965171) 使用提交 96678398。A08 完整 PG 初始化仍由 initdb.exe 返回 3221225781（0xC0000135）；前置同run目标包 runtime/pgsql/bin 与 lib 到隔离 A08 进程 PATH 未改变结果，故 CR-EXEC-037 的根因假设未获支持。A08 未输出业务通过标记。同期前后端/构建、PG18 sidecar、P24/P25/P39/P40/A17/A34/A35 等列出的独立 job 成功；整体 run 仍因 A08 failure 不能视为全绿。此证据仅是 GitHub Hosted Windows Server 2025/D:，不是 Windows 11 实机结果。

## 实施前方案

在 A08 实际调用完整 initdb 的同一已安装目标目录、同一临时环境和同一子进程 PATH 下，增加只读的 initdb.exe --version 与 postgres.exe --version 差分探针。两个探针均把 stdout/stderr 直接丢弃，只保留整数退出码（或固定的 timeout/launch_error 分类）；不得打印原始路径、输出、异常消息或数据。之后照常调用原完整 smoke，不改变验收条件。异常摘要只扩展严格白名单字段。

## 影响、风险与回滚

只改 SUR-07-A08 验收验证器及其 workflow 诊断正则；不改产品逻辑、公共 smoke、PG 候选、安装包、API、Schema 或验收通过标准。风险是探针自身带来少量托管时长；探针只执行版本查询，不创建数据库、不写业务数据。若 Hosted 运行证明探针环境/模块也成功，问题将进一步缩小到初始化路径中的延迟加载/运行阶段，不能宣称已定位缺失 DLL。回滚移除探针包装与对应诊断字段即可。

## 验证计划

- Hosted Windows Server 2025，D: runner temp，使用同run、同commit、不可发行的候选包。
- 先运行语法和边界静态检查，再完整 A08 PG18/HTTPS/Edge/权限/License拒绝流程。
- 摘要继续只上传固定业务 markers 与经过 allowlist 的整数/固定分类；原始日志随 owned temp 清理且不上传。
- 仅当原有全部 A08 markers 成功时才可记 PASS_LIMITED；当前状态保持 NOT_PASSED。

## 实施记录

按上述边界在 A08 首个完整 initdb.exe 调用前，使用同一 env 直接查询目标布局内的 initdb.exe --version 和 postgres.exe --version。输出句柄指向 DEVNULL。探针结果并入安全摘要 allowlist，原 _run 在结束后恢复；完整 smoke 和业务断言保持原样。等待本次 GitHub Hosted workflow 复验，不预判结果。
