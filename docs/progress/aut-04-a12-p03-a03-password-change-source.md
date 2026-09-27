# AUT-04-A12-P03-A03 改密first及真实密码来源

## 编码前检查

Phase2/Gate3未通过；WBS A12P03A03；基线64cdf09/API02/CR-AUT007，前置987fb5a实际0048来源/历史验证。
模块Auth；实体immutable changefirst/前后Credential；无API/Schema变化。
权限：Repository caller UOW无commit；历史密码匹配不授当前权利。首次record使用严格内部draft，acceptedAt由DB生成，不信任draft受理时间。
验收：真实PG/Scrypt旧新两密码匹配/差异、source精确首结果/ID-User-version-time-profile、laterCredential不改原核验；坏source/KDF异常安全不可用，无写/无秘密，caller rollback。
风险：TEST_ONLY转换夹具不等于实际原子改密；当前Session-CSRF/收据/HTTP仍待。

DEC-20260927-312：get显式13列DTO，record严格draft除acceptedAt由DB默认；record也检查两原Credential固定profile，verify先匹配真实immutable first，再分别精确前后Credential，AFTER normal/self changedBy，固定SCRYPT元数据预检后真实KDF。复用Auth已验固定profile校验，不增加Key/摘要/依赖，撤未挂source保历史。

## 实施与实际验证

2026-09-27 / 0.1.0.dev0 / PASSWORD_CHANGE_REAL_SOURCE_VERIFIED_ATOMIC_SERVICE_PENDING。

- 新SqlAlchemyPasswordChangeResults caller UOW get/record/verify；get未知结果None，私有字段显式映射严格DTO；record不commit，acceptedAt由DB生成并由0048来源再次核验，不采用draft受理时间。
- 历史匹配先精确比较实际immutable first，再读取对应前后Credential ID/User/version/time；AFTER正常且changedBy自己。两源固定Scrypt参数/编码格式校验，坏元数据不能驱动任意KDF成本；布尔结果严格判定，不返回Hash/参数或异常详情。
- 2项新repo unit；全后端1359 tests无失败（2既有Windows权限跳过）。实际PG18/Scrypt source验证：caller-UOW record服务器时间/get/未知结果，真实UTF8前后密码匹配，两项各错/交换/尾空格冲突；伪造first ID/User/trace/前后Credential/count拒绝，KDF异常/非bool不可用，八表不变且Proof双缓冲擦除。
- 后来TEST_ONLY追加Credential3更换真实当前密码，原请求仍校验1/2，使用后来密码替代当次新密码被拒绝；旧first不能在后续current root重新插入。原凭据历史保留。
- 真实新Credential4错误KDF参数在record拒绝且夹具写整体回滚；另真实合法Credential4/User更新/Session撤销/Audit/first写后故障明确已到达record，再由caller UOW整体回滚八表，原v3会话仍可用。全部转换为TEST_ONLY夹具，不证明当前用户有权改密或完整生产服务。
- 原双Scope文件发布回归通过；未重跑所有历史HTTP脚本，不把Schema/Source测试当原子Session-CSRF/幂等收据证明。
- 开发wheel727401 bytes，SHA256 `dd39bbc4cc958397aaf7161ff779498ffe646c669994c496f581ed69ca575176`；仅构建检查，不是安装包，不上传wheel/密码/库数据。

兼容0048，无新Migration/依赖/API/生产升级；回滚撤未挂source入口保所有first/凭据/Audit历史，不恢复旧密码或Session。当前认证/锁/同Key竞争/最终变更专用证明、原子Application/HTTP/Windows/UI/正式信任/性能/三平台/完整包/Gate仍待。下一A12P04：真实当前Session-CSRF（含受限）与锁定User凭据、真实当前密码校验、同UOW追加正常Credential/版本/全Session撤销/Audit/first/receipt，换密末核不无条件跳过授权；历史恢复仍要求当前有效认证。
