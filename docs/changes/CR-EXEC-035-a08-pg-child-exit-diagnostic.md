# CR-EXEC-035：SUR-07-A08 PG 子进程退出码安全诊断

日期：2026-11-07  
状态：实施前记录；A08 未通过。

## 证据

Hosted run [42269084207](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42269084207) 的A08已经通过candidate staging、D盘边界与PLM_P51_TEMP_ROOT所有权检查，并进入包内平台写入验收。失败调用帧：verify.py:301 → smoke_current_app_packaged_https.py:226 → smoke_packaged_platform_write_https.py:357 → smoke_packaged_pg18_migration.py:66。第357行执行pg/bin/initdb.exe；helper的 _run 在第66行因子进程非零返回而抛RuntimeError。

helper异常文本按源码包含可控执行文件basename、数字exit code和截断的stdout/stderr。A08当前外层诊断为了保护信息不输出该消息，因此具体子进程退出码未知。原始输出按既定策略未上传并已清理。

## 单点修正

仅增强A08 verify.py与Workflow包装器：从异常消息中仅用固定格式提取命令basename和有符号整数exit code；命令名仅允许PG helper固定列表（initdb.exe、pg_ctl.exe、psql.exe等）。不提取或记录 stdout、stderr、异常消息、完整路径、环境、请求/响应数据。无匹配则输出child=none/child_exit=none。既有阶段、最多8个净化basename:line、D盘staging/PG边界和所有业务标记保持。

不改产品逻辑、PG二进制、验收门槛或数据库设计。

## 风险、回滚与验证

即使命令和退出码仍不足解释根因，也可避免危险正文外泄；如有需要再另行按证据设计固定词条分类。回滚仅删除该两字段解析。完整 Hosted Windows Server 2025 D盘运行仍须通过全部既有步骤/标记并清理exact owned root。只用合成数据，不外发客户内容或调用外部AI。


## 实施记录

已按CR-EXEC-035在A08 verify.py中匹配helper固定错误前缀，只提取命令basename与有符号整数退出码并将命令限制在PG/python白名单；未读取输出段用于摘要，Workflow regex同步约束字段。实施过程静态复核发现一次正则转义写法不匹配十进制数字，已在本提交前修正为Python raw regex的数字类写法。完整Hosted复验待GitHub Actions。


## Hosted 结果与下一隔离探针（CR-EXEC-036）

run 42272810533 在同run A17成功的同时，A08通过候选解包，随后target layout内initdb.exe以3221225781/0xC0000135退出。该状态说明Windows loader报告DLL缺失，但没有指出具体DLL。不能基于异常推断产品包装缺。下一步在完整校验的stage二进制路径执行无写入的 --version 探针，捕获并丢弃所有输出，仅保留整数退出码；再与target layout测试比较。若stage probe通过，则按A08与A17 env/layout差异继续分析。
