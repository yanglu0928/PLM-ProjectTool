# AUT-04-A12-P07-A03 HTTP异常防御验收

2026-09-27；0.1.0.dev0；Windows11/Python3.13.15/coverage7.13.5；输入fc1ed2a及P07A02原覆盖，Schema0049，生产源码未改。

新增8个parameterized测试方法，覆盖两个接口缺依赖、初始principal None/未知对象/零UUID/字符串UUID、初始安全与未知异常、结果错User/Actor/原版本/被篡改DTO、未知写异常、postwrite未知对象/错用户/非过期Session错误/安全与未知异常、确认过期清Cookie与有效Session保Cookie、错误媒体类型和零目标。写后各路径secret buffer擦除、不回显private错误/正文，不对未知Session猜测清Cookie。过期Cookie明确max-age=0、secure、httponly、samesite=lax、path=/。

这些是HTTP Port故障替身测试，**不冒充数据库提交或授权证据**；可信当前角色/真实事务/回滚/丢回执/历史权限依据同轮四组实际隔离PG/Windows验证。仅HTTP路由成功数据投影通过不表示业务事实已真实写入。

8项专门测试全部通过；同一coverage再执行完整1441 unit/contract无失败/errors0，2既有跳过，并实际完成reset-history+原atomic、change-history+原atomic、Windows reset、Windows password-change四入口，均断言通过，包含原Windows状态/双Scope发布回归。正向信任材料明确synthetic，不涉及客户数据外发或正式生产操作。

同一21密码文件/全Auth/工厂范围、不增加omit/pragma、不删除源码安全路径。与A02比较，仅两个API增加命中，其他密码文件计数保持，完整文件分母见A02报告。

|范围|行|分支|结论|
|---|---|---|---|
|password_change HTTP|72/72|22/22|100%/100%，只证明已测分支|
|password_reset HTTP|71/71|28/28|100%/100%，只证明已测分支|
|同一21文件密码全流程|982/1017=96.559%|293/370=79.189%|分支未达90%，整体未通过|
|全Auth|3070/3334=92.082%|716/974=73.511%|分支未达90%，未完成|
|Windows全组合根|362/369|8/10|单列，未称全平台安全PASS|

密码综合91.925%仍不能抵消分支不足；脚本exit1是保留90%验收缺口，测试本身无失败。原JSON另.poc-runtime/auth-security-http-defensive-coverage/coverage.json，SHA256 cf1447b57f8cc952fcdfa959c1aff1c12371ede99fdce724c16a6a8eb383a23f；A01/A02原路径/报告/Hash不覆盖，raw runtime/日志/Secret不提交Git。

下一P07A04按实际剩余分支补Application Service对错误current proof/immutable first/receipt/source/结果与repo返回的拒绝、时间/依赖边界及无额外写/密码擦除；用可信Port替身模拟接口违约，不取代真实PG。真实PG错误边界需另实际执行。当前无生产源码/Migration/API/权限/算法/依赖变化或升级，wheel未跑；默认4/性能CR008 FAIL、正式信任/服务账户/三平台/安装升级/UAT/Gate与可用包未完成。
