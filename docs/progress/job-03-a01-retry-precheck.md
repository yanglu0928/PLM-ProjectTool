# JOB-03-A01：受控重试前置核查

2026-09-27 / Phase2；输入冻结API-03 Job retry、DM-05 Job终态/新generation、0044、当前Audit/Document原源Port。只核查Schema/实际运行拒绝，不实现新重试命令；当前重试没有前置可用Owner事务及持久lineage，不能直接开放HTTP。

编码前：涉及Jobs/Audit/Document，现Job/Attempt/Lease/Outbox/Export；权限为当前Session/CSRF/License及原Owner业务规则；验收需新Job/原Job不可变/原源归属/当前授权/If-Match/同Key原响应/同事务Audit，未知Owner不能复制payload。

静态证据：

- API-03明确202新JobRef，引用原Job/新幂等Key，不复活终态；API Runtime源Job字段/持久retry lineage/用户重试Receipt及Owner受控入口均缺。
- JobLeaseService.retry_or_fail仅有效RUNNING Lease/fencing、原Job有界RETRY_WAIT或FAILED，是Worker内部重试，不是终态用户重试。不得复用成公开retry。
- Audit enqueue按export_id固定唯一pair，重复原请求返回同Job/Outbox；原Acceptance/捕获/Render/Result固定原Job，一般复制payload无法生成可被现Owner证明的新Job。
- Audit/Document read Owner当前retryable=False；不凭FAILED猜可重试。Document实际Parser未实施且属于Phase3，当前不得伪造可重试结果。

前置结论：直接公开用户retry BLOCKED；不是整个目标阻塞。自主建立CR-JOB-006，先Audit新generation lineage/同事务原结果快照，再当前权限与失败分类、命令/HTTP及Windows接线。保留完整其他Owner/Outbox工作。新Schema必须ORM+Migration up/down+空/有数据升级及错误回滚。

## 实测结果

新增独立验收器复用P05真实两Windows Factory/临时PG/Audit实际发布与Doc提交：当前成功Job安全retryable=false；POST :retry未注册，实际405（GET-only动态路径匹配）而非假定404。原Audit owned enqueue同UOW返回相同原Job/Event，十八表无写；真实information_schema无预设来源generation字段/专用关系表。双Factory均通过，原混排/文件发布回归也通过。

首轮测试误判未注册POST应为404，实际405；只修验证器预期和注释，不改生产路由/权限保护。本轮无生产变化/新Migration/API，1214后端/2跳过及wheel666922为P05同版本历史，未重复全跑。检查工作完成，公开retry仍未实现，不把前置证据PASS当功能PASS。

JOB-03-A01为Job受控重试核查的内部执行切片标识，不新增冻结Scope。下一内部P01按CR-JOB-006先完成Schema/DTO设计及迁移评审再实施；新旧结果可追溯链与原Source/当前权限缺任一时不得开放HTTP。
