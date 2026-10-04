# AUT-04-A12-P06-A04-P02-A04 本人change历史KDF事务外

## 编码前检查

- Phase2/Auth；单一问题：change历史双密码KDF移出global锁。输入冻结64cdf09/CR007/008/0049，readonly hint与exact detached source及reset编排已验并同步bc1e051。
- 当前User普通或受限Session/CSRF短UOW取scope/hint/full first精确BEFORE/AFTER源；miss才取current source。准备结束后固定4-slot/5秒，history真实两KDF，不做current verify/new hash，不持有DB锁。
- 原global写UOW新身份、同scope/reserve、full first与两个fresh实际source再核、末次身份检查保留；fresh保原current true/credential ID-version-flag/root/allSession/Audit/first/receipt/intentional final原子链。
- miss后reserve发现history则退出写UOW最多一次重新准备；无锁内KDF、无限循环、旧Session授权。实际并发自身change会撤旧Session，失效请求应拒绝，不为重放绕过current身份。current false只拒fresh，不能误拒已完成历史。
- 无Migration/API/依赖/权限/算法变更，无Admin/License门槛；构造replay_verifier参数保兼容，detached实际校验通过Result端口。
- 风险：first/role错配、准备后logout/renew/disable/reset/current凭据变化、race、slot/两secret擦除；单元、实际PG两KDF独立锁/current变更/真实历史after later凭据、旧原子/Windows两链/20并发全验。
- 回滚恢复原串行history、保所有历史与0049；原性能FAIL不隐藏。CR008/Gate仍OPEN，验收待执行，不把内部接口通过当完整程序包。

## 已执行功能验证

- 1419 tests无失败/2既有跳过。新history五项unit涵盖事务外两KDF、fresh双来源再核、各密码false/非bool/异常、current false+miss竞争不得提前invalid、重试最多一次、当前身份/source失效拒绝、两缓冲擦除。
- 实际PG真实change1→2→later3后，用最新普通有效Session和原双密码重放；独立连接在两个真实固定Scrypt时可取global/User/Session锁，history不做current KDF/new hash。任一原密码差异conflict，九表不写。
- 第二历史KDF期间actual logout/renew/disable/laterchange4使本请求AUTH_ACCESS_DENIED，九表仅外部操作变化。合成License disabled仍正常返回原first，无新License门槛。
- 准备miss后，另一次actual change提交first并撤销旧Session：外层安全拒绝、不额外写；真实新login后原Key/双密码恢复原first。原change原子全Session撤销/SQL-Port-precommit回滚/丢确认/同不同Key/受限转正常及publication回归通过。
- 开发wheel751532 bytes/SHA256 `709f6671dcbe3ec4a2f4c9927e75d910fd2fd9a256793c1bd33c6a62fd24d5ef`通过；不是安装包、不上传；无Migration/API/依赖/生产升级，0049兼容。
- Windows change A04及reset A07两专门链本轮依次实际运行exit0：普通/受限真实HTTP登录改密、Cookie清理/旧Session拒绝/新login历史恢复、reset强ETag/self/丢回执恢复、默认模式/只读/构造故障/缺正式信任源均通过。正向License合成，正式安全/三平台/网络TLS/持续负载/覆盖率/包/Gate仍待。

## 20并发实际结果

- Windows actual factory/PG18/真实Scrypt/合成信任/进程内ASGI，生产参数4slots不变。五组均20/20 200：GET P95 138.900ms，fresh reset1642.030ms，fresh change3157.216ms，history reset1650.695ms，history change3220.477ms（原8114.279ms/14成功6锁超时）。
- fresh与history实际SQL错误全部空；20+20 first及最新Credential3/旧Session失效一致，history两组九表完整快照无写/原first保持。reset/change slot活动峰值4/结束0/等待超时0，process peak working set673980416 bytes（不是整机/PG总内存或发行最低配置）。
- 本轮history锁超时功能故障已消除，但四普通写/历史P95都超过1秒；脚本真实exit1 FAIL，性能标准不变。旧state/publication通过不抵消失败，CR008/Gate3保持开放。
