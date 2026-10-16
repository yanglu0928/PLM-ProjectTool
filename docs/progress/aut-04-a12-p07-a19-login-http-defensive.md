# P07-A19 Login HTTP防御

2026-09-27编码前检查：Phase2/WBS AUT-04-A12-P07-A19；输入冻结64cdf09/0049/A18/A16全Auth84.717%；前置Login HTTP与真实Windows链已有。仅Auth HTTP输入/来源拒绝与bytearray擦除，无生产/API规则/权限/Schema/算法/依赖变。

验收：三依赖None；非JSON/坏JSON/坏UTF8/错误正文结构或字段类型提前拒绝；孤立Unicode代理项401无Service；ASGI缺client/空host503无Service且已分配buffer清零；Service固定错误/通用异常及投影身份/flag/来源错误不Set-Cookie，已交出bytearray清零。Mock与限定ASGI输入仅HTTP合同，不冒充SQL/真实浏览器；通用异常维持原SYSTEM_INTERNAL，不擅改错误契约。

风险/回滚：新增contract可撤，无升级；完整测试实际跑，coverage/14PG/wheel/性能本批不跑，原raw/Hash/90%与84.717%保持，不推算。生产/正式trust/性能CR008 FAIL/Gate/可用包待。

结果：6新增参数化方法、完整1520unit/contract failures0/errors0/skipped2、exit0。三依赖、六正文、两孤立代理项、两client故障、四Service错误与三投影故障安全拒绝。client故障直接跟踪本路由分配bytearray，已清零；Service/投影后caller持有attempt.password清零，响应无Cookie/令牌/私有详情且no-store。未知Service异常沿原500 SYSTEM_INTERNAL，不改生产规则。仅HTTP合同，不代表Session已经回滚或浏览器/SQL验收；coverage/14PG/wheel/性能本批未跑，原84.717%与Hash保持。下一P07-A20独立User name patch Repository输入/事务拒绝与真实缺行/冲突来源另分项，后完整统一实测。
