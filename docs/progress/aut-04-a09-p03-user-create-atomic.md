# AUT-04-A09-P03：当前授权原子User创建

2026-09-27 / INTERNAL_ATOMIC_COMMAND_PASS，公开HTTP与Windows写组合未完成。

## 编码前检查

- 当前Phase/WBS：Phase2 AUT-04-A09-P03；输入冻结Auth API/CR-AUT-005/0046；P01/P02内部实际验证已同步ddd3f82。
- 涉及模块/实体：Auth User/Credential1/first-result，公共Audit与Platform receipt Port；无新Schema/HTTP/权限/依赖。
- 当前权限：原Auth Session-CSRF/ENABLED DeploymentAdmin真实锁与到期判断，不接受客户端actor；原LicenseGuard前后调用。License Guard既有公共接口自有UOW，不伪称其与业务在同一事务或完全消除检查后撤权窗口；本项不跨模块改License。
- 本次目标：同业务UOW reserve→User/Credential/激活→Audit→不可变first→complete→当前权限及License再核→commit；重放先当前权限，再非秘密指纹与原密码证明组合，返回原safe View不提交/不复活。
- 验收：真实Scrypt/Session-CSRF/admin权限、同Key竞争单身份/credential/Audit/结果/收据；不同密码/用户名同Key冲突，不同Key同canonical冲突；后续停用换密原首次重放；六表完整回滚及逐点故障/末尾撤权、清理/静态错误；unit/原Schema+读取回归。
- 风险：KDF位于当前Admin锁事务内，20并发性能未验；提交确认异常可能已提交但只返回静态不可用，客户端必须用同Key重放，不自动重试新创建；正式License供给未完成。公开HTTP仍关闭，非安装包验收。

决策：保旧Service入口，不嵌套其UOW；复用Auth现有同策略Admin Session-CSRF Adapter的具名子类，权限不变。新Auth result Repository增加caller-UOW记录首次源，不直接写Audit/Platform内部表。无生产迁移；回滚撤未装配Service保0046历史。

## 执行证据

- 新`CreateManagedUser`只接session/CSRF/trace/username/write-only密码，actor来自Auth。严格输入/规范化、非秘密fingerprint reserve与原Credential1 proof组合重放、初次各写同caller-UOW、当前权限/License再核；新result record还私下校验真实初始SCRYPT metadata，坏源不提交。
- 八新unit/全后端1298无失败（2既有Windows符号链接权限场景跳过）：初次绑定/非秘密fingerprint、重放强制原密码且无commit、当前/末尾权限License拒绝、参数/源/审计/哈希/commit故障静态错误/缓冲清理。
- `validation/aut-04-a09-p03-user-create-atomic/verify.py`真实PG18+Scrypt+当前Admin Session-CSRF：两相同Key并发单User/Credential1/USER_CREATED Audit/first/receipt，两个不同密码竞争同Key恰一成功一冲突；原密码通过真实PasswordIssueAccess，不作为完整登录HTTP证明。
- 同Key不同用户名/密码、不同Key同canonical冲突；普通/未知/已撤Session、Admin降角色或停用、CSRF/License拒绝。目标后来合法插入Credential2并停用改名fixture后，原Key只返首次safe View且六表全行无写，不复活；新密码不当原密码。
- 九个实际postwrite故障全部到达并计数：reserve/User/Credential/activate/Audit/first/complete/末尾License/实际同事务Session撤销；全部六表全行回滚。非法初始Hash在Source拒绝、真实KDF资源故障、末尾实际Session时限拒绝均全回滚。
- 真实commit前故障回滚、真实commit后确认故障保已提交事实但返回静态不可用；同Key随后恢复原结果不写/不重复Audit。首轮validator失败暴露ContextManager代理没有保存enter返回的实际tx，修正夹具并加两侧commit boundary reached断言重跑通过；没有放宽生产规则或把提前失败当commit证明。
- P03实际validator附双Scope实际文件发布链回归通过，P02原密码证明与其发布回归再次exit0；A07两actualWindows列表/当前权限/分页/依赖故障及缺正式材料拒绝与发布回归再次exit0。完整创建HTTP/性能等未验。
- 开发wheel700157 bytes，SHA256 `4210fa07b1554ea5a84fc910098a3038e48315dc79e055c834e5fdf41377ae85`，仅本地忽略开发产物，非离线安装包。

Changed/Files：Auth原子Service/具名Access/首次结果Repository记录Port、八unit与真实validator、本记录/DEC296/CR/STATUS/CHANGELOG。Migration/API：无变化，head0046；原入口/默认HTTP保持。Result：内部原子命令PASS。Known Issues：正向License显式合成，Guard既有独立UOW前后核验并非业务同事务License锁；20并发/性能、公开输入/HTTP、Windows写装配/正式信任/三平台/完整包/Gate仍待。Next：AUT-04-A09-P04可选User创建HTTP。
