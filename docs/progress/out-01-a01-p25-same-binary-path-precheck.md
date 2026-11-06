# OUT-01-A01-P25 编码前检查：同一解包PG二进制的 PATH 单变量对照

- 日期：2026-11-06
- 状态：编码前检查通过；Hosted双臂差分待实现/运行
- WBS：OUT-01-A01-P25
- 基线：冻结API Contract V1、DB Schema V1及CR-OUT-021；只改P25诊断比较脚本/证据，不改产品代码、API、Schema/Migration、Publisher trust或安装包。
- 依据：Hosted run [42159992981](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42159992981) 中同一P25 job的既有父包PG18 smoke成功；同run父包解包的PG payload与sidecar 1,627文件hash一致，但移除Node目录后的PATH中，父包对照与P25 initdb均返回 `3221225781/0xC0000135`，无输出且未创建数据目录。smoke和失败对照的二进制位置/参数并不完全相同，PATH过滤尚非已证根因。
- 单一问题：移除Node安装目录PATH是否导致相同PG二进制的initdb失败？
- 实施：在P25的 `compare_parent_pg.py` 复用同一父包PG payload解包目录和同一 `initdb.exe`，完全相同P25命令参数，创建两个隔离D盘数据路径；分别以job原PATH及仅移除Node目录的PATH运行。两臂记录固定字段：过滤项计数、退出码、stdout/stderr字节数、PG_VERSION是否出现；不打印环境、错误原文或数据库内容。保持后续P25 harness行为不变。
- 独立验收：Hosted P25 job中两探针都运行并上传摘要。仅原PATH失败/过滤PATH成功，才支持PATH过滤与失败相关；两者同结果则转查二进制装载位置；两者都成功则检查P25 harness差异。P25 HTTP/Edge仍须实际通过。
- 安全与回滚：仅D盘RUNNER_TEMP合成临时库，不启动服务、不做业务写入、不调用外部API/插件、不用客户数据/秘密。本机不运行程序。回滚仅还原比较脚本及记录。
- Secret检查：不新增密钥，不打印PATH或任意环境变量值。
- 决定：PASS_WITH_LIMITATION，可实施该受限Hosted探针；P25继续BLOCKED_DIAGNOSTIC。


## PATH双臂 Hosted 结果与下一项重新检查（run 42162415883）

原PATH和Node过滤PATH在同一解包initdb.exe、相同P25参数下均返回 `0xC0000135`、没有输出或PG_VERSION；PATH过滤不是充分根因。既有完整父包smoke成功，但源码确认它使用不同的initdb命令profile。下一项编码前检查因此只比较两个已存在profile：P25 profile与父包smoke profile；固定同一二进制路径、原PATH、Runner-temp父目录，只改变profile（用户和flags作为一个参数组），不启动server。P25原流程保持不变。
