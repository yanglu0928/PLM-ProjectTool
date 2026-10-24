# P06-P03 审计专属领取与命令适配

日期：2026-09-27；状态：CLAIM_ADMISSION_INTERNAL_VALIDATED / EXHAUSTION_AND_LOOP_PENDING。

编码前：Phase2/P04-P03-P06-P03；输入CR-AUD-004/ADR011，前置原submit/Job-Outbox、受控identity/真实静止锁/单命令执行器已验。涉及Jobs owned专属候选/领取Port与Audit原Root/pair准入；Job/Lease/Attempt，不新增DB/API/依赖/权限。

发现偏差：通用claim_next混领所有模块且会静默终止耗尽尝试，不可直接供Audit执行器使用。保留旧通用入口兼容现有消费方，新增固定audit/AUDIT_EXPORT选择；候选无写无锁，仅Root→pair→Job一致顺序后可实际领取，复验actual Claim完整binding/活租约。已满三次不静默FAILED，留给下一分项受控到期/耗尽审计；该前置缺口不标整体通过。Scope不限客户断言，真正原Root决定。

验收：两Scope真实PENDING/RETRY_WAIT/过期RUNNING、新Worker/fence命令、其他Owner不变、并发不重复、坏Root/pair或identity/写后故障整回滚。max3/取消/成功/未来available不领取，无正文/file I/O/强杀/续原租约；当前User/License业务授权仍由执行器逐步核验，不授系统业务角色。commit确认丢失不猜已领取，保真实租约等待恢复。撤未装配准入保历史；主循环/耗尽安全终止/正式包/Gate仍待。

Changed/Files：Jobs AuditExportClaims/Candidate与专属Repository，Audit ClaimAdmission/严格ClaimedAuditExport命令适配，unit/实际验证脚本及CR/状态/决策/版本记录。无Schema/Migration/API/依赖变化，0042保留，无生产升级，通用claim_next未改。候选选择不锁不写，最终领取populate_existing刷新避免同UOW先读对象缓存旧状态；原Root/pair绑定后actual eligible/current lease最后再验。

Tests/Result：7新unit（原pair/实际命令/空与三次竞争限制/输入与错Root-pair/identity/坏actual claim/确认错误不重复猜领取/真实活心跳拒领取）。Windows11/Python3.13后端完整1067项无失败、2既有权限环境跳过。实际bounded PG18临时库/Vault两ScopePENDING领取后实际capture/render/publish，最高优先级其他Owner全文行保持不变；两个独立Supervisor并发只一条领取成功。真实授权retry后5秒等待期间无领取无写，deadline到后实际下一代。真实3秒到期三代不同Worker/fence，原Lease EXPIRED与Attempt保留，第4次不领且六表无写、原RUNNING不被静默FAILED。实际claim全写后故障与第二identity丢失六表回滚；旧发布fixture回归通过。错Root/pair为unit注入拒绝，未虚称数据库源腐坏整套实测。

验证fixture结束使用既有技术取消排除过期审计样本、通用技术finish排除其他Owner合成样本，只在临时库；不作为实际耗尽审计/Document业务或生产删除PASS。开发wheel617526字节，SHA256 521c59132af30958179adc175e154a17b7c8464fa4dd789f29af314fa9d11ea6，构建通过；不是可用安装包。未运行实际领取commit后确认丢失恢复/网络断线/三平台发行或新执行器全循环。

Known Issues/Next：P06-P04补已到期且三次耗尽的安全终止/审计；随后领取确认丢失原源恢复/主循环/CLI/HTTP。坏来源当前拒绝并回滚，隔离/告警与健康任务公平选择尚待主循环治理； bounded contention的None不是全队列已空证明。Scope和正式信任源/质量/Gate/最终包均保持未完成。
