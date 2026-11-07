# PLG-03-A02：Windows 子进程树启动 containment 结果

- Change Request：CR-EXEC-048
- 日期：2026-11-07
- 结果：`PASS_SCOPE_LIMITED`
- 环境：GitHub Hosted Windows Server 2025；D-drive runner temp；synthetic Python child only。

## Changed

Windows Process Host 曾在进程启动后才尝试 Job Object 归属，静态检查发现主程序可能先于归属执行。按 CR-EXEC-048 改为携带显式 Win32 `CREATE_SUSPENDED=0x00000004` 创建，创建 kill-on-close Job Object，完成进程归属，再恢复初始线程；创建/配置/归属/线程定位或恢复失败均保持失败关闭。POSIX进程组路径不变。

此前首轮Hosted run 42318583193失败并保留为历史证据；固定诊断 run 42319306937 将失败定位到 `thread_resume;native=0`，之后在更新CR的基础上修复，未掩盖或覆盖首轮结果。

## Tests and evidence

Hosted workflow run [42319974381](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42319974381)：

- 后端全量 4,095 项通过，Host 共 8 项通过，wheel成功。
- descendant测试要求 synthetic child 实际启动后代、父进程进入超时；Host返回 `PLUGIN_TIMEOUT`，在后代计划写入时间之后受控marker仍不存在。
- 前端测试/build、PG18 sidecar/父包、P25/P40/A17/A34/A35/P24/P39/A50作业成功。
- A17同run含P45真实IN_REVIEW PlanVersion snapshot及P46零写入拒绝marker。
- 17 jobs中16 success；唯一失败为SUR-07-A08 `initdb.exe` 3221225781。target initdb只读probe=0，受控TEMP环境probe同码，未应用替代环境；按CR-EXEC-039停止该排查路线。

## Limits

只验证Hosted Windows Server 2025上的合成进程及子进程树清理，不代表Windows 11实机兼容、真实Publisher trust、插件发行或操作系统级完整sandbox。没有真实/客户/第三方插件、生产Output/Worker、外部AI调用、业务数据库写入、API或Migration变更。Pilot、Gate 3及正式Release仍未通过。
