# CR-EXEC-011：修复 cloud PG smoke 子进程管道等待

- 状态：已记录，实施中
- 日期：2026-10-27
- 关联：PLT-PKG-01-A09-P51-A19、PR #55、run 40458978359
- 范围：只调整runner临时父包PG生命周期烟测的pg_ctl启动输出接管及失败清理。

## 证据

run `40458978359` 的源码/前端/PG sidecar/Python base/embedded backend/父包组装均通过。最后的clean extraction和PG smoke在 `pg_ctl.exe ... -w start` 阶段超过120秒。脚本通过 `subprocess.run(capture_output=True)` 启动pg_ctl；PostgreSQL后代进程继承stdout/stderr句柄，超时后Python等待pipe EOF，Actions job最终在45分钟上限被取消。该轮没有上传A19 smoke summary，不能计为通过。

## 决策与差异

启动pg_ctl时将stdout/stderr重定向到runner临时root内受限诊断日志文件，避免服务器子进程继承管道句柄；对pg_ctl作业本身设置有界等待，并在失败/超时finally阶段先查询PG状态，再尝试停止本次数据目录对应实例。启动失败时摘要只输出失败类别和服务日志尾部的非敏感诊断；临时目录清理仍只在RUNNER_TEMP直属非C盘子目录进行。继续校验数据库loopback、空库、pgvector版本与服务停止，不修改产品或父包。

## 风险、回滚与验收

- 若pg_ctl仍不能启动，bounded timeout后显示server日志，且必须停止已启动的服务；若服务无法停止则阻断清理并让hosted job结束回收整个runner。
- 回滚为恢复原始进程调用，并保留首次超时证据；不更改产品、正式安装或受保护数据。
- 下一次hosted run必须在45分钟内给出终态、输出启动/查询/关闭结果和清理结果；否则不得标PASS。
- 本项不代表产品API、服务账户ACL、License trust、Pilot或Release已验收。
