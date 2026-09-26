# AUD-03-A06-A01：异步导出当前权限

日期2026-09-26；版本0.1.0.dev0；Phase2；结果CURRENT_AUTHORITY_INTERNAL_PASS，不是完整Worker验收。

## 编码前检查与实现

输入冻结API-02/DM-02、A03当前权限Port和已验收A05内部提交。按DEC-20260926-197先记录后实施。一个问题：受理后每个异步安全检查点重新核验实际当前权限。新增Auth公共CurrentUserFacts/CurrentUserAccessPort及SQLAlchemy实现、AuditExportCurrentAuthority；六项unit与独立数据库验证。无新实体、Migration、API、角色、依赖、技术栈或Scope，0038不变。

Auth只锁本模块实际enabled User并读取当前部署角色，不访问Audit/Project私表。Audit在CAPTURE/RENDER/PUBLISH每次先核验License，再锁当前User，项目经Project公开AUDIT_PROJECT_EXPORT核验实际当前PM/成员/有效期/部门/项目，保留归档维护例外；部署只当前Admin，不授予项目旁路。返回None不提供可跨事务复用证书。Export UUID供License技术trace关联，不新增业务审计事实。

此Port的request仍只是坐标。可信Owner必须先用持久不可变Export/acceptance绑定Actor/Scope/Project，并核对真正Job租约；本项没有这个编排，测试Export UUID为合成坐标，不能声称受理Root或Job证明已完成。原Session注销或到期不自动取消已受理异步工作；不把HTTP授权省略，也不持久化原Token。实际禁用用户/撤PM或Admin/暂停成员/部门停用/许可失效都拒绝继续。

## 实际验证

Windows11 / Python3.13 / PostgreSQL18独立UUID库：三个stage、PROJECT/DEPLOYMENT、实际四类项目角色和部署Admin矩阵，跨项目/未知User/无Admin项目旁路、归档维护、当前用户禁用/成员暂停/降角色/部门停用/部署角色撤销，各stage重新拒绝，通过。注销原Session后实际当前权限仍可核验。User/Project/member/department四事实及部署User锁在Port返回后仍被竞争连接实际lock_timeout证明保持到caller UOW退出；不写Export/acceptance/membership/capture/Job/lease/attempt/outbox/receipt/Audit。

License测试为合成Guard，正式信任锚/真实到期来源未证明。隔离库finally清理，无客户数据或生产操作。六项unit覆盖输入与DTO再校验、精确身份/Project/operation/PM绑定、无Admin旁路、每stage新检查、安全异常与依赖无默认许可。

后端853项无失败，2项既有Windows符号链接权限跳过。A05-A03-P02完整实际提交/并发/故障/40P01/历史重放回归通过。开发wheel构建通过，SHA-256 `a15d3be6496a05e849d49a1310389b3dae72f7c733ee46897e35153093c639ba`，非正式可用包。

## 当前租约与交付缺口 / Next

实际代码核查：jobs/application/lease.py只公开claim/heartbeat/finish/retry_or_fail；finish先改成功状态，再在caller事务发布回调。lease_repository.py已有_current锁Job→Lease→Attempt并核对worker/fencing/state，heartbeat/finish另核对clock_timestamp到期；没有适用于capture/render的公开只检查当前租约Port，也无取消命令/协作取消实现。只有状态枚举存在，不是行为验收。不得借heartbeat改时长作为只读检查，也不能先标成功再执行文件I/O。

下一项AUD-03-A06-A02：Jobs owned公开事务内当前Lease检查与真实取消边界，然后Audit实际Root/acceptance/Job/current-authority/capture编排、整事务锁序/死锁和旧Worker竞争验证。生成文件须在受控存储生命周期内进行，发布仍需当前权限、Job fencing与取消、不可变结果和完成Audit同事务；相关Artifact Port/崩溃对账/空间限制及公开交付尚未实现。

升级无新动作，需要既有0038；回滚可撤未装配Port，不更改历史。POST保持关闭。Server2025本轮未验，Debian13暂缓但目标保留；真实业务Owner、AI质量、正式信任材料、性能、Gate3、UAT和完整程序包仍待。
