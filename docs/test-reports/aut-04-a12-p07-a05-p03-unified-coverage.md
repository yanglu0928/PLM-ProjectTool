# P07-A05-P03 统一实际覆盖结果

2026-09-27；0.1.0.dev0；Windows11/Python3.13.15；coverage7.13.5（本地验证工具，不是生产依赖），输入aa9b5d0/Schema0049。

同轮完整1467unit/contract：failures0/errors0/skipped2，既有符号链接权限跳过保持。四实际入口全部通过：P06A04P02A03 reset history+atomic，P06A04P02A04 change history+atomic，P05A07 Windows reset，P04A04 Windows change；沿用真实隔离PG、SCRYPT与Windows显式工厂及原发布回归。合成信任源不冒充正式安全材料。

|测量范围|行|分支|结论|
|---|---|---|---|
|原完整21密码文件含SCRYPT/进程预算|1003/1017，98.623%|317/370，85.676%|未达到90%分支|
|完整Auth|3091/3334，92.711%|740/974，75.975%|未达到90%分支|
|完整Windows production_login工厂单列|362/369，98.103%|8/10，80%|未完整覆盖|

密码综合95.169%不覆盖分支缺口；exit1为门槛未达，不是unit/集成失败。不缩减分母、不添加pragma/omit、不把0分支文件称为分支100%，原协议省略行的既有测量配置未改。

原始证据（忽略目录，不提交）：`.poc-runtime/auth-security-adapter-defensive-coverage/coverage.json`；SHA256 `45c4d14a92034d373a8d566eb17fe2bbbdb8e2da5f9041c77aefb07576efa98d`。前轮service-defensive JSON与Hash e81793fc…保留未覆盖。本轮无生产源码/Schema/API/依赖变化，wheel/性能/生产升级未跑。

未覆盖实际范围包括Service异常清理边、reset非bool历史核验、两个Result来源/record异常、当前Credential源异常与current-final错配/live Session/count拒绝、issue未找到匹配Credential等。测量缺边不是不可达证明，不以伪造成功SQL提高覆盖。

下一P07A06：结果来源输入/固定异常防御，然后真实PG current-final与事务故障证据；按新实际测量保留完整范围。性能CR008 OPEN/FAIL、默认4、正式trust/目标账户/环境/安装升级/UI/UAT/Gate3与可用包仍待，用户持续授权不豁免这些事实。
