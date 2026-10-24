# AUT-04-A12-P05-A05 原子管理员reset

编码前检查：Phase2/Gate3未通过；基线64cdf09/API02/CR-AUT007/0049，前置b99004c current Admin及self末核、真实first/Scrypt source已验。仅Auth原子Application/Repository，公共Audit/receipt/License，暂不HTTP。当前normal Admin-CSRF、License前后、target expected version（冻结强If-Match内部值），固定must_change_password=true；disabled状态保持，self不禁。

DEC-20260927-321：同部署锁5s后当前proof→reserve（actor/target/expected/true非秘密fingerprint）→Scrypt→append Credential/root version/全Session→Audit/first/receipt→License与普通Admin或self专用末核→commit；replay必须当前正常Admin与原临时密码历史source，原expected及first保存，不以最新Credential替代。self未知提交只能临时登录/change恢复normal Admin后原Key恢复；License无效仍能执行已有change，不能以受限Admin授新管理写。密码finally擦除。无Schema/API/依赖变化。

验收：真PG/Scrypt normal/disabled0与有会话/self/最后Admin可达性，强expected/flag/角色/License/CSRF/差异拒绝九表无写；同Key单first/不同Key版本竞争，later实际change历史重放、全部写阶段/commit前及确认后故障回滚或严格恢复；self故障末核不跳过。回滚撤未挂入口保历史，不能静默回写密码/启用目标/复活旧Session；HTTP/Windows/UI/性能/三平台/正式信任/包/Gate仍待。

## 实施与结果

新增PasswordResetService/ResetPassword及caller-UOW Repository；新Credential strict Scrypt/must-change=true，root仅指针与Credential/User版本/更新人时间变化，全未撤销Session含expired统一PASSWORD_RESET；Audit/first/receipt同事务与普通或self末核。历史重放校验原target/expected/true fingerprint及当次临时密码KDF，当前Admin/License前后仍必须有效，密码finally擦除。

4新unit/1384 tests无失败（2既有跳过）。实际隔离PG/Scrypt版本/flag/CSRF/NONE/unknown目标/License拒绝九表不变；同Key两线程同first/单转换，三Session含expired撤销，临时登录受限不能管理，实际change到normal3后历史first仍版本2/原Key密码差异冲突。不同Key同expected两线程仅一版本赢家，另一CONFLICT_VERSION。

四实际Port postwrite（Repository/Audit/first/receipt），三实际SQL阶段（Credential INSERT/User UPDATE/Session UPDATE）、precommit、末License与事务内真实角色撤销均九表回滚、原Session保留。实际commit后丢确认，未误判回滚，用仍有效其他Admin原Key恢复。disabled通过已有真实状态Service停用后reset维持DISABLED/count0且临时密码不能登录。

明确TEST_ONLY坏旧profile来源经真正reset修复，新Scrypt凭据可真实登录；首次测试误读IssuedSession无credential_version，改由真实sessions.validate核version后完整复跑通过，生产未放宽。明确TEST_ONLY仅留一名Admin角色夹具：self专用末核实际true后强制false全回滚，真实self commit后丢确认/旧及受限Session原Key均无新管理权；真正change在合成License guard禁用时仍可恢复normal3，恢复guard后新正常Admin原reset Key/临时密码恢复首版本2，九表不变，最后恢复原角色夹具。

原双Scope发布回归通过。开发wheel747290 bytes，SHA256 `12f5151e8702457a1e2bd0df8394937572576307922d162ef27590df20d1cd65`，非安装包。兼容0049，无Migration/API/依赖/生产升级；撤未挂Service保历史，已重置不可回写旧Hash/复活Session。

内部原子命令PASS，License正向/撤销guard为明确合成，角色与坏profile为TEST_ONLY来源；非正式公钥/目标账户/HTTP If-Match解析/Cookie/Windows/browser/20并发性能/三平台/完整包/Gate证明。下一P05A06可选冻结reset-password POST，严格临时密码true/Session-CSRF-Key/强If-Match/安全版本响应与self Cookie/正常Admin历史恢复；P05A07再实际Windows装配。
