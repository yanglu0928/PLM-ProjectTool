# AUT-04-A12-P04-A02 原子改密服务

## 编码前检查

- 当前Phase：Phase2，Gate3未通过。
- 当前WBS：P04A02，仅内部原子PasswordChangeService，不挂HTTP。
- 输入基线：64cdf09/API02 AUTH_PASSWORD_CHANGE S,C,I,A（无License），CR-AUT007、0048。
- 前置任务：92bce75 当前身份/真原密码/首次专用末核已实际验证，历史双密码来源已验证。
- 模块/实体：Auth User/Credential/Session/first，公共Audit及Platform receipt；无Schema/API/依赖变更。
- 权限：普通或受限有效本人Session-CSRF，无Admin要求。部署锁后当前身份；新Credential normal false，原User身份/状态/角色不改。
- 验收：真实Scrypt当前密码及新登录，全旧Session撤销；Credential/User/Audit/first/receipt同事务；错误及每阶段写后故障回滚、commit确认故障后新有效Session同Key历史双密码恢复；同Key/不同Key竞争与受限改密。
- 风险/回滚：密码Hash仅原不可变Credential，不持久化密码等价摘要；两密码finally擦除。旧Session撤销后不得授新写，竞争输家原Session可能认证失败；须重新登录再恢复。撤未挂入口保历史，不回写旧密码或复活会话。完整HTTP/性能/三平台/发行仍待。

DEC-20260927-314：receipt scope绑定当前本人/固定V1_AUTH_PASSWORD_CHANGE，非秘密fingerprint仅request_schema；重放用first绑定原前后Credential真实KDF两密码校验，最终再核当前有效proof。首次专用末核在commit前，仅精确本次预期变更。No License按冻结合同，不引入If-Match。

## 实施与验证

新增内部Service及caller-UOW Repository；完整执行当前认证→reserve→真原密码→Scrypt→Credential/User/全Session→Audit/first/receipt→专用末核→commit。未知错误静态拒绝，两密码finally擦除；重放不提交新事务写入，历史密码校验后再核当前有效身份。

1365 tests无失败（2既有跳过），新增4unit覆盖输入/密码擦除/锁严格True/异常与无身份不Hash。实际隔离PG18/Scrypt普通NONE账户转换，三旧Session含已过期全部撤销、新密码登录、旧Session拒绝且八表不变；当前有效新Session原Key重放及后来Credential变化仍原first；差异密码/CSRF/错误原密码无写。

实际五Port写后注错（Repository/Audit/first/receipt/final），及SQL Credential INSERT/User UPDATE/Session UPDATE各执行后注错、commit前异常均八表回滚；每注错点明确到达。真实commit后丢确认，新密码登录后原Key恢复，未猜失败或盲用失效Session。两线程同Key及不同Key各唯一转换，原Session输家AUTH_ACCESS_DENIED，新认证可恢复胜者first。TEST_ONLY追加受限Credential来源后，真正Service转换为normal Credential且新登录正常；此夹具不证明管理员reset已实现。

原双Scope文件发布回归通过。开发wheel733922 bytes，SHA256 `527a070703ce48fd71e2ec5ab25c917e45f04aa9318f0f7e0fc37066c9e2c384`，不是可安装发行包。无Migration/API/依赖/生产升级，兼容0048；回滚撤未挂入口保所有历史。

内部验收PASS；HTTP/Cookie/Windows组合/20并发及性能/三平台/正式来源/完整包/Gate未通过。下一AUT-04-A12-P04-A03：可选冻结password:change POST、成功清旧Cookie与503确认后新登录同Key恢复合同，不公开reset或扩大业务权限。
