# PLG-03-A01 PluginExecution 持久化基础验收结果

- 日期：2026-11-05
- 结论：PASS_SCOPE_LIMITED
- Hosted workflow：[41974625395](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41974625395)
- Change Request：[CR-PLG-014](../changes/CR-PLG-014-plugin-execution-persistence.md)

## 验收证据

隔离 PostgreSQL 18.6 verifier报告 `PASS_SCOPE_LIMITED`。从旧head `20261104_0230` 升级至 `20261105_0231` 时包含一条合成既有 Job 行；升级前后三张新增表状态、旧schema表数与既有行均按断言保持。验证覆盖 Execution/Job/Project/OutputRequest/Context/Installation/Manifest operation 固定关系、result-file Project/FileObject/hash/path约束、state-event同Project与状态码约束、Owner写关闭、append-only和TRUNCATE拒绝、空库downgrade/reupgrade，以及存在Execution历史时拒绝downgrade并保留数据/head。

同一父包PG18 smoke成功，后端全量测试及wheel、前端测试/build、PG sidecar、A17/A34/A35/A50等成功。结果通过run中的专用PLG-03 marker和PG verifier JSON，不依赖状态推断。

## 限制和未通过项

同run P25 Windows Server 2025专项在 `initdb.exe` 以 `0xC0000135` 退出，未完成HTTP/Edge；因此该run总体不是全绿。插件没有被执行、没有文件生成、没有生产写Owner/API、没有外部API或客户数据。此结果仅表示PluginExecution持久化模式在指定PG18合成验收范围内通过，不代表插件执行安全、Windows 11设备、Pilot、Gate或正式Release通过。

## 运行位置与安全检查

验证由GitHub hosted Windows runner执行，临时目录为D:。用户本机与C:均未运行项目代码或测试。变更提交内容为源代码、验证器及文档；无Key、密码、License私钥、客户数据、日志、临时运行产物或本机环境文件。
