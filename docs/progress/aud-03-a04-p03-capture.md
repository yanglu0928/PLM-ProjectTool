# AUD-03-A04-P03：实际单statement采集与固定集合重放

日期2026-09-26；Phase2；0.1.0.dev0；结果TRUSTED_STORAGE_CAPTURE_PASS。真实权限/License/Lease/文件交付/导出HTTP未完成，不是发行/Gate PASS。

## 编码前检查 / Changed / Files

任务限定Audit owned来源选择/封口/重放。输入冻结API-02/API-03、A01设计、A03Spec、CR-AUD-001、P01摘要及P02实际0037 Schema；前置满足。模块Audit，固定Export/capture；无迁移/API/角色/依赖变化。实施前DEC-20260926-193固定服务器V1安全上限100000及超限整事务失败、不截断。后续改上限须新政策版本并保留旧集合规则；上限不代表性能通过。

新增capture_contract.py、capture_repository.py、7项unit与隔离验证脚本。可信调用方事务入口，不创建UOW/commit/rollback/鉴权/许可/租约；真实调用方必须先核验当前事实且锁持至事务结束。只接受固定Export坐标，匹配原Actor/Scope/Project是绑定不是权限证明，默认/显式平台均未装配这个存储入口。固定READ COMMITTED与PostgreSQL；未知版本、错误原Spec指纹或Scope绑定安全拒绝。

根FOR UPDATE锁后从原持久Spec单条data-modifying CTE INSERT SELECT固定时间/UUID降序集合，全部六筛选与Scope/Project、起止窗口来自服务器持久意图；使用同statement的captured_at，不声称请求时点快照。取最多100001成员，超过100000抛错且不seal，调用者整UOW回滚；没有截断成功。随后数据库统计安全坐标/摘要，0037 seal触发器独立重验；不把分页或客户端给定成员作为新capture来源。

有seal仅重验原Spec/版本、Scope/源time/全筛选、完整count/order/hash与同一capture xid，返回原不可变metadata，不重新选择现在的合法事件。空集合有固定摘要和时点。read_capture提供同样可信再验，不读Session/路径/正文，返回metadata不是授权或Job成功证明。Source已追加不可变，读取同一源不会把新事件加入固定集合。SQL摘要/排序仍O(n)，100000行/20并发/P95未验证。

## Tests / Result / Migration / API / Compatibility

Win11/Python3.13后端823项无失败，2项既有符号链接环境跳过。7项新增unit覆盖SQL形状/全筛选、错误请求/阶段先拒绝、根不存在/绑定/锁、isolation拒绝、持久Spec/全版本指纹重验、seal数量/摘要/顺序Scope异常/xid/时间、最小冻结metadata（mock仅存储边界，不冒充真实权限）。

独立UUID PostgreSQL库实测：实际引擎记录第一次采集只有一条成员INSERT SELECT，重放/读取不再执行采集；迟提交的历史时间事件在采集时不可见，commit后亦不进入原集合；后续回填/新事件被原集合排除，新Export可以独立采集新集合。PROJECT/DEPLOYMENT、全六筛选及单项错筛选空集、Python规范摘要与SQL一致；调用者不commit回滚成员与seal；成员已写后seal故障整UOW回滚可安全重试；测试小上限超限不封口/不留成员/不返回截断成功。真实同一重试调用者阻塞根锁，期间新增事件，第一次提交后返回原seal metadata。原Actor/Scope错绑定与形状合法但指纹错误意图拒绝。所有库finally清理，无客户资料。

0037/P02隔离Schema、源关联/同事务seal/并发/历史down保护回归PASS。本项无新Migration、公开API/角色/依赖变化；无数据库升级动作，可撤未装配存储代码不删历史。开发wheel PASS，SHA-256：`f9c7c94b6be3e65d6b7d71073a7c0431d4136f475ae7af8f61af1bb05bfe899d`，非正式安装包。

未运行100000行/20并发/性能、实际当前Actor权限/License/租约、文件/磁盘/HTTP/UAT验证。Server2025未验，Debian13暂缓但正式目标保留。Review真实Owner/质量失败、正式发行账户材料、Gate3/完整业务Scope/可用包仍未完成。

## Next

AUD-03-A05：真实受权请求/幂等/最小ExportRef Job enqueue与Audit同事务编排，先核对其当前权限/归档维护/公共Job写Port前置；缺口拆任务并记录，不把存储入口直接公开。随后Worker当前权限/Lease/取消/安全文件交付。
