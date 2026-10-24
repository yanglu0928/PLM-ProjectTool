# Review 读取授权设计 V1

2026-09-26；RVW-01-A04；来源冻结 API-02 REVIEW_GET/角色矩阵/API2-R02/R05，AF-02 ProjectAuthorizationService/ReviewService、DM-02 Review、CR-RVW-001；只细化内部实现，不修改冻结 API/权限/Schema。

## 两层授权和返回范围

读取顺序：有效 License → 活动调用方事务 → 当前 Session/User → 锁定 Project/成员/部门当前事实 → PROJECT Review 身份 → 主题 Owner 身份权限 → 固定轮次（如请求）及该固定版本权限 → 返回不可变内部 DTO。Actor 仅从 Session；Project 从受控查询参数；不接受请求声明角色、Owner、已批准证明或调用方提供的身份快照。

REVIEW_GET 项目角色候选为 PM、IM、CM、CustomerMember；这只是 Project 层资格，不代表主题权限。Archived Project 允许受权只读；成员 SUSPENDED/REMOVED、部门 INACTIVE、失效 Session 拒绝。DeploymentAdmin 未成为有效 Project 成员时不能读取；GLOBAL 必须使用独立明确策略，本项 PROJECT 服务不提供 GLOBAL 回退。

Subject Owner Port 必须在同事务重读并保持权限事实锁，返回绑定当前 actor/project/subject identity、固定 version（若有）的明确读取授权结果；缺 Owner、None、错误 Actor/Scope/Subject/Version、非预期 DTO 一律拒绝。不将 assigned reviewer 身份或旧 APPROVED 当当前主题访问权。Owner 返回的授权只是访问证明，不是当前 Evidence 资格、正式客户批准或可放行 Gate 的证明。

身份授权之后才能加载/返回本轮 Assignment、Decision/comments、refs；读取历史轮次时还需 Owner 允许该固定旧 Version，不能只凭当前主题权限读取已受限版本。内部 fixed DTO 含摘要/历史观测，不是公开 ReviewView；后续 HTTP 必须显式白名单映射，不自动序列化基础设施字段或主题正文。Evidence/Trace 的受权 Viewer 仍需各自重新授权，不因获得历史 ref 自动可读来源正文。

## 并发与锁

统一相对顺序 Project 当前事实 → Review 身份 → Owner 身份/版本 → 固定 Round；读取固定轮次需先锁 Review，稳定定位 version，再调用 Owner 保持固定版本授权锁。后续写服务必须遵循同一相对顺序，实际 Owner 适配前不得声称已完成跨模块锁/死锁验证；现有 0034 受控脚本先 Review 再 Round。

事务结束前项目撤权/Owner 权限变化不能使当前快照与授权漂移。Port 对象形状校验不等于真实授权实现，生产装配不得用恒真适配器、任意代码动态 Owner 注册、客户端 type→module 或已持 UUID 替代真实事实。

## 实施拆分与验收

RVW-01-A05：新增 Project REVIEW_GET 锁读策略与内部服务，Session/Project/License复用既有真实组件；Owner 提供窄类型 Port，仅合成实现验证协议/拒绝，默认无适配，不挂载 HTTP。单位矩阵覆盖四角色、跨项目/错误证明、未知 Owner、旧版权限、异常脱敏；隔离数据库核验真实 Session/成员撤权锁、历史保留和查询无写入。完整真实 Owner 验收待各业务模块实现，此部分不能标通过。

后续按 WBS 完成 Owner 可用性、读取投影与 HTTP，以及独立的创建/送审/决定/撤回/审计幂等。Owner 送审锁必须阻止内容修改和替代 Draft，审批完成仅通知 Owner，Review 不越界改主题表。

## 兼容与回滚

无 Migration/Breaking API/新增角色或依赖。新增内部操作策略不装配路由；可停用服务回滚，保留 0034 历史。真实 Owner 缺失是公开接线阻塞，不阻塞独立内部协议验收，也不移除原业务 Scope。
