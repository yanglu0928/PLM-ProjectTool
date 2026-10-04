# AUT-04-A12-P05-A03 reset first真实临时密码来源

编码前检查：Phase2/Gate3未通过，WBS P05A03；输入64cdf09/API02/CR-AUT007/0049，前置2ec85a6实际Schema已验。Auth first与当次新Credential caller-UOW Repository；无Schema/API/依赖/权限变化。

DEC-20260927-319：get/record不commit、acceptedAt由DB供给，strict15字段及当次新Credential ID/User/version/true flag/changedBy Admin/time/profile；历史重放必须actualfirst全等后真实固定Scrypt校验原临时密码，不能查询当前active代替历史。不校验旧密码Hash以阻止Admin修复坏旧凭据，旧坐标由0049 triple FK及来源约束验证；新增密码严格profile拒绝坏源。Port不授当前Admin/License/Session/CSRF权。

验收：真PG/Scrypt record/get/server时间、UTF8原临时匹配/尾空格-后来密码差异、伪造first/KDF异常非bool九表无写与擦除、later正常change仍原临时first，坏新profile及实际合法first写后caller故障回滚/原Session保留。测试转换标TEST_ONLY，非原子reset/强If-Match/Admin权限/HTTP证明。回滚撤未挂Port保历史，不改旧Hash或复活Session；下一原子reset/专用self末核，包/Gate仍待。

## 结果与验证

新增实际SqlAlchemyPasswordResetResults，get显式15字段，record仅当次newCredential strict profile/actor/true/time且acceptedAt由DB默认；不commit。verify先actualfirst全等，精确历史Credential ID/User/version再真实Scrypt，只接受bool。

3新unit/1377 tests无失败（2既有跳过）；真实隔离PG/Scrypt当次Credential2 record/get/server受理时间、UTF8临时密码匹配，旧密码/尾空格/后来密码冲突，伪造result/user/actor/trace/Credential/state/count及KDF异常/truthy拒绝，九表不变/密码缓冲擦除。unknown ID返回None，旧first重新登记拒绝。

TEST_ONLY reset转换生成真实Hash及User/全Session/Audit/first；之后真正已实现的PasswordChangeService将受限临时登录转normal Credential3并新密码登录，原resetfirst仍匹配临时密码而不接受最新密码。坏新profile实际caller先写root/Session/Audit后record拒绝回滚，合法Credential4+first真正写后caller故障回滚九表，原Credential3会话仍有效。不是原子reset/Admin-CSRF-License/If-Match或reset receipt证明。

原双Scope发布回归通过；开发wheel741372 bytes，SHA256 `5b0487a491369cc3ba44824866d2f873d76c4f3ca57c677217874b90bc5c8857`，非安装包。无Migration/API/依赖/生产升级，兼容0049；撤未挂Port保历史，不回写旧Hash/复活Session。

内部source PASS，完整reset/HTTP/Windows/性能/正式来源/三平台/UI/包/Gate仍待。下一P05A04当前normal Admin-CSRF身份及自reset首次专用末核前置，然后P05A05原子reset Service；保持disabled目标与self范围，不以普通失效Session授管理权。
