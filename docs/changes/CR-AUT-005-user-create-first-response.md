# CR-AUT-005：受控User创建首次响应与幂等

2026-09-27 / IMPLEMENTATION_IN_PROGRESS，按用户持续自主授权执行；原冻结64cdf09与Migration0001～0045不追写。P01内部Schema/ORM/DTO及新增0046、P02原始Credential1只读/实际Scrypt密码技术证明已隔离验证，见相应progress；当前Admin Session-CSRF/License/完整请求receipt组合留P03。公开POST和原子命令未完成，CR整体不关闭。

## 来源与实际冲突

冻结API-02 AUTH_USER_CREATE要求当前DeploymentAdmin/Session/License/CSRF、持久幂等/Audit、201 UserView及初始密码write-only。旧`UserCommandService.create_user`只持Actor UUID与访问Port，内部自行开UOW，创建User/Credential/Audit后返回三字段CreatedUser；无通用receipt/不可变首次UserView或实际Session-CSRF生产编排。直接挂POST将缺原子幂等，并可能在User后来停用/改名/换密时重放变化后的响应或复活账户。

User已有不可变PasswordCredential历史（0006 UPDATE/DELETE/TRUNCATE触发器）和用户名唯一性；原创建默认新User deployment_role=NONE，激活初始credential_version/lock_version=1。新受控创建保留该默认，不顺手开放角色修改或部署管理员提升。

## 方案比较与选择

- A：直接调用旧创建Service后另写receipt：双UOW/不原子，拒绝。
- B：仅username指纹，忽略密码变化同Key：不同密码错误重放，拒绝。
- C：把密码明文/可逆值或快速SHA256放receipt：扩大原密码保护之外的离线猜测面，拒绝。
- D：独立HMAC命令key绑定密码：可行但新增信任Key/备份供给成本，当前无需为此替换既有密码验证机制。
- E（选择）：通用receipt只绑定非秘密规范化请求字段；Auth owned不可变首次结果记录固定新User/初始Credential1及首次安全UserView。**每次同Key重放还必须通过既有真实Scrypt PasswordVerifier核验该原始不可变Credential1**，组合证明完整请求一致；不把receipt部分指纹单独当完整重放许可。密码不同固定CONFLICT_IDEMPOTENCY，Verifier/源故障静态不可用，不忽略或猜匹配。

## 规则与模块边界

- 新命令必须实际Session-CSRF及当前ENABLED DeploymentAdmin/License；Actor来自owned Auth访问，不由客户端提供。初次与重放同UOW再核，结束前License/当前权限再验。
- 保留原创建入口供其原内部/初态用途；新编排在同一调用方UOW直接使用Auth owned Repo/规范化/Hash/PasswordVerifier及Audit/通用receipt，不嵌套调用另开UOW的旧Service。
- fingerprint覆盖规范化显示username与canonical、操作版本等非秘密字段；密码UTF8字节精确比较（不trim/NFC密码），借原批准Scrypt verifier，不保存额外快速密码摘要、回显或记录密码。输入缓冲区repr隐藏/各路径尽力清理，不能宣称清除Python所有副本。
- reserved receipt→新User/初始Credential/激活→USER_CREATED Audit→不可变安全首次快照→receipt complete同事务；任一点错误全回滚。相同Actor/操作/Key同载荷并发只创建一次；相同Key不同username或密码冲突；不同Key同canonical返回用户名冲突，不虚构第二身份。
- 原始Credential固定绑定user_id/credential_version=1/原creator/首次创建来源，历史hash只在Auth内部Verifier Port使用，绝不进入response/receipt/snapshot/Audit/Trace。快照存凭据逻辑ID/FK是内部source绑定，不是公开Credential信息。
- 首次201 UserView/ETag为创建时不可变事实；后续账户状态/名称/密码改变后重放仍原始安全快照，不更新User或Credential、不启用DISABLED账户、不增加Audit；当前GET另取现在状态。旧Key每次仍须当前请求Admin/Session-CSRF/License，不能借原actor绕过撤权。
- Schema记录与受控创建Audit/User/Credential来源一致，并UPDATE/DELETE/TRUNCATE拒绝；不能以Schema事实代替Session或密码验证。已有旧User不伪造补填首次受理历史。

## 迁移、兼容与回滚

拟增加Auth owned创建首次结果表/DTO与连续0046（以实施时实际head核对）和ORM；不能修改0001～0045/原冻结。必须空库及有数据up/down/re-up、原User/PasswordCredential/Session/旧业务保留、非法来源/版本/快照拒绝、不可变/回滚验证。已有首次结果历史时down必须拒绝丢失，不自动删记录或生产数据。旧代码撤新router/命令可回滚，保持完整历史；升级须备份/停写/实际Migration，尚无生产迁移。

公开冻结路径/权限/Envelope不变，无新厂商/依赖/角色，原Scrypt与License机制保持。真正API输入/幂等错误/响应绑定在HTTP子项明确记录，不能本设计即开POST或标PASS。

## 验收与剩余风险

P01 Schema/ORM/strict快照及源约束；P02实际当前授权/初始不可变Credential证明与原密码验证Replay Port；P03同UOW创建/receipt/首次结果/审计与并发/密码不同冲突/后续停用重放不复活；P04可选HTTP严格write-only输入/CSRF/安全错误；P05 Windows显式write装配、readonly/default关闭、实际缺信任拒绝及旧读写回归。

必须用真实Scrypt证明初始密码可登录/重放验证，不用TEST_ONLY；真实Admin/Session/License positive可明确隔离合成信任但不能称正式供给。Verifier耗时与锁序/20并发性能、提交确认异常、密码缓冲副本、正式信任/三平台/完整管理面与最终包仍待，按证据分别验收，CR保持未完成。
