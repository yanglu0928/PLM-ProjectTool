# OUT-01-A01-P31：Output 可重试失败原子回队验收

- 日期：2026-11-05
- 结论：PASS_SCOPE_LIMITED
- 变更依据：CR-OUT-027
- hosted workflow：[run 41963052416](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41963052416)
- 验收环境：GitHub hosted Windows Server 2025，临时目录/数据库位于 D 盘；PostgreSQL 18.6 + pgvector 0.8.6，纯合成记录。
- 父包：SHA-256 `61593a1aab3529b09c15baa0231d6723eb1cad337a709db272b6148db2c87e1b`，20,214 个 payload 文件。
- 兼容/发布：本次不是产品安装或发行；不构成 Windows 11 设备验证、Pilot、Gate 3 或 Release 通过。

## 验收结果

父包临时 PostgreSQL smoke 报告 `output_generation_retry_validation.status=PASS_SCOPE_LIMITED`，确认：

- 暂态失败在固定30秒退避后将 Jobs 转为 `RETRY_WAIT`，同时将 Output 原子回到 `QUEUED` 并清除当前 execution ref。
- attempt 达到上限时，Jobs 与 Output 在同一事务内原子转为 `FAILED`。
- Job 与 Output Audit 使用同一 UnitOfWork；Audit 写入失败时两个 Owner 的状态一并回滚。
- 错 worker、过期 fencing token、非白名单错误及自由文本都被拒绝。
- 全部使用合成数据；没有生成文件、执行插件、调用外部 API 或启动产品服务。

同一 hosted run 的后端全量测试/wheel、前端测试与构建、PG18/pgvector sidecar、Windows 父包组装、A17 packaged PlanVersion Edge/HTTPS/PostgreSQL flow、A34 隔离替换与手动恢复演练均成功。父包 lifecycle 报告同时重验 P29、P30 与 P31。

## 独立阻塞与限制

P25 的真实 Output Create HTTP/Edge job仍在 `initdb.exe` 初始化前以 Windows `0xC0000135`（DLL not found）失败；本轮未启动该 HTTP/Edge 流程。独立的同run父包 PG18 lifecycle smoke 成功，且 P31 已在该独立环境通过。故 P25 保持 `BLOCKED_DIAGNOSTIC`，不能把整体 workflow 标为全绿。

本项不证明真实 Worker 重启、插件信任/执行、文件生成或 Artifact 发布链。没有 Schema/Migration/API/default挂载变化。Pilot、Gate 3 与正式 Release 继续保持 NOT_READY。程序代码和验证仅在 GitHub hosted runner 执行，未在用户本机或 C 盘运行。
