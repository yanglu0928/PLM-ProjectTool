# P04-P03-P04-P05 取消提交确认丢失核验

日期：2026-09-27；状态：INTERNAL_VALIDATED / REMAINING_LIFECYCLE_PENDING。

编码前检查：Phase2；WBS AUD-03-A06-A04-P03-A07-P04-P03-P04-P05；输入CR-AUD-004/ADR011；前置真实首USER申请、活代ack/到期恢复、SystemActor静止锁已验。涉及Jobs owned只读CANCELLED/Lease/Attempt证明和Audit owned唯一完成事件、核验Owner；无新Schema/API/依赖/权限扩张。只解决实际提交确认丢失，不接主循环或猜测网络错误已成功。

验收标准：活代RELEASED与过期EXPIRED均绑定当前Worker/fence、原Job/Outbox/Scope/trace/payload、一致完成时间；原首USER源必须存在且为RUNNING申请；唯一SYSTEM事件匹配当前identity/原actor/原trace/固定原因和完成窗口。真正commit后故障可只读核验，多次无写；错源/重复事件/终态或绑定/完成类型错误拒绝。不调用Mutation、不commit、不读取文件，不以STALE/单一CANCELLED代替证明。

风险/回滚：即时PENDING取消没有Worker租约，不属于本证明；原技术取消/恢复没有SYSTEM完成源不能采用。撤未装配核验保历史/终态/字节；正式材料/三平台/网络停机/质量/Gate/完整Scope可用程序包继续待验。

Changed/Files：Jobs CancelledJobProof/当前代owned Repository与只读Port，Audit完成来源Repository/核验Owner、两unit文件、独立验证脚本及状态/版本/决策/CR。Migration/API/依赖无变化，0042不变，无生产升级；内部安全核验无User/License业务旁路或新事实。完成来源同真实首USER事件的时间顺序亦实际校验；RELEASED只能租约活期完成，EXPIRED只能到期后完成。

Tests/Result：6新unit（Owner 4、完成源2；字段/类型/缺失/重复/时间窗/identity/无mutation），Windows11/Python3.13完整后端1031项无失败、2既有权限环境跳过。真实PostgreSQL18临时库/临时Windows Vault，两Scope×活期ack/过期恢复真正commit后故障，真实CANCELLED+Lease/Attempt+唯一首申请/完成Audit核验；四次重复八表完整snapshot无写。错Worker/fence/root/完成类型、RUNNING/CANCEL_REQUESTED/成功、缺首USER/缺SYSTEM/重复SYSTEM/第二identity丢失均拒绝，旧实际发布fixture通过。没有新增Owner并发竞争、生产账户或网络断线测试，不扩大证据。

初次完整unit执行2项错误来自新测试requested_at早于fixture accepted_at；修正合成时序为accepted后1秒申请、2秒完成，未改生产校验，完整重跑通过。之后补首USER与完成事件时序检查再次完整unit/实际DB重跑通过。开发wheel603233字节，SHA256 320ce081aa7a281c50154488dcb90bbae641aac6bb7831e6cfa4cb8b4608b301，构建通过；不是可用安装包。

Known Issues/Next：瞬时失败retry选择及对应审计、执行器安全终态接线/主循环/公开HTTP-IfMatch仍待。Next P04-P03-P05瞬时失败重试策略与安全Owner；CR/Gate不关闭，完整Scope保留，最终交付目标持续active。
