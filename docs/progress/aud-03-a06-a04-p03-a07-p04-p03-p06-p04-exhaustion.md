# P06-P04 到期耗尽安全失败

日期：2026-09-27；状态：INTERNAL_PASS，非整体交付或Gate PASS。

编码前：Phase2/P04-P03-P06-P04；CR-AUD-004/ADR011，前置专属claim不再静默耗尽、原Root/pair、SystemActor/静止锁与失败证明已验。涉及Jobs owned到期耗尽同UOW Port/真实证明、Audit仅安全失败Owner/来源核验及可选单命令接线，无DB/API/依赖变化。

政策：仅当前RUNNING、恰好三次/max3、匹配Worker/fence、一致ACTIVE Lease与未完成Attempt且DB clock已到期；预读到期后最小SYSTEM AUDIT_EXPORT_FAILED/AUDIT_EXPORT_ATTEMPTS_EXHAUSTED、identity后验、最后再次真期限检查→Job FAILED/Lease EXPIRED/Attempt固定耗尽码同UOW。当前User/License不授业务但不阻安全停止，不续期、不读正文/写文件、保旧尝试字节。成功/取消/旧代/未到期/未三次拒绝，不能强杀线程或替代用户申请取消。

验收：两Scope真实三代到期，失败审计与三表一致、故障全回滚、真正commit后确认丢失以完整expired失败+唯一SYSTEM源核验，无写重读；最小可选执行器分支只在注入相同identity/Supervisor时启用，不影响旧参数。候选扫描/主循环/领取确认恢复/正式材料/质量/Gate/全Scope包仍待。

Changed/Files：Jobs lease_repository/audit_export_failure提供CHECK/EXPIRE/VERIFY caller-UOW Port；Audit worker_exhaustion/execute_export可选接线；8新unit、独立validation/verify.py及状态/版本/CR/DEC239。Migration/API/依赖：无变更，增量0042保留，无生产操作。

Tests/Result：实际Windows11/Python3.13后端1075无失败，2既有Windows权限跳过；独立临时PG/Vault两Scope真实3秒三代到期，前代/活租约/错Worker拒绝；实际Audit/state写后故障六表全回滚；真实User停用/合成License仍拒绝capture但允许安全失败。真正FAILED commit后注入确认丢失，执行器完整来源恢复、六表无写重读、原staging字节保留；旧P06-P02执行器/发布回归通过。首次脚本因测试相对路径缺file_root失败，修正后重跑通过；模拟确认故障不代表真实网络中断已验。

Build：开发wheel 619732 bytes；SHA256 `f4d59eeba01d7704d7f257cdffb1de919afe701418423b05f3a54d3171529b5e`，不是完整产品安装包。

KnownIssues/Next：耗尽扫描/领取确认恢复/进程loop/CLI/HTTP/正式信任锚/质量/完整Scope/三平台/Gate仍待；下一P06-P05只读扫描与受控收尾。未强杀OS进程或删除原文件。
