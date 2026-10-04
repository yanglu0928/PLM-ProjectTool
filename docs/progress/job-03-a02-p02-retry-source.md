# JOB-03-A02-P02：Audit原失败与Jobs技术来源

## 执行结果

- Jobs owned只读Service/Repository及严格最小failure DTO、Audit owned原Acceptance/唯一失败事件Reader完成；无Migration，head仍0045，无公开API/权限/依赖变化。Root→原pair→Job/Attempt/Lease锁与现流程对齐，Port不自产事务/commit，不返回worker/fence/payload。
- 真正运行原Worker双Scope5/15秒退避、实际第三次AUDIT_UNAVAILABLE→FAILED，再验证真实原Job版本、第三Attempt/RELEASED Lease及唯一SYSTEM原失败Audit；错版本/类型/actor/Job-Event pair与PENDING拒绝，十一表读不写。
- 第二轮加入真实同UOW重复失败Audit并验证歧义拒绝、rollback不留事件；第三Attempt窗口外事件拒绝；原Worker故障回滚/权限/License/identity及文件发布回归保持通过。新7个unit严格DTO/防错误Port/安全异常，全部1223后端无失败/2既有权限跳过。
- 开发wheel674156 bytes，SHA256 `ebf0c662ee79380a259fcf4bb3b727016794deb7f1af8ae6c7e1a2cdf0833724`，非完整可用安装包。
- 内部来源验收PASS，不意味着当前用户Auth/CSRF/License写权限或生成新任务已完成。没有改公共retryable=False，用户retry仍不可用；正式账户/三平台/性能/其他Owner/完整包/Gate待。
- 下一P03先当前授权+不可变generation Repository及同事务Receipt/Audit/原强版本命令，再HTTP和Windows接线；历史终态与已发布文件不变。

2026-09-27 / Phase2编码前PASS，仅内部只读来源Port。输入CR-JOB-006/0045/原Worker固定5/15秒第三次AUDIT_UNAVAILABLE失败；前置Schema完成。涉及Audit/Jobs原Root/Acceptance/Job/Attempt/Lease/AuditEvent，不新增Migration/API/权限/依赖。

DEC282：调用方须先当前授权并锁原Audit Root，再find原pair，Jobs owned核原owner/type/actor/trace/Scope/payload/expected_version和终态、第三Attempt/Released Lease及既有retry transition。向Audit仅返回安全坐标/版本/时序，不传worker/fence/payload。Audit own原失败唯一SYSTEM事件以精确原trace/Scope/原actor/Job/第三Attempt时窗及AUDIT_UNAVAILABLE核对；历史SYSTEM来源不要求当前worker identity重读，旧immutable事件不可变且不授当前业务权。技术Port未注入Auth/CSRF/License，不能公开。

验收真实原Worker双Scope定时重试第三次FAILED经Port核验、错版本/原源/非失败和坏source拒绝且不写；DTO严格类型/时间/次数，原Worker回归/全后端。P03再当前权限+receipt原子命令；本分项不能把Job retryable公开改true。回滚撤新未接线Port保历史，其他Owner/完整Scope/Gate仍待。
