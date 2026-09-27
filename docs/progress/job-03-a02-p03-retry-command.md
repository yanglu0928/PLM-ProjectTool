# JOB-03-A02-P03：受权原子用户重试

## 结果

- 内部AuditUserRetryService/严格Request及Audit owned generation Repository完成；无Migration/API/权限/依赖变化，head0045。当前Session/CSRF/PM或Admin及License同UOW先核，完成receipt后最后再核，确保后置拒绝回滚。
- 真实双Scope第三Worker失败后，新Export/Job/Outbox/两Audit/Acceptance/lineage/receipt原子创建。同Key两并发一致且仅一新generation、trace变化重放无写；异expected_version同Key冲突，新Key明确另一代。新Job实际Worker capture/render/publish成功，历史重放仍首次版本0/同Job，旧FAILED整行不变。
- 错版本/Session/CSRF/Scope/角色/Admin项目绕过/License均拒绝，postAudit/lineage/receipt写后故障十五表全部回滚；原Worker退避/故障/文件发布回归通过。
- 首轮CSRF错误码预期更正为实际内部AUTH_ACCESS_DENIED，没有放宽Auth。复用P02观察器第二Scope出现第一Scope合法lineage，原全表零断言改为当前source无generation并保完整快照不变，不伪造全库零记录。
- 新6unit/1229后端无失败/2既有权限跳过；开发wheel677500 bytes，SHA256 `616968e1b89c9ad506035fe1037abe1155b8d90b1c47acec01ecfe78a7937e08`，不是完整可用安装包。数据库/用户Session/文件/Worker实际，正向License仍合成；生产材料/其他Owner/三平台/性能/Gate待。
- 内部命令PASS；公开retryable仍False、HTTP未挂载。下一P04冻结Job retry HTTP及权限/并发/异常矩阵，再P05 Windows和安全metadata retryable接线。撤未挂入口可回滚，历史不删。

2026-09-27 / Phase2编码前PASS：0045 lineage及真实第三Worker失败原源已验，输入CR-JOB-006/冻结API-03；只Audit internal command/repository，尚不挂HTTP/改变公开retryable。现Session/CSRF/License和AUDIT_PROJECT_EXPORT PM/DEPLOYMENT Admin逐次同UOW授权，强版本/原源不让泛Job权限代替。

DEC283：查原Root无锁hint后当前授权，再Root锁、receipt（原Job/原queryhash/expectedversion指纹）、原pair/第三失败源；新Export同spec、新Job+Outbox+原提交Audit/Acceptance+retryAudit+immutable lineage+receipt同事务，最后再授权，不复活旧Job。相同Key重放最初新Job及版本0，即使新Job已结束；仍核当前权限/源、禁止自动补旧receipt。不同Key明确新generation，同Key异条件冲突。

验收真实双Scope三次Worker失败后新generation、同Key并发唯一/旧Job不变/新Worker实际成功后历史重放、错误版本/CSRF/角色/License/跨项目拒绝、Audit/lineage/receipt写后故障整体回滚。无Migration/依赖/API新增；回滚关未挂入口保历史，正式材料/完整Owner/三平台/性能/Gate待。
