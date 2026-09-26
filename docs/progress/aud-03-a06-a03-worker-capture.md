# AUD-03-A06-A03：受权Worker固定来源事务

日期2026-09-26；版本0.1.0.dev0；Phase2；结果AUTHORIZED_WORKER_CAPTURE_INTERNAL_PASS。不是文件渲染、Artifact发布、公开HTTP或正式包验收。

## 编码前检查 / Changed / Files

输入A05完整受理/不可变acceptance、A06当前权限/租约/取消及A04实际capture；前置满足。实施前DEC-20260926-201；任务只把已实现能力接成实际已受理Worker capture事务。新增worker_capture.py命令/服务/Repository Port、SubmitRepository只读peek、7项unit和独立实际链验证。无新Schema/API/角色/依赖，0039不变。

Worker仅输入Export UUID、原Job UUID、规范worker和fencing token，不接收客户端Actor/Scope/任意payload/凭据。先无锁peek不可变Root作为内部查找线索，再当前License/真实User/PM成员部门或部署Admin；随后Root加锁精确重读、原acceptance及源Audit核验、Queue公共Port原Job/Event pair精确身份、公共Lease checkpoint。检查真实ClaimedJob Type/Scope/Project/原Trace/最小Export/策略payload和generation，不用历史Actor或DTO当授权。peek不授予权限，不用于公开读取。

锁序当前User→Project/member/department→Root→Queue advisory/Job/Outbox→Lease/Attempt，避免Root-first与提交User-first反序。调用真实single-statement capture并核对结果完整坐标/版本/时点/count/hash；结束前再次当前权限/License与数据库clock租约检查，才commit固定集合。不会finish/heartbeat/生成或发布文件。已有seal仅重放原集合，新的generation不得偷偷新capture。

任一失败整个UOW回滚含成员/seal，只有真实因果链DBAPI40P01最多三次新UOW重新授权；一般存储错误/未知commit不重试。长capture末次检查到期拒绝，不以锁阻止时间流逝。没有性能达标或永久权限证明。

## Tests / Result

Windows11/Python3.13/PostgreSQL18独立库：实际Session/CSRF/PM或Admin提交产生Root/请求Audit/acceptance/receipt/Job/Outbox，实际claim后Worker通过当前事实/原Ref/租约固定两Scope集合。重复与新增源事件不改原seal，真正双调用并发首次仅一capture/同成员数；归档维护允许，跨Job/错worker/当前User禁用/暂停成员/降PM/部门停用/撤部署Admin/许可拒绝无写。注销Session不自动取消实际已受理任务，当前业务权限仍须满足。

真实成员/seal后故障、末次License失败、真实1秒Lease在capture后到期均全表快照不变；真实接管拒旧Worker，下一generation复用原seal。实际Jobs取消REQUESTED拒capture，不靠测试改枚举。真实PG40P01发生在seal写后，完整事务恢复至第二次并重新授权；连续三次耗尽无残留。实际旧Root无acceptance和缺Outbox均拒绝不猜修复。隔离库finally清理，无客户数据/生产操作。

License为合成Guard，不能证明正式信任锚/真实授权来源。没有文件/Artifact或Worker进程调度；既有capture行数上限机制不等于10万行实际性能。后续publish Job-first锁序/取消下载与真实产物仍需独立验。

首轮夹具误从被导入脚本获取未导出的JobRef；修正为直接导入公共合同后通过。首轮7项unit因Mock把assert_current当保留断言名而失败，改明确spec并完整重跑。最终873项无失败（2项既有Windows符号链接权限跳过）；7项新增unit覆盖输入/根及原Ref/实际Claim/结果绑定/末次检查/有限重试及commit。真实完整原子提交与协作取消回归通过。开发wheel通过，SHA-256 `8300df1faebe349789189acc699aef0ce42be98b1b26d499338631b04fa34f9e`，非正式安装包。

## Migration / API / Compatibility / Known Issues / Next

无Migration/API/依赖变化，需要既有0039，升级无新动作；撤未装配Worker不删除历史或降级绕过保护。Server2025未验，Debian13暂缓但正式目标保留。正式信任材料、真实业务Owner、AI质量、性能、Gate3/UAT及完整可用包仍待，整体Scope不缩减；导出POST仍关闭。

下一项AUD-03-A06-A04：固定seal安全投影与JSONL渲染、受控Artifact存储/空间/归属/Hash及生命周期前置核查和实现；随后当前权限/Lease/取消保护下原子发布与安全结果访问。用户取消receipt/Audit/HTTP仍需当前权限接入，不以内部可信Port代替。
