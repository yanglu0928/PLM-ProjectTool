# CR-JOB-005：受权任务列表与安全分页

P05更新：两Windows显式运行列表完成内部验收，与详情共享Audit/Document原源registry；专用KeyRef缺失拒绝启动，原测试正向fixture明确供给新独立测试codec，不引入生产回退。1214后端无失败/2既有跳过、实际双Factory混合来源/权限/分页十八表无写及20旧验证回归、开发wheel通过。原冻结版本不改，无Migration；正式账户密钥供给/三平台/性能/完整Owner仍待，CR与模块整体不关闭。

2026-09-27 IN_PROGRESS；持续自主授权执行，Phase2/JOB-01-A05，原冻结API-03 JOB_PROJECT_LIST/JOB_ADMIN_LIST保持。前置：已验当前Auth/Project/License、Audit/Document原源与安全结果、0044；无Migration。

方案：同UOW锁当前Session/User/Project/Member/Department，明确JOB_PROJECT_LIST策略（四角色，客户仅自身原actor）。Jobs owned查询仅registry明确owner/type、安全Job事实、Scope/Project/actor及稳定created_at/job_id倒序keyset，最多200条候选；每项经原Owner真来源投影/重新读取一致性。RESOURCE_NOT_FOUND资源隐藏可跳过，但一次仅扫描page_size候选，不做无界填满；next是最后消耗候选而非最后可见项，允许空页继续。错误源/未知异常整页静态失败，不能标部分成功。

安全偏差：原系统HMAC明文base64游标能看到坐标，若列表隐藏受限条目，最后消耗位置可能包含不可见JobID。不能把HMAC当加密。本轮内部私有position不公开；公开HTTP前使用已有cryptography AES-256-GCM专用Job-list游标密钥、family/Session/Project/查询绑定，并验证错族/篡改/跨会话及恢复。此安全调整必须先记录，依既有持续授权执行；不复用Secret主密钥或别的游标密钥，不加新依赖，不改License。

当前registry只有Audit/Document，其他Owner未实现不得自动授元数据权；完整Owner/列表/重试/Outbox Scope保留。单项列表实现不能关闭整个Jobs模块或Gate3。公开分页页长不承诺填满，total_count未知不伪造。未来新增Owner明示安全Port后注册。

风险：多Owner锁竞争、当前权限变化、坏原源、稀疏页/新插入项；不无限重试/追扫、不保证跨页快照、不缓存权限。回滚撤新list Service/Repo/策略/游标接线，保旧详情和所有历史；无Schema迁移。验收：current role/actor/path/Admin隔离、稳定同时间戳分页/无重漏/隐藏候选前进/拒绝无写、严格输入/错误静态、实际PG与HTTP及Windows正式信任拒绝、全后端；性能/三平台另验。

P04更新：当前Service/keyset、AESGCM可选HTTP与Windows专用KeyRef/临时恢复已内部验证，实际Audit Worker文件发布+Document真上传在同库经当前Session/Owner registry混合列表/状态ref/相同timestamp/角色与坏源拒绝十八表无写通过。Windows列表运行装配仍待；完整Owner/性能/三平台/Gate不因局部内部PASS关闭CR。
