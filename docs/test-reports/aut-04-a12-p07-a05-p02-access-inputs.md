# P07-A05-P02 授权输入与事务异常

2026-09-27；0.1.0.dev0；Windows11/Python3.13.15。输入a2801b0，生产源码与Schema0049未改变。

新增7个参数化测试方法：reset/change各8种非法token/CSRF/time，不取得数据库会话或调用base prove；两个适配器事务异常只呈现固定错误；change非法source proof/final proof/trace/时间在SQL前拒绝；未知source/错误password类型/空或1025字节memoryview/非法Hash不调用verifier；verifier返回None/1或抛异常固定拒绝，True/False原样保留；Session issue未知proof、错误password类型及长度不读transaction.session；缺失/抛异常/错误Session类型/真实未开始事务Session均拒绝且不调用verifier。

完整1467测试，failures0/errors0/skipped2（既有账户符号链接权限场景），exit0。无成功SQL模拟、无客户数据/秘密外发；真实Session()无数据库连接，仅验证未开始事务的拒绝。固定规范Hash用于合同路径可达控制，不是实际认证结果。底层异常内部可保留供调试，不将异常链清除与对外固定错误混淆。

无生产/Migration/API/权限/依赖/算法变更，兼容0049，无升级需求；回滚撤新增测试。coverage/四PG/wheel本批未跑，保留最近密码82.432%分支/全Auth74.743%及原JSON/Hash。下一统一真实覆盖复验，90%门槛、性能CR008 FAIL、默认4、正式trust/环境/安装升级/UAT/Gate3/可用程序包未完成。
