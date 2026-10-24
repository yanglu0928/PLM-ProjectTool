# AUD-03-A06-A04-P03-A03-P02：真实Worker渲染计划

日期2026-09-26；当前Phase2；编码前检查PASS（实施/验收尚未完成）。

- 输入基线：Gate2原冻结64cdf09、CR-AUD-002/ADR010、0041、当前权限/Queue/Lease公共Port。
- 前置任务：不可变capture、真实受理与Worker capture、0041渲染计划Schema已验证并同步。
- 涉及模块/实体：Audit own Export/Acceptance/Capture/RenderAttempt；Auth/Project/Jobs仅现有公共Port。
- API：无公开路由，无Breaking Change；POST仍关闭。
- 权限：当前User/License/PROJECT PM成员部门或DEPLOYMENT Admin；归档仅既有Audit维护例外。
- 实施：复用Worker已验证User-first授权锁序；RENDER仅读完整既有capture，不创建/重捕获；原Job/pair/current Lease后登记同代唯一计划并精确读回；结束前再权限/租约核验，commit前失败整体回滚。
- 预计文件：Worker应用编排、计划DTO/own Repository、unit及实际PG验证；本进度/决策/STATUS/CHANGELOG。
- 验收：双Scope、原代次同文件/新代次不同文件但同capture、实际并发、撤权/取消/到期/缺源/误绑及写后故障回滚；既有capture回归及后端全集。
- 风险：计划不是文件/发布/下载成功；同代部分写不能另配路径；真实License仍合成Guard；正式信任源、质量/发行Gate仍未完成。
- Migration：无；只使用0041；撤应用代码不删除任何计划历史。

## 执行结果

PASS（限定内部计划编排）。新增AuditRenderPlan/Repository Port和own SQLAlchemy实现；共享既有捕获Worker授权流程，捕获行为保持原样。计划无成功状态、不产生文件或Job终态。

### Tests / Result

- 实际PG18 UUID临时库，真实Session/CSRF submit→原Acceptance/Queue→claim→固定capture→计划登记，PROJECT/DEPLOYMENT双Scope通过；同代反复相同全部列、新事件不改变原成员、真并发唯一计划、新generation独立file且原成员摘要不变。
- 缺capture拒绝且不补封口、错误Job/worker、当前User/PM成员/部门/Admin撤权、归档维护与合成License拒绝；实际取消已有计划仍拒绝重放、删除真实原Outbox边后仍拒绝重放，所有拒绝DB完整快照不变。
- 实际插入后异常、合成Guard结束前拒绝、真实Lease结束前到期全UOW回滚；实际到期接管拒绝旧Worker。真实PG40P01写后死锁整UOW恢复及三次耗尽无残留通过；未知存储错误不盲重试/不暴露正文由unit验证。
- 后端912项无失败，2项既有Windows符号链接权限环境跳过；新增8项。首次4项unit因Mock缺assert_current spec失败，修复模拟配置后重跑全集通过；实际首跑因PG本地时区返回触发DTO UTC保护，Repository显式规范化UTC后实测通过，未放宽UTC约束。
- 既有真实Worker capture验证完整回归PASS，包括当前权限/源/租约、真实取消/到期、死锁、重放和单seal。
- 最终Port类型注解补充后全集912项重跑通过；开发wheel `0.1.0.dev0`成功，553210 bytes，SHA256 `c1d2e7dfd6e49eba2db1b466143244bdde638ed85c4aa33901b18466c6577202`；不是可用安装包。

### Known Issues / Next

License仍合成Guard，未供给正式SystemActor/目标账户信任源；无物理文件、成功结果或manifest持久Schema、Job完成/HTTP/下载/性能验收。下一项P03-A03-P03唯一不可变成功结果/完整manifest Schema，再真实文件渲染与原子发布。Gate3/质量/发行/完整Scope不缩减。
