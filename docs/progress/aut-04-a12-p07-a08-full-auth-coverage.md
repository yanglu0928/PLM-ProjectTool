# AUT-04-A12-P07-A08 完整Auth实际覆盖

2026-09-27；Phase2；MEASURED_INCOMPLETE。输入1a88d8f/冻结64cdf09/Schema0049，前置P07A07密码范围通过，完整Auth仍78.239%。本项仅整合已有隔离验证入口，不改生产实体/API/权限/Schema/依赖。

验收：完整unit、原五密码实际链及六非密码实际链（Windows user detail/list/create/name/state、实际Vault login/GET/renew/logout）同轮覆盖；完整Auth/21密码文件/工厂分别展示，不缩文件或分母、不新增排除。原程序仅据密码范围设置退出码，本新增入口还必须独立要求完整Auth行与分支>=90%，否则exit1，不能只以继承退出0为安全通过。

风险：旧验证入口可能因新基线不兼容，需要按证据修正验证，而不是修改生产绕过安全；正式trust仍合成/供给缺项，Windows login专属随机TEST凭据与唯一临时DB独立清理。禁止真实秘密/客户数据外发或生产数据库操作。保旧raw/new独立runtime，撤入口即可回滚，无升级；性能CR008/Gate/包未完成。

结果：完整1470unit无失败/2既有跳过，11真实入口全部通过；全Auth3168/3364行94.174%、792/988分支80.162%，密码1031/1047行98.472%/350/384分支91.146%，工厂362/369行8/10分支。完整Auth门槛输出False/exit1，不能用综合90.993%或密码通过关闭安全。原Hash不覆、新Hashf6a57106…见report。下一A09 Session Service时间/结果/异常防御与无写边界，再统一完整实测；生产/Schema/API/依赖未改，wheel/性能未跑。
