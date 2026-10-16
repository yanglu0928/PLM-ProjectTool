# AUT-04-A12-P01 当前改密事实及业务授权限制

## 编码前检查

Phase2/Gate3未通过；WBS AUT-04-A12-P01；输入64cdf09/API02/DM02、CR-AUT007；前置e8349c5已真实复现缺口。
模块Auth；实体当前User/PasswordCredential/Session；本轮无公开API/Schema变化。
权限：已签发Session只证明身份，业务部署读写/项目读写/Review五种原Auth proof须精确当前Credential must_change=false；受限事实允许后续改密/退出，不产生普通授权。
验收：typed当前事实/严格布尔和版本绑定、真实Scrypt受限Session、五原proof全部拒绝且无写、普通Credential正常及历史Session失效、坏Token/expiry/CSRF；原Windows链与全unit回归。
风险：改密HTTP与受限身份投影尚未实现，不开放reset；不把内部限制当完整用户流程。

DEC-20260927-308：共用Auth当前正常凭据EXISTS谓词绑定active ID/User/credential_version/must_change=false，接五业务proof；新增私有当前Session凭据事实读取和严格DTO，不修改Session正常签发语义、不加客户端flag/缓存/Schema。回滚撤新入口但不得公开reset绕过限制。

## 实施与验证

2026-09-27 / 0.1.0.dev0 / INTERNAL_CREDENTIAL_RESTRICTION_VERIFIED。

- 私有SessionCredentialFact严格UUID/正bigint/boolean、固定能力白名单；must-change只能内部声明PASSWORD_STATE/PASSWORD_CHANGE/LOGOUT，BUSINESS拒绝。该规则不等于改密HTTP已经实现。
- 当前事实精确User activeCredential ID/User/version绑定，当前Session时间/撤销/credential版本有效；只读共享User/Session锁。统一normal_current_credential EXISTS接部署读写、项目读写、Review五Auth proof；源缺失/不匹配不产生正常权限，无缓存或客户端flag。
- 1346 tests无失败（2既有Windows权限跳过），2新增unit验证严格事实/能力矩阵。实际PG18真Scrypt签发must-change会话仍证明身份，五业务proof均拒绝且七表不变；fact明确credential2/required=true；未知Token拒绝。
- TEST_ONLY追加normal Credential3，旧Session五proof及fact拒绝，新真实Scrypt会话五proof恢复且七表不变，fact required=false/version3；原Credential1/2/3保留。本夹具不是已实现的密码变更服务。
- 原A12缺口复现脚本更新为反回归断言，旧e8349c5复现证据仍保留，不改写历史；不让已修复源码继续通过“漏洞存在”断言。实际Windows状态链完整矩阵及原发布回归通过；未声称所有历史脚本都跑过。
- 开发wheel721216 bytes，SHA256 `5207bdc0c5c33f5c49f8feec0df1652e027ac6fd10d6ef6d52705961de89be90`通过构建检查，不是安装包、不提交临时wheel。

无Migration/依赖/公开API/生产升级，兼容0047。受限Session最小公开身份投影尚未接线，当前GET/login仍旧投影；普通业务五proof已限制，但不宣称完整受限流程或全部未来业务入口验收。改密/退出前置整合、reset/change first/原子链/HTTP/UI/正式信任/性能/三平台/包/Gate仍待，reset入口关闭。下一A12-P02受限身份投影与密码状态Port，使login/session明确改密状态且不枚举项目或管理权限。
