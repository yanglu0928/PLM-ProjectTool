# AUT-04-A12-P02 受限Session公开身份投影

## 编码前检查

Phase2/Gate3未通过；WBS A12P02；输入64cdf09/API02、CR-AUT007，前置9d6fb82 currentFact/五proof真实验证。
模块Auth；实体User/Session/current Credential；API登录/Session GET/续期保持路径及Cookie，仅加password_change_required boolean。
权限：Windows真实SQLview按Token/currentFact精确绑定，required=true不调用项目reader并输出NONE/空项目；身份不提供普通授权。
验收：普通兼容、新flag严格boolean/无Hash，实际受限Scrypt登录/GET/续期最小投影与普通权限拒绝；坏Token/旧Credential/投影故障拒绝；原Windows回归。
风险：改密接口还未开放；不能称完整安全流程。Legacy opt-in view仅resolve仍保留测试/外部适配兼容，生产SQLview必须具有真实resolve_for_session且不可fallback。

DEC-20260927-309：新增精确Token投影调用Port，Windows现有SQLview实现当前fact/共享锁，再读取同UOWUser与当前Credential；required=true不读项目，DTO防泄露管理角色/项目。正常字段保留加false。旧resolve兼容，生产精确Port失败不得回退；无Schema/依赖，撤新入口保历史。

## 实施和验证

2026-09-27 / 0.1.0.dev0 / WINDOWS_RESTRICTED_SESSION_PROJECTION_VERIFIED。

- LoginSessionView增加严格password_change_required boolean；true时即使DTO携带角色/项目，公开投影固定NONE/空项目，不泄露凭据。SqlAlchemySessionView在同UOW真实Token事实/共享锁绑定当前ID/version/flag，再读User；true直接返回，不调用Project Port。
- login/Session GET/renew复用resolve_session_view；Windows实际SQL源走resolve_for_session，异常不回退。legacy opt-in仅resolve适配仍兼容，不作为Windows安全来源。既有路径、Cookie、SessionView字段保留，新字段为非破坏增量。
- 全后端1348 tests无失败（2既有Windows权限跳过），新增DTO受限投影/非布尔拒绝；普通投影期望加false，不放宽其字段断言。
- `validation/aut-04-a12-p02-restricted-session-view/verify.py`实际Windows Factory/PG18真Scrypt登录：普通false；TEST_ONLY追加Credential2 true并赋Admin后旧Token401，新登录/GET/renew均true/NONE/空项目，Admin业务GET404；ForbiddenProjects reader实际不会被调用。错User/坏Token/旧凭据投影拒绝；真实SQL源故障503且旧resolve故障桩未被用作回退；受限退出成功清Cookie。
- 原Windows状态完整矩阵、五构造故障dispose/readonly-default拒绝及原双Scope文件发布回归通过。正向信任合成，Credential追加/角色均明确TEST_ONLY，不是实际reset/change服务。
- 保留冻结续期只轮换受限身份，SESSION_RENEW加入严格能力白名单，不改must_change标志、不授普通业务权限，记录CR-AUT007与DEC309。改密接口尚未实现，不声称当前用户已可完成强制改密。
- 开发wheel721845 bytes，SHA256 `18e2241a3ba18705fda1d8fd0a82d9f28e6e8723181017dcf870c3a44bf12abd`，仅构建检查，不是安装包，不提交临时wheel或密码/测试数据。

无Migration/依赖/生产升级，兼容0047；回滚撤新入口保历史，不开放reset绕过限制。正式信任/并发性能/三平台/UI/完整密码流程/包/Gate未通过。下一A12P03：密码变更不可变首结果与前后Credential绑定前置及Schema；随后原子真密码校验/全旧会话失效/当前认证重放，不能通过失效旧Session授予新写权限。
