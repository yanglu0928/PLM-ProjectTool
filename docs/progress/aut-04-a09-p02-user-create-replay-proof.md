# AUT-04-A09-P02：原始凭据重放证明

2026-09-27 / INTERNAL_PASSWORD_PROOF_PASS，非完整User创建/当前授权PASS。

## 编码前检查

- 当前Phase/WBS：Phase2 / AUT-04-A09-P02；输入冻结Auth/CR-AUT-005/0046；前置P01实际Schema已通过并同步0c0422d。
- 涉及模块/实体：Auth内部UserCreateResult/原PasswordCredential1；无新API/Migration/权限/依赖。
- 目标：只读加载首次结果，以精确不可变原凭据验证重放密码；非现在active凭据。DAO不提交，Application proof消费后各路径尽力清理，不回显hash/密码。
- 验收：真实Scrypt原密码正确/错误/UTF8字节区别、目标后来停用/改名/凭据2仍验证原1/历史不变、错误源/伪造结果/损坏参数/KDF异常静态拒绝、六表无写；unit边界/清理/异常；旧Schema/列表回归。
- 风险：仅技术密码一致性证明，不是当前Session/Admin-CSRF/License或完整请求证明，只有P03同事务组合规范化非秘密receipt与当前权限后才能授权重放。密码Python副本不能承诺全清除，KDF性能未验。

## 实施前决策

保留原Scrypt机制/Verifier；Auth只读Adapter私下取得原Credential1，先严格验证其固定SCRYPT V1格式/整数参数，区分坏源（不可用）和实际密码不一致（CONFLICT_IDEMPOTENCY），不把Verifier的坏metadata false误报用户冲突。原Hash只传原Verifier，不返回公共DTO、receipt或Audit；原结果与传入DTO精确等值证明，actor仍待外层当前权限绑定。

回滚撤新未装配Port保0046历史；无生产迁移/正式信任供给/公开POST。保持后续原子编排前置，不将本项宣称完整创建/登录/可用安装包。

## 实际执行

- 八新unit通过：精确bool结果/非bool故障、非法UTF8/NUL/长度/types、篡改源与全部bytearray清理/无commit、repr不含密码、固定SCRYPT metadata拒绝bool成本/未知错误码静态；全后端1290无失败（2既有Windows符号链接权限场景跳过）。
- `validation/aut-04-a09-p02-user-create-replay-proof/verify.py`真实PG18、原Auth Repository/同caller-UOW首次结果与Audit、真实固定Scrypt；原密码通过实际PasswordIssueAccess（不是完整登录HTTP），错误/trim/NFC字节变化均CONFLICT_IDEMPOTENCY。
- 伪造credential/actor/trace/Audit/first-name拒绝为静态不可用；真实新Credential2后目标停用/改名，原1密码仍匹配、现在2密码冲突，不恢复账户；原DTO/六表全行无写。旧用户无首次结果返回None不补历史。
- 合法Schema但TEST_ONLY算法/bool参数/损坏格式三个独立fixture在KDF前拒绝；真实hashlib.scrypt资源异常静态不可用不冒充密码错误。每次proof字节均擦除；不承诺清除所有Python副本。
- P02真实validator与P01迁移/历史保护再次exit0，二者附原实际文件发布链回归通过。P01已验Windows列表保持历史；本P02无生产装配变化，未再次运行Windows列表独立入口。
- 开发wheel696766 bytes、SHA256 `0cbfdf6413e8dca66056ca2b5a2babfd75e15aa88d0c3218ceefda8c2a0cdff5`；忽略本地产物，不是离线安装包。

Changed/Files：新Application proof消费器/Auth只读Repository、八unit、真实validator、本文/DEC295/CR/STATUS/CHANGELOG。Migration/API：无变化，head0046。Result：仅原始密码技术证明PASS。Known Issues：外层当前Admin Session-CSRF/License/非秘密fingerprint原子receipt必须P03组合后才授权重放；性能/提交确认异常/公开HTTP/正式供给/三平台/完整包/Gate未完成。Next：AUT-04-A09-P03当前授权原子创建与完整幂等。
