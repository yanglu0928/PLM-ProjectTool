# AUD-03-A06-A04-P03-A04-P02：真实私有文件渲染

日期2026-09-26；Phase2；编码前检查PASS；限定私有渲染阶段验收PASS。

- WBS/输入：Gate2原64cdf09、CR-AUD-002/ADR010、0042；真实Worker计划、canonical renderer、Document staging/hash公共Port及Jobs完成Port已验证并同步。
- 涉及模块/实体：Audit own Root/Acceptance/Capture/Plan/固定Member，Auth/Project/Jobs公共Port；Document仅公共Storage坐标/Hash，不访问其私有表/路径。
- API/权限：无公开HTTP，POST关闭；每阶段当前User/License/PM成员部门或DEP Admin，原Root/pair/有效Worker Lease重核；归档仅既有维护例外。Context/Hash不是跨事务授权。
- 实施：短UOW准备原计划/完整capture；固定成员按position最多128条页取，每页当前权限/原pair/Lease前后验并结束交易，然后yield给renderer写私有staging；无文件写/hash/fsync在数据库UOW内。完整成员/文件digest、flush/fsync后独立读回Hash，再短UOW最终权限/Lease/完整封口重核。
- 验收：真正submit→claim→capture→plan→暂存文件，双Scope empty/nonempty/多页/中文存储根/新事件不进原集合；观察写/verify时无DB UOW；页间撤权/实际取消/到期/源失败/磁盘短写等失败无FileMeta/结果/Job成功，部分保持私有、不删或换原路径；新代次独立file；旧流程及全集回归。
- 风险/回滚：不提升、不写FileObject/结果/Job完成/发布Audit；不宣称可下载或正式身份。无自动物理删除；同代部分/完整staging不覆盖，失败交给上层Job重试/新generation。无心跳调度/20并发/性能承诺，长渲染若到期拒绝，后续协调器实现租约续期。
- 预计文件：paged Source Port/Adapter、Worker render与DTO、准备计划公共内部复用、unit/实际PG+临时文件verifier、决策/本进度/CR/STATUS/CHANGELOG。
- Migration/API/依赖：无，head0042；撤代码保留计划/私有失败文件和全部历史，真正发布/恢复后续验收。

## Changed / Files / Migration / API

新增AuditRenderContext/StagedAuditExport及WorkerRender，准备阶段复用已验证User-first原Root/pair/当前Lease/固定capture/计划；paged Source公共Port/own Adapter显式17安全列，封口集合按position最多128条/页；每页前后权限/Lease及原generation重核，UOW结束后yield供canonical renderer写文件。完整成员Hash/数量、规范manifest/file digest经renderer复核，storage close/flush/fsync后独立reopen/hash，再短UOW完整capture/权限/Lease末验。

Context/Hash只作不可变一致性DTO，不当授权；Staged DTO再次核exact来源/坐标/content/规范manifest。不提高/改写FileObject/结果/Job终态、不生成发布Audit、不提升final。只准备/页取/尾验DB阶段40P01限三次，不重试整个文件I/O；同代已存在部分或完整文件拒绝覆盖，失败Job协调/新generation以后接线；保留历史和私有失败文件。无Migration/API/依赖，head0042，旧iter_events/计划行为保持。

## Tests / Result

- 实际PG18 UUID库+真实临时文件：Session/CSRF submit/原accepted Queue/claim/固定capture/当前User/PM或Admin/Lease/plan→storage staging，PROJECT/DEPLOYMENT均empty及260条三页[0,128,256]，实际canonical JSONL/hash/size/完整manifest精确、晚到匹配事件不进入原集合、中文临时存储根通过。安全投影无hint/路径，DTO不返回locator。
- 观察Worker所有UOW进入/退出及每次actual write/actual fsync/verify，文件操作时计数为0；source页取时为1。数据页commit后才yield，不以无锁长事务替代短事务；没有发布DB行或final文件。
- 实际128条页写后enabled User撤权、原Job公共取消、真实Lease到期，下一页拒绝，只留128条私有partial；Source失败/short page同样拒绝；合成OSError ENOSPC写失败（不是实际满盘）拒绝且不发布，标准化错误不回传内部内容。独立文件hash后合成License撤销最终拒绝，完整暂存仍私有。
- 同代再次render不覆盖原暂存，原字节不变；实际过期接管，新代独立file_id，旧partial字节保留，新文件完整260条/同capture，未用旧Worker或新事件伪造新源。
- 930项后端无失败（2既有Windows符号链接权限环境跳过）；新增4项Context/DTO/页大小exact type和依赖/坏命令不触及file；真实Worker计划、原canonical renderer/固定源、结果Repository真实回归PASS。
- 开发wheel0.1.0.dev0通过，563114 bytes，SHA256 `fab5dd9d4e8085042204362538b6f25e3835d0753ab6f0377496578473d3f1db`，不是可用安装包。

## Known Issues / Next

License仍合成Guard；未生成正式SystemActor或生产密钥。无final提升/元数据/成功结果/Job完成/发布Audit/HTTP下载；无心跳调度、极限空间/20并发/性能及目标账户ACL/三平台证明。下一项P03-A04-P03接真实Document元数据/提升/own Result/发布Audit及Jobs caller-UOW完成，当前权限/Lease/取消每阶段再核，随后受控恢复与下载。当前POST仍关闭、Gate3/质量/正式信任源/完整Scope/程序包交付未完成。
