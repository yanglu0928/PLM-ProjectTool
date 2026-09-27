# AUT-04-A12-P05-A04 当前Admin及self reset专用末核

编码前检查：Phase2/Gate3未通过；基线64cdf09/API02/CR-AUT007/0049，前置888754f真实reset source已验。Auth当前Admin-CSRF/独立self首次末核Port；复用既有normal当前凭据Admin proof/UserStateActorProof和部署advisory锁5s，非新认证机制，无Schema/API/依赖变化。

DEC-20260927-320：self首次执行只有actual proof/原Credential normal/原Session-CSRF仍在原生命周期，且实际不可变resetfirst/trace/expected自目标全等、当前User身份/角色不变ENABLED Admin、新true Credential与自己changedBy、原Session本次PASSWORD_RESET准确撤销/版本+1/生命周期不改、全Session/count准确才允许commit前末核。失效或受限Session不能prove新管理写，history只能正常Admin重新登录后恢复。License必须由后续Service前后检查，Port不是License授权。保留最后Admin自reset经实际change可恢复，不新增禁止self范围。

验收：真实normal Admin/坏CSRF/NONE拒绝，self同UOW真实first后末核、伪造token/trace/expected/first/Session version/到期/角色名变化拒绝，旧及受限Admin无新权，actualchange恢复normal Admin。source回滚回归保留。测试转换仍TEST_ONLY；无原子reset/receipt/HTTP/正式信任证明。回滚撤未挂Port保历史，下一原子reset Service/License/强If-Match/disabled/self完整验证。

## 结果

新增SqlAlchemyPasswordResetAccess复用normal Admin proof与部署锁；专用require_self_reset仅actual first/原身份/本次变更的精确commit前末核，不把旧或受限身份当管理权。原source validator增加可选access_checks，默认行为保持，TEST_ONLY transition新增可选Admin坐标以覆盖self。

3新unit/1380 tests无失败（2既有跳过），无verifier/坏输入/expected边界及缺实际事务静态拒绝。实际隔离PG/Scrypt正常Admin-CSRF与部署锁，错误CSRF/NONE身份拒绝，other目标不得通过self末核。

真实创建用户及Session，TEST_ONLY角色提升后同UOW捕获真实Admin proof、执行TEST_ONLY self reset凭据/根/全Session/Audit/first，首次专用末核成功；坏Token/CSRF/trace/expected/原Credential/Session version/first count/原生命周期到期拒绝，savepoint内意外改名/降角色/停用拒绝，rollback后同源末核恢复。提交后旧Session与新的受限临时Session均无法prove新管理权；真正PasswordChangeService转normal3后新登录恢复Admin proof。未验证仅剩一名Admin场景或License，留完整原子Service。

原真实reset密码source/九表回滚与发布回归通过。开发wheel743224 bytes，SHA256 `19fd2537fa26694cb062189f99aebf293ecdb127521df178af909056c4e4d53c`；非安装包。无Migration/API/依赖/生产升级，兼容0049；撤未挂Port保历史，不回写Hash/复活Session。

内部Auth前置PASS，TEST_ONLY reset转换非原子reset/收据/强If-Match/License/HTTP证明。下一P05A05原子reset Service，License前后、target expected version/disabled保持/self专用末核、真实并发/故障/确认恢复及最后Admin可达性；完整UI/三平台/安装包/Gate仍待。
