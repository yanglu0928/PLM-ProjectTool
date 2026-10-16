# P07-A05-P01 适配器输入拒绝验收

2026-09-27；0.1.0.dev0；Windows11/Python3.13.15，生产6db71f5/Schema0049未改。

新增4个参数化unit方法：reset零/字符串User ID、无Actor、bool/负/上限expected_version与未知Hash DTO（7类）；change未知proof或Hash类型（3类）；change credential_version或lock_version=BIGINT最大值（2类）；两Repo分别拒绝参数p=True、弱n与空dict（6组）。每组通过明确_session Spy断言数据库会话未获得，因此没有SQL成功或客户数据写入。

Hash正向控制是固定SCRYPT参数与规范编码的合成元数据，目的仅是到达相应版本检查，不是实际password认证/凭据/授权；没有生成或写入生产Credential。错误参数沿既有_validate_hash拒绝，不修改算法/参数/生产代码。

完整unit/contract1460 tests，failures0/errors0/skipped2（既有符号链接账户权限场景），exit0。真实SQL正向/原子/rollback/current权限仍由P07A04P02同轮四PG/Windows报告支持，本批没有重跑；coverage/wheel未跑，不推算新覆盖率，最近密码82.432%分支/全Auth74.743%保持。原JSON/Hash历史不覆盖，不提交runtime/日志/客户资料/Secrets。

无Migration/API/权限/算法/依赖或生产升级。下一A05P02 current proof/transaction输入、安全异常拒绝，然后统一真实PG覆盖复验；90%/性能CR008 FAIL、默认4、正式trust/服务账户/三平台/安装升级/UAT/Gate3及可用包未完成。
