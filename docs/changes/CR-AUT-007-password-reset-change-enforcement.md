# CR-AUT-007 密码重置、强制改密与当前会话限制

日期2026-09-27；版本0.1.0.dev0；状态RESTRICTED_SESSION_PROJECTION_VERIFIED_PASSWORD_FLOW_PENDING。

P03A03进展：真实0048first Repository及前后Credential精确历史Scrypt来源通过；record服务器受理时间/固定profile、双密码匹配差异/伪造first/KDF异常、laterCredential历史保持、坏profile与实际caller写后回滚已PG验证，1359 tests无失败（2既有跳过）、原发布回归通过。转换仅TEST_ONLY，生产当前认证/原子Application和HTTP仍待，见P03A03progress；下一A12P04原子change。

P03A02进展：新增0048/ORM thirteen-field改密first、前后Credential/User/self Audit/time/撤销Session计数源与历史保护；空有数据升降往返/ORM/坏源及must-change=true拒绝/回滚/非空down实际验证通过，1357 tests无失败（2既有跳过）、四旧Schema/Windows受限投影/原发布回归通过。0001～0047保留，无生产迁移或改密公开入口；Application/真实密码来源及原子幂等仍待，见Schema增量及P03A02progress。

P03A01进展：严格不可变change first DTO和两项密码source proof已通过9新增unit/1357总测试（2既有跳过）及真实内存Scrypt匹配/差异验证；只公开credential_version，无快速摘要/明文持久化或新Key。当前未有first Schema/真实Repository/原子change服务，故CR整体不关闭；见P03A01progress。下一Schema/来源验证，完整Scope不缩成纯DTO。

P02当前状态：Windows真实Token绑定currentFact投影接login/session GET/renew；受限返回password_change_required=true、NONE和空项目，不查询项目reader；旧Token/错User拒绝，生产精确源失败503不回退。保留原续期功能仅轮换受限身份，不能解除改密限制或生成普通业务权限（DEC309补充）；能力规则同步SESSION_RENEW白名单。完整改密/reset路径仍待。
授权依据：用户持续授权；保留冻结64cdf09/DM02/API02与原0001～0047，不静默替换原基线。

## 来源、冲突及实际证据

- P01已新增严格current SessionCredentialFact及精确正常Credential谓词接五原Auth业务proof，实际must-change全部拒绝/七表不变、后来正常Credential新Session恢复而旧Session失效；1346 tests无失败（2既有跳过），Windows状态和原发布回归通过。公开login/session最小投影及完整改密/reset尚未实现；见P01progress。以下调查原证据对应e8349c5，原复现脚本已改为反回归，不抹去历史缺口。

- 冻结AUTH_USER_RESET_PASSWORD要求当前Admin、Session/License/CSRF、幂等Key、强If-Match及Audit；输入temporary_password write-only、must_change_password=true，响应/收据不回显密码。AUTH_PASSWORD_CHANGE要求当前密码/新密码、Session/CSRF、Key和Audit，换密使旧凭据会话失效。
- 当前PasswordCredential已有must_change_password列，但真实SqlAlchemyPasswordIssueAccess未读它；SessionRepository/SessionService和原Admin proof也未限制该标志。没有reset/change Application或HTTP。
- `validation/aut-04-a12-reset-preconditions/verify.py`已实际隔离PG18复现：新User原Credential1保留，显式TEST_ONLY追加Credential2 must_change_password=true并赋Admin，真实Scrypt校验签发Session、当前Session校验成功、原Admin-CSRF proof仍授予身份。该输出是CONFIRMED GAP，不是安全PASS。无生产数据或信任材料操作；原发布回归通过不能抵消该缺口。
- 现有createfirst与statefirst均不能证明reset请求密码一致性或原凭据版本响应；不能引用当前User或把临时密码快速摘要持久化冒充合格幂等。

## 比较与选择

1. 只写must_change=true然后复用普通登录：已证实不限制业务，拒绝。
2. 拒绝临时密码登录且无改密路径：用户无法完成首次改密，不作为最终方案。
3. 临时凭据创建受限Session，仅允许最小Session身份/强制改密/退出；业务权限重新查询真实当前Credential标志并拒绝；成功换密追加正常凭据并失效旧Session，重新登录正常使用。选择，沿原Cookie/CSRF/密码算法与统一Auth来源，不新增认证机制或缓存授权。

## 设计增量与实施顺序

- A12-P01先补当前凭据强制改密事实读取及受限Session授权策略。标志来自User activeCredential ID/User/version的精确当前源；坏源安全失败，非客户端或旧Session长期快照。必须覆盖直接Auth部署读写/Project读写/Review入口及任何复用源，不能只在HTTP middleware挡一条路由。
- 保留正常账户行为，限定Session身份投影明确password_change_required；受限投影不枚举项目/管理权限。该字段和专用错误作为可追溯非破坏增量，最终响应合同/实现另单任务验证。普通业务Port不能把受限Session当普通权利凭证。
- 在开放reset前实现当前密码→新密码的实际强制改密路径：真密码核验、追加Credential n+1而不更新历史Hash或must_change标志；current User指针/credential_version/lock_version/Audit/首次结果/receipt原子更新，撤销旧Session；成功后重新登录，不以恢复旧Session替代认证边界轮换。冻结“其他Session撤销”同时旧凭据当前Session亦自然失效，此行为须记录HTTP Cookie和确认恢复策略。
- reset再实现Admin当前权利/强If-Match、固定must_change=true、Scrypt新Credential、全未撤销Session撤销、User状态/角色/身份不变；允许DISABLED保持DISABLED，不能顺带启用。目标与调用者同一时需严密本次换凭据/撤销专用末核，不能无条件跳过最终授权，范围不静默缩成只重置其他人。
- reset owned不可变首次结果绑定原此次新Credential版本、User安全结果、Audit/actor/trace/expected及receipt。非秘密fingerprint只含目标/版本/固定标志；重放用该次不可变Credential真Scrypt校验temporary_password后返回原first，后来再换密不覆写首结果。不持久化明文、可逆密码、快速摘要或额外密码等价物。
- change幂等须证明原请求当前密码与新密码两项一致性；通过首次结果绑定转换前后不可变Credential再真实校验，不把当前最新Credential充当原请求。撤销原调用Session后恢复策略必须仅原Key/原身份严格绑定，不能用失效Session授予新写；具体安全恢复合同先验证后开放。

## 迁移、风险、回滚与验收

本轮只有前置调查/复现/设计，无生产编码或Migration。原credential/Session Schema不改写；结果Schema按后续ORM/Alembic空库与有数据up/down单任务实施。正式升级前备份/维护停写；有不可变历史不得破坏性降级。撤新入口保凭据/结果/Audit/receipt历史；已重置密码不可静默回写旧Hash或复活Session，必要时执行新的可审计重置。

验收需真实Scrypt当前/新密码、强制改密受限登录与所有业务Port零授权、坏源/失密/CSRF/License/版本、全Session撤销与新登录、disabled/自重置/最后Admin可达性、同Key密码差异与并发、后来凭据变化首响应、实际写后/commit确认故障整体回滚或严格原结果恢复、HTTP Cookie/来源/错误无秘密、Windows actualFactory；20并发及三平台另验。不得只测试DTO或标志存储便宣称强制改密PASS。

当前reset/change生产入口仍关闭，未完成安全机制，Gate3/安装包不关闭；无需逐项审批，但测试失败必须如实记录。

2026-09-27/P04A01：普通及受限当前身份/真原密码与本次首次变更专用末核已在实际隔离PG验证。末核不是失效Session通用授权，必须在首次执行原UOW提交前精确核原生命周期、实际first/trace和全Session撤销。下一原子Application及当前有效身份历史恢复；TEST_ONLY转换不能关闭本CR或Gate。

2026-09-27/P04A02：内部实际原子change Service已完成PG/Scrypt当前认证、全Session撤销、Audit/first/receipt与末核/commit验证；真实写后及precommit回滚、commit丢确认新认证恢复、同/不同Key竞争与受限源转normal通过。历史重放须重新登录当前有效本人，不能使用旧Session授新写；原请求两密码只与first前后Credential真实KDF比对。公开HTTP/Cookie/Windows组合/reset/发行仍待，CR未关闭。

2026-09-27/P04A03：可选冻结HTTP及Cookie/恢复合同真实PG-ASGI验证通过，见增量合同与progress；默认关闭，Windows实际组合/browser/reset/发行未完成，本CR不关闭。

2026-09-27/P04A04：Windows显式write实际装配及登录/改密/旧Session密码拒绝/新登录、六构造故障安全dispose/关闭模式、正式材料缺失拒绝已验证；正向信任为合成，不是正式发行。reset仍未实现；下一原reset首次响应来源及Schema前置，整体CR/Gate不关闭。

P05A01实施前设计：reset first15字段记录result/user/actor/old-new Credential ID/version/原expected User version与new version/原target_state/Audit/trace/全Session撤销数/changedAt/acceptedAt。disabled保原状态、count可0；self目标允许但专用首次末核另验。重放仍须当前正常Admin/License/CSRF，原临时密码比对当次newCredential真Scrypt；自reset的受限临时登录先完成change恢复正常Admin，之后原reset Key可历史恢复。无密码快速摘要/新钥匙，原freeze保留，来源Schema/迁移与完整命令另步骤，不缩范围或提前关闭CR。

2026-09-27/P05A01：纯first/proof实现与实际内存Scrypt单密码历史契约已验，1374后端测试无失败（2跳过）；source Schema设计标未实施，当前0048不变。非PG reset Repository/原子重置/当前Admin授权/HTTP证明，下一来源Schema与真实验证；整体CR仍未完成。

2026-09-27/P05A02：0049/ORM独立15字段及完整DB source/immutability/down保护已真实隔离验收。空有数据/旧十三表保持、disabled0/self范围、坏源/Audit/时间/count/受限actor拒绝、实际回滚/并发及旧链通过，原0001～0048保留，无生产迁移。TEST_ONLY转换非真密码/当前认证或原子reset，下一实际Repository/Scrypt source；CR/Gate未关闭。

2026-09-27/P05A03：实际first Repository及当次temporary Credential真实Scrypt source已验，后续真正change到normal3仍原临时密码历史匹配；坏profile/实际合法first后caller故障回滚保原Session。无当前Admin/License/CSRF授权或原子reset/receipt/HTTP证明，下一normal Admin身份及self专用末核与原子Service；CR整体保留。

2026-09-27/P05A04：current normalAdmin-CSRF与首次self reset精确末核已实际PG验证，原生命周期/实际first/原normalCredential/受限新凭据及预期撤销严格绑定；旧及受限Session不授新管理权，actualchange/newlogin恢复Admin。TEST_ONLY重置非完整原子Service/License/If-Match/receipt/唯一Admin/HTTP证明，下一完整命令，不关闭CR/Gate。

2026-09-27/P05A05：实际原子reset命令完成当前Admin-CSRF/合成License前后/target expected/固定true、Credential/root/全Session/Audit/first/receipt及self精确末核；真实同不同Key竞争/回滚/提交恢复、disabled0保状态、明确唯一Admin角色夹具self受限→License-disabled真change→normalAdmin原first恢复通过。真正坏旧profile修复也验证；原freeze与0049保留，无生产迁移。HTTP强If-Match/Cookie/Windows/正式License/性能/发行待，不关闭CR/Gate。

2026-09-27/P05A06：可选冻结reset HTTP真实PG/Scrypt-ASGI通过，强If-Match/严格JSON/来源/Session-CSRF-Key、normal/disabled/self及历史User ETag、Audit回滚与self提交后末读503正常新认证原Key恢复。1388 tests无失败（2既有跳过），原发布/wheel通过。无Migration/依赖/生产升级；默认404，Windows实际装配下一项。合成信任不是正式License验收，完整CR/Gate保留。

2026-09-27/P05A07：仅Windows显式write实际装配reset链及完整HTTP矩阵/真实登录强制改密链验证通过；六新增构造fault实际到达/dispose一次/九表无写、readonly405/default-login404/缺正式材料拒绝，旧状态/发布回归及1388无失败（2既有跳过）/wheel通过。无Migration/依赖/生产升级；正向trust合成，性能/完整安全验收/三平台/安装包未完成，下一汇总缺项及20并发性能前置，不关闭CR/Gate。
