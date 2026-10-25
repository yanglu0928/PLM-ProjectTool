# AUT-04-A12-P04-A01 改密原身份与变更末核

## 编码前检查

Phase2/Gate3未通过；WBS P04A01（原子服务的单一Auth proof前置）；基线64cdf09/API02/CR-AUT007，前置cbc5b21真实0048first/Scrypt source。
模块Auth；实体当前User/Credential/Session、changefirst；无HTTP/Schema变化。
权限：普通及受限Session均可证明自己的改密身份，不能取得业务/Admin权限。Token/CSRF/时间/凭据指针在caller UOW锁定；原密码真实校验。首次变更后专用末核精确自己版本/凭据替换和当前Session本次撤销，不泛化为失效Session授权。
验收：真实Scrypt normal/restricted proof，坏CSRF/旧会话拒绝；末核绑定实际first/trace/User稳定字段/新normalCredential/原Session生命周期及PASSWORD_CHANGED时间版本、全部撤销/count，伪造与expiry拒绝；无写。
风险：单一Auth proof不证明Application/收据/提交原子性或公开改密可用。

DEC-20260927-313：共用启停部署advisory锁及5s lock_timeout；独立非Admin PasswordChangeActorProof不携Token/密码，currentCredential flag严格boolean；final只核该次真实immutable first/原身份/预期替换/原生命周期还有效与全Session准确count。真实末核异常静态不可用，False不被truthy接受；后续Service必须限定首次commit前调用。回滚撤未挂Auth Port保历史，无Migration/依赖；测试待。

## 验证结果与边界

1361 tests无失败（2既有跳过）。实际隔离PG18/Scrypt验证普通及受限NONE身份、真实原密码、坏CSRF拒绝；在执行TEST_ONLY转换的同一UOW重新锁定并取得身份，追加真实凭据/撤销Session/真实Audit/first后专用末核成功。伪造Token/CSRF/trace/原flag/Session版本及原生命周期到期拒绝；旧Session不能取得新认证。原双密码历史来源、写后回滚及双Scope发布回归通过。

开发wheel 730294 bytes，SHA256 `583e047354e0b5762d1d911105ab72c562dbf7882af5fd8e7dfc9f26ee48d864`。不是安装包。无Migration/API/依赖/生产升级；兼容0048，撤未挂Port保历史。

下一AUT-04-A12-P04-A02：原子PasswordChangeService，当前身份/真原密码、追加normal Credential、全Session撤销、Audit/first/receipt与首次commit前专用末核；恢复仅当前有效身份及历史双密码证明。当前TEST_ONLY转换不证明完整服务、HTTP、并发、性能、三平台或Gate3。
