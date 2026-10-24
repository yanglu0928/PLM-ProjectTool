# JOB-02-A04：冻结项目取消HTTP

2026-09-27 / Phase2，编码前检查PASS：A01～A03/0044、原当前授权/来源/版本/收据快照已验；输入冻结API-01/03、原64cdf09保留。单问题：可选项目 :cancel HTTP和显式Owner分派；不新增Admin取消、不装配默认或Windows生产模式。

Application命令严格JobId/ProjectId/token/CSRF/trace/原因/expected_version；先当前License与Session-CSRF，Jobs owned只读hint选择显式(owner,type)注册，Scope/path必须PROJECT一致，无未知Owner回退。只读UOW关闭后调用Owner，Owner必须在真实写UOW重新授权并验证Root/acceptance/pair/版本；hint不是授权/锁，不把前次Session当写许可。当前Audit Adapter调用原request_job，结果必须严格job绑定且首次version非None。

实施/Files：Jobs cancel_request.py/可选api/cancel.py、Audit job_cancel_adapter.py、create_app可选参数；5单位/5Contract、validation/job-02-a04-cancel-http真实验证及接口文档。无新增Schema/Migration/权限/依赖，仍需0044。SESSION错误按原Auth语义映射：ACCESS_DENIED为CSRF，SESSION_EXPIRED为401，其他不可用为静态503。

Result INTERNAL_PASS：Windows11/Python3.13.15后端1177项无失败（2既有账户权限跳过）。真实PG-ASGI原Session-CSRF/License/Audit Owner，PENDING首次取消v2；RUNNING同Key两个HTTP并发仅一次请求Audit/首次结果相同，实际Worker确认后GET当前CANCELLEDv3，重放仍首次CANCEL_REQUESTED/v2，十一表无写。实际旧版本/改同Key版本/跨Project/IM他人/Admin项目/CSRF/Origin/未知Session/License/停用后重放/未知Owner/旧None快照均拒绝无写。实际快照insert后故障十一表回滚；分派后Owner写事务前实际停用用户，Owner再授权拒绝，无取消写。最后原请求可成功，未遗留eligible任务干扰原fixture。

原A03真实空/有数据up/down/up、快照来源/不可变/含历史降级拒绝/首次v2与实际Workerv3/回滚，以及两脚本内原publication双Scope空/260行真实文件/当前权限/Lease/取消-发布锁竞争回归通过。开发wheel651760 bytes，SHA256 `3c669213717cd528d3ffe3fce68594d5302772e67e4c919fe7290265370d9dab`，非完整安装包。

失败/修正：真实组合测试最初预期缺Admin取消为404，但同时挂原Admin GET /jobs/{job_id}的动态匹配导致POST405；已确认没有Admin POST路由并精确修正组合测试预期405（只挂取消Router的Contract仍404）。不新增fake Admin route、不移除安全用例，不改变取消许可。前文“Admin404”是未挂GET模式，组合行为以此为准。

Known Issues：Windows生产模式尚未挂取消；仅Audit Owner、其他Owner/列表/重试需求保留，正式信任/账户/性能/三平台/监听服务/UI/Gate待。Next JOB-02-A05：仅Windows显式write挂项目取消，默认/login/readonly未提供写；已有GET时未支持POST可以405，不能以期待404新增Admin/关闭stub。撤接线保历史，无本轮生产操作。

Router可信Host/Origin、单Cookie/CSRF/Key、强If-Match；8192-byte UTF8严格JSON只reason字段，未知/重复字段拒绝，客户端不指定Owner/export_id/Scope。当前Session先验，200只job_id/state/changed/etag/status_url与当前trace；强ETag来自首次快照而非当前查询。重放state+etag不漂移，实时另GET。状态/错误/static异常不泄露原因/路径/lease/SQL。default404，Admin404，旧None收据缺版本失败关闭；权限不可因细粒度读取放宽。

涉及Jobs Application/API、Audit Application Adapter、可选create_app、测试/文档。无Schema/Migration/依赖/角色/技术栈变更；需0044。DEC-268先记录。Rollback撤可选Router/分派接线保历史。验收：默认/未登记Admin关闭、严格请求与428/400/409/权限/安全错误/None快照拒绝单位及Contract；真实PG-ASGI Project当前Auth/Creator-PM/Audit原取消与Worker确认后首次重放v2，失败/冲突/跨Project/未知Owner无写、原source写后故障回滚；全后端/原版本/发布回归。正式材料/完整Scope/性能/三平台/Gate仍待。
