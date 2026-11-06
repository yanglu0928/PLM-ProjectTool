# OUT-01-A01-P25 编码前检查：initdb 命令 profile 对照

- 日期：2026-11-06
- 状态：编码前检查通过；Hosted对照候选待实现
- WBS：OUT-01-A01-P25
- 基线：冻结API Contract V1、DB Schema V1、CR-OUT-021。只改诊断比较器/证据，不改产品代码或P25真实Harness参数。
- 证据：run [42162415883](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42162415883) 中同一解包父包initdb.exe、同一P25参数，两种PATH都以 `0xC0000135`失败，原始与过滤PATH结果相同。Node过滤仅移除1项；两臂输出长度为0且无PG_VERSION。同job完整父包PG smoke成功。源码显示该smoke使用不同用户及旗标profile。
- 单一问题：P25使用的命令profile与同job成功smoke的命令profile是否造成差异？
- 实施：在同一个P25 Hosted job、同一父包PG payload解包二进制路径、原始进程PATH和同样D盘runner-temp父级上，分两个独立新数据目录执行两个既有调用profile：P25 profile `--pgdata=... --username=poc_admin --auth=trust --encoding=UTF8 --locale=C`；parent-smoke profile `-D ... -U postgres --auth-local=trust --auth-host=trust --no-locale -E UTF8`。profile整体为一个差异组。两臂均仅执行initdb，不启服务。摘要只写profile固定代号、退出码、stdout/stderr字节数和PG_VERSION布尔，不记录错误原文、PATH值、环境变量或数据库内容。
- 验收/分支：若parent-smoke profile在相同解包路径成功而P25 profile失败，则下一项拆分user与旗标；若两者都失败，则PATH和命令profile均不能解释完整smoke/直接对照差异，转查父包staging路径/组件布局；若两者都成功，则比较P25现有harness其他阶段。
- 安全：仅合成临时D盘目录；无网络/服务/业务写入/客户数据/外部API/插件；Hosted runner结束回收。本机不运行项目代码。
- 风险/回滚：增加两个受限诊断initdb尝试；只改比较器并保留失败目录于一次性runner temp。回滚仅还原诊断代码和追踪文档。
- Secret检查：不记录环境值、错误消息、凭据或库文件。
- 结论：PASS_WITH_LIMITATION，可进入该Hosted对照；P25仍BLOCKED_DIAGNOSTIC。
