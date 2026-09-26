# P06-P06 领取提交确认恢复

2026-09-27 / INTERNAL_PASS，非整体模块/发行/Gate通过。编码前：Phase2/P06-P06；CR-AUD-004/ADR011；前置P06-P03专属准入、P06-P04/05真实状态收尾已验。涉及Jobs owned当前活claim只读Port与Audit准入确认；无实体/Migration/API/依赖/权限变更。

问题：领取commit异常不能判断是否已分配真实Lease。选定方案：只捕获本次已构造命令/真实Claim/受控identity，结束原UOW后新UOW核原Root/accepted/pair/当前同Worker-fence活Lease/Attempt/完整Claim/当前同identity；全部一致才返原Claim。不得盲claim、用STALE猜成功或从候选推断。commit异常不得走通用deadlock自动重新领取，核验失败只报安全错误。

权限：这是技术领取收据，不授正文权限；后续执行仍按实时User/License授权。已过期/已取消/旧代/identity变化拒绝；无改状态/Audit/文件/renew。保原普通领取与三次真实前commit竞争重试。风险：当前generation已改变会拒绝，后续调度再处理；无持久跨进程未知command恢复，本项不冒充该功能。

验收：Unit成功/回滚/错源/identity/不重复领取；双Scope真实PG commit后响应故障仍一Lease一Attempt、不写核验、真正未commit整回滚拒绝、真实当前权限业务拒绝保留，旧准入/发布回归。Migration/API无变化，撤确认分支保历史回滚；完整loop/CLI/HTTP/Gate/安装包未完成。

Changed/Files：Audit claim_export私有未确认标记与只读源核验；Jobs audit_export_claim.check_target和专属Repo实际current活Lease/Owner/type/max3/未完成Attempt读取；3项unit与独立validation，配套STATUS/CHANGELOG/CR/DEC241。Migration/API/依赖无变，0042不改，无生产数据操作。

Tests/Result：Windows11/Python3.13 1084项后端无失败，2既有权限跳过；双Scope临时PG/Vault真实commit前故障整回滚/一次commit不重领/仍PENDING count0，实际commit后抛确认故障返回原命令且一Lease/Attempt，完整源六表重复不写；错Worker、3秒实际过期、新代及成功后拒绝；实际User停用/合成License仍capture拒绝，但技术收据允许核源，恢复权限新代正常发布。首次脚本直接调用内部_confirm时仅捕获AuditWorkerError而Jobs端正常拒绝JobLeaseError，修正测试异常范围后重跑通过；公开claim_next仍安全错误，不泄露内部异常。

Build：开发wheel 622972 bytes，SHA256 `b7dbf06621c99d8243f412e2dc3c7303ead725488093e56f2d9c57bbd6582016`，非完整产品安装包。

Regression：旧P06-P03专属领取真实双Scope/并发/5秒retry/三代过期/不混领/整回滚及夹具发布验证重跑通过；其历史输出pending仅说明该旧脚本未覆盖新分支，不改写旧证据范围。

KnownIssues/Next：未证明实际网络断线或跨进程丢失未知命令的恢复；当前代变化只拒绝，不猜成功、不盲重领。坏源隔离/公平/主循环/CLI/HTTP/正式信任/质量/完整Scope/其他平台/Gate仍待，下一P06-P07有界后台单步编排/停止控制。
