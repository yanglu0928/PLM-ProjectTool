# P04-P03-P04-P03 后台安全取消确认

日期：2026-09-26；状态：INTERNAL_ALIVE_ACK_PASS / EXPIRY_RECOVERY_PENDING。

编码前检查：Phase2/P04-P03-P04-P03；输入CR-AUD-004/ADR011，前置P02真实当前授权首申请历史/唯一USER Audit/原响应及Jobs当前活代ack已验。涉及Audit内部安全Owner、同Supervisor静止锁、owned Jobs ack、当前SystemActor和最小SYSTEM Audit，无Schema/API/依赖/权限扩张。

一个问题：同步I/O已返回且心跳实际结束→当前identity→原Root/acceptance/pair/真实CANCEL_REQUESTED首历史与唯一申请Audit→最小SYSTEM取消完成Audit→再次identity→owned同Worker/fence/alive Lease ack最后→同UOW commit。原User/申请者撤权或License失效仍不得继续业务，但不阻碍仅确认取消；不删除字节、复活终态、创造新申请或修改首reason/actor/time。不从裸技术状态或STALE猜完成。

验收：真实双Scope首Owner申请后用户/License撤权仍终止且唯一SYSTEM Audit、原历史/字节保留；当前Worker/fence/真实期限/首来源缺失/成功拒绝，Audit/ack写后及后验identity异常整UOW回滚，活心跳拒绝。到期恢复/确认丢失/执行器接线留后续，不将取消申请等同停止外部I/O。

Changed/Files：`worker_cancel.py`仅确认真实活代、4新unit与独立实际PG验证脚本；复用现有owned first-request/ack/SystemActor静止锁，不读正文/文件，不新增User/Role/License恢复面。必须可信执行器同步I/O先返回、使用同Supervisor，锁非全局强杀。

Tests/Result：4新unit/Windows11 Python3.13完整1021项无失败（2既有环境权限跳过）。真实PG/临时Vault双Scope首先通过实际申请Owner写首USER来源，再受控SystemActor同UOW取消完成；真实User停用+License拒绝仍禁止capture但允许ack，唯一SYSTEM事件保持Root original actor/trace/Scope。实际Job CANCELLED/Lease RELEASED/Attempt JOB_CANCELLED完成绑定，原actor/time/reason与private stage字节/Result/File不变。真实Audit插入后故障、ack全部写后故障、第二identity来源故障整体回滚；错Worker/fence/Root、已取消/已真实发布成功、首Audit缺失、真实两秒到期均拒绝六表无写。活心跳拒绝unit通过；本轮未新增真实ack/publish竞态矩阵，不扩大原发布fixture竞争证明。原发布空/260及取消优先/发布优先底层回归成功。

开发wheel 599087 bytes，SHA256 `7bfb8b49cb40374bfe8d002b06b058c9972cf0585da8732312cd697a33b70fae`，非可用安装包。无Migration/API/依赖，head0042不变，无生产升级，撤未装配Owner保首申请/Audit/字节，不复活终态。

Known issues/Next：真正过期租约必须走单独系统恢复，不能调用活代ack冒充；确认丢失原源核验、执行器/主循环/公开HTTP还未接线。下一项P04-P04到期取消恢复及边界；正式材料/三平台/质量/Gate/完整Scope安装包未完成。
