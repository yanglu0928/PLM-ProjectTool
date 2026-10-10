# AUT-04-A12-P05-A01 管理员重置first与密码proof契约

## 编码前检查

Phase2/Gate3未通过；WBS P05A01单一reset first/proof，前置167cfc0完整内部至Windows change已验。输入64cdf09/API02 AUTH_USER_RESET_PASSWORD S,L,C,I,M,A、CR-AUT007。模块Auth，涉及reset first/immutable Credential；本轮纯Application DTO/proof，无Schema/HTTP/依赖/权限变化。

验收：15字段严格坐标、非负撤销数/ENABLED或DISABLED均允许、自reset不禁；公开只有credential_version。密码write-only bytearray/UTF8/NUL/1024上限、finally擦除；source只能校验当次immutable newCredential真实KDF，严格bool，错误不泄秘密。实际内存Scrypt证明一致/差异/后来当前凭据不代first，不冒充PG持久源或原子reset。

DEC-20260927-317：first记录result/user/actor/old-new Credential ID/version/原expected User version与new version/原target_state/Audit/trace/revoked count/changedAt/acceptedAt；target_state固定为本次转换前后不变状态，count可0（停用无Session），不与change强制>=1混用。self actor==target允许，最终授权特殊核验另任务；自reset受限后需先实际改密恢复正常Admin，再用原reset Key/临时密码历史恢复，不能以受限或失效Session授管理权。receipt非秘密payload绑定目标/expected/固定must-change=true，禁止密码快速摘要。

下一Schema须精确15字段/两个Credential triple FK/User与actor/Audit FK、current target state及changedBy==Admin actor、must_change=true/Audit action版本/全撤销与count来源、不可变/非空down保护；空有数据up/down/ORM/故障/并发另任务。回滚撤未挂纯Port保旧链，不回写凭据或启用目标。完整reset/HTTP/性能/三平台/包/Gate仍待。

## 验证结果

新增15字段immutable first与临时密码Proof/Verifier；source接口verify_reset_password只接本次first与临时memoryview。strict True/False及静态unknown、UTF8/NUL/边界/finally擦除，公开唯一credential_version。不持久化原密码或密码快速摘要。

6新unit/1374 tests无失败（2既有跳过）：DTO enabled/disabled/self与shape不可变、密码边界/错误/擦除/不进source、False冲突/非bool与exception安全拒绝；实际内存独立Scrypt Hash证明原临时密码匹配、UTF8尾空格/后来当前密码冲突、伪造first未知拒绝。该InMemorySource是明确unit夹具，不是已验证PG Repository/当前Admin授权。

开发wheel737736 bytes，SHA256 `6b79155cfb682279783c57797c9d74c0b4261723f381a43cb3f83b38176fa51d`。无Migration/API/依赖/生产升级，兼容0048；本轮未运行PG/HTTP验证，旧真实链证据保留不冒充重跑。Schema来源设计标未实施，下一P05A02真正ORM/Migration与真实验证；原子reset/HTTP/性能/三平台/UI/安装包/Gate未完成。
