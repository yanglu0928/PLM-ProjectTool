# P07-A06-P02 实际最终核验故障与回滚

2026-09-27；0.1.0.dev0；Windows11/Python3.13.15/隔离PostgreSQL18；输入cdb9f2e/Schema0049，不改生产源码。

每类change、自reset先以实际Service写入Credential/User/Session/Audit/immutable first/Receipt，再在真实final证明成功后注入同事务数据故障：

|真实故障|实际最终核验|Service结果|
|---|---|---|
|插入新Credential版本额外活Session|False|AUTH_ACCESS_DENIED|
|插入同changed_at/reason额外已撤Session导致count错配|False|AUTH_ACCESS_DENIED|
|当前User lock_version再增1|False|AUTH_ACCESS_DENIED|
|SELECT 1/0实际SQLSTATE22012，原事务已中止|固定Access不可用错误|对应change/reset不可用|

两路径共八故障均九表SELECT *全行前后相等，旧Session实际validate仍有效、caller bytearray全部擦除；完整事务含注入行全部回滚，触发器没有禁用，没有模拟成功SQL。每次actual final正向控制在注入前True，注入后再次执行同实际函数；这是精确被测事实，不代表所有字段错配已覆盖。

两路径随后普通真实Service成功提交、新Credential2与新密码Session2可用。原完整双Scope空及260行实际文件发布回归通过，独立入口exit0；由原fixture创建并清理唯一隔离DB/临时文件/合成Vault，不访问生产。新增Admin角色供给TEST_ONLY，License合成，不能作为正式信任材料验收。

本批无Migration/API/权限/算法/依赖/生产升级变化，兼容0049；回滚撤验证入口。unit最近1470无失败/2跳过为P01结果，本批未重跑；coverage/wheel/性能未跑，原85.676%及Hash保持。下一P03完整unit+原四链+本新链同轮覆盖，保完整范围/旧runtime；90%/性能CR008 FAIL/默认4/正式trust/目标环境/安装升级/UI/UAT/Gate3与可用程序包仍待。
