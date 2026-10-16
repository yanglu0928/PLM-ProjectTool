# AUD-03-A05-A01：实际提交授权与归档维护例外

日期2026-09-26；Phase2；0.1.0.dev0；结果SUBMIT_AUTHORITY_PASS（独立数据库、License合成）。不是Job提交/Worker授权/导出HTTP/正式发行PASS。

## 编码前检查 / Changed / Files

WBS只处理导出提交当前授权前置。输入冻结API-02/AUDIT_EXPORT S,L,C,I,A及Admin/PM、DM-02归档审计导出维护例外、A03Spec/A04完整存储；前置满足。DEC-20260926-194实施前记录。涉及Audit授权与Project owned操作政策，Auth公开实际Session/CSRF适配复用；实体只权限绑定metadata，无新增Schema/API/角色/Scope/依赖/安全机制，不追写冻结版本。

新增export_submit_authorization.py、7项unit及隔离verify.py。调用方事务内校验固定Spec、Session/CSRF/trace形状、License、Auth真实用户/当前Session及CSRF；项目使用实际ProjectAuthorizationService和AUDIT_PROJECT_EXPORT实时PM/member/department，部署实际DeploymentAdmin。Auth的LicenseImportAccess仅复用Session/CSRF/Admin锁事实，Audit始终另require_valid，不继承License恢复豁免。不创建UOW、不commit/rollback、不写Export/Job/receipt/Audit。Guard可能有自身许可审计，不能据合成Guard测试声称真实Guard永久无写。

Project增加唯一AUDIT_PROJECT_EXPORT write维护操作，仅这个write允许ARCHIVED，所有其他原write归档拒绝保持不变。实际三项目事实锁由owner持有直到调用方UOW结束，无Admin项目旁路；管理员需显式该项目PM成员资格。返回Actor/Scope/Project/Spec hash是最小绑定metadata，不是跨事务权限凭据，后续命令每次实际调用服务，Worker另需当前非Session事实授权。对象被错误适配器修改、错误proof绑定、未知scope/目的或指纹变化拒绝。

## Tests / Result / Migration / API / Compatibility

Windows11/Python3.13后端831项无失败、2项既有符号链接环境跳过。7项新增unit及1项完整归档write矩阵验证：24操作×4角色、只有导出write归档例外、Scope分支/最小冻结结果/no commit、Session/CSRF repr不泄漏、错误请求/腐损Spec、guard执行、当前Actor/proof绑定、异常脱敏、错误适配器修改意图拒绝。Unit的mock不是实际权限/许可证明。

隔离PostgreSQL当前真实Session/CSRF与PM/Admin核验通过：所有非PM角色、跨项目、部署Admin非成员拒绝；显式另一项目PM管理员可申请但不能访问未加入的项目。错误Session/CSRF、future clock导致过期、用户停用、成员暂停、部门INACTIVE、PM降级、部署角色撤销、Session撤销拒绝；License合成Guard失效时项目/部署均拒绝。五类实际User/Session/Project/member/department锁在授权服务返回后仍持至调用方结束，竞争FOR UPDATE真实超时。归档PM授权通过但WORKFLOW_START仍PROJECT_ARCHIVED。所有被观察Export/capture/Job/Outbox/receipt/Audit原行不变；服务没有创造半任务。验证初次使用错误部门DISABLED状态被Schema拒绝，核对原约束改为INACTIVE后完整重跑通过，无生产影响。独立库finally清理，无客户数据。

既有AUD-02-A01受权读与Windows显式平台审计真实数据库/HTTP回归PASS（License/key合成）。开发wheel PASS，SHA-256：`bad3f166a05eb61d8015d807465cd28750eafb57aa72aab8233a0d2fe8a800a5`，不是正式安装包。无Migration/公开API/角色/依赖变化，升级无数据库动作；未装配入口可回退代码，历史不变。

未运行正式License材料、Worker当前权限、Job提交/幂等/Audit原子/HTTP/性能/文件交付验证；不声称权限覆盖率目标或Gate通过。Server2025未验，Debian13暂缓且目标保留。真实业务Owner/质量失败/Gate3/UAT/完整可用包仍未完成。

## Next / 缺口分项

AUD-03-A05-A02：Jobs owned Audit专用最小ExportRef/政策引用enqueue公共Port、固定Scope/Actor/幂等读回与Job+Outbox同事务。Parse enqueue只Document不复用假Document，不重标GLOBAL。A03才能把实际授权、immutable首次Export/Job响应、receipt、请求Audit接到单UOW，之后A06真实Worker权限/Lease/取消/交付。POST保持关闭。
