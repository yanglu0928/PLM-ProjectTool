# P04-P03-P04-P02 取消申请事务

日期：2026-09-26；状态：INTERNAL_REQUEST_TRANSACTION_PASS / WORKER_CONFIRMATION_PENDING。

编码前检查：Phase2/P04-P03-P04-P02；输入冻结API03 S/L/C/I/M/A/协作式取消、CR-AUD-004，前置真实取消权限/原Root-acceptance-pair及技术取消Port已验。涉及Audit Owner、Jobs owned只读首次取消事实、Platform caller-UOW幂等；无Schema/API/依赖扩张。

单问题：可信Owner读Root的original actor/spec→当前Session-CSRF-License及creator/PM→锁原Root/pair→同UOW首取消历史/唯一USER申请Audit/持久收据。同key按首次Audit不可变响应重放，不用当前状态改变首次响应；新key检查已取消/终态只记录CHECKED，不覆盖首申请或复活任务。取消技术状态没有首申请Audit时拒绝接管来源。首Actor/time/reason保原、Audit不含reason正文，仅USER_REQUESTED；客户端不提供原actor/路径。

验收：实际PG双Scope RUNNING/PENDING申请、同key/并发重放/异载荷冲突、后续CANCELLED仍重放首次CANCEL_REQUESTED、审计及技术写后/后验授权失败整UOW回滚、跨项目/当前权限/License拒绝，终态成功不撤回结果。后台SystemActor确认/到期恢复与HTTP未完成，正式包/Gate待。

Changed/Files：`request_export_cancel.py`可信Root绑定、专用取消权限前后重核、原0015持久幂等；`export_cancel_sources.py`以不可变USER Audit为首次响应源/唯一首申请证明；Jobs `read_facts`严格当前状态与首次完整actor/time/reason只读DTO、reason隐藏repr；5新unit/实际PG脚本。新key重复检查记录CHECKED，首申请动作只有一次REQUESTED；同key没有第二次Audit/收据/状态写。技术取消事实缺首申请Audit时拒绝采用，不偷偷补造来源。

Tests/Result：Windows11/Python3.13完整1017项无失败（2既有符号链接权限跳过），5新unit通过；实际PG双Scope当前Session/CSRF/License/Root/pair、并发同key一个首申请/相同原响应，异reason同keyCONFLICT_IDEMPOTENCY。真实技术ack使Job CANCELLED后仍重放首次CANCEL_REQUESTED（八表无写），新keyCHECKED保原actor/time/reason。通过真实Submit新建PENDING即刻取消，已真实发布SUCCEEDED取消检查不撤回Result；裸技术取消无首Audit拒绝。真实Audit与Job写后异常、后验授权拒绝时整个取消/Audit/收据回滚；跨Scope与CSRF/License拒绝无写。原发布空/260回归成功。ack仅测试首次响应漂移，不冒充系统取消Owner或取消完成审计证明。

开发wheel 597358 bytes，SHA256 `06c8d21af71a3a8fb1a45448b20809e4f0cf4fddaa443c58517dca985ca0f378`，仅开发库不是安装包。无Migration/API/依赖，head0042不变，无生产升级；撤未装配申请服务保留历史，禁止改写/删除首Audit/首申请/成功文件。

Known issues/Next：内部申请已验证，公开取消HTTP/If-Match尚未实现；后台受控SystemActor确认、过期恢复、取消提交确认丢失及执行器/claim主循环待。下一项P04-P03实现依据原首申请Audit的安全确认，正式材料/三平台/质量/Gate/完整Scope可用安装包仍待。
