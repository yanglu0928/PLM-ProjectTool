# AUD-03-A06-A04-P03-A02-P02：Document owned元数据Port

日期2026-09-26；Phase2；输入0040/CR-AUD-002/ADR010、已验P01存储；编码前DEC207。结果：限定caller-UOW元数据/真实文件验证PASS，完整Worker发布未完成。

## Changed / Files / Migration / API

Application提供精确RegisterAuditFile、AuditFileMetadata、AuditFileMutation与公共Protocol，绑定export/原User/Scope/FileID/完整内容Hash与Size，返回无Locator/绝对路径的状态/版本/首次来源及可用事件Ref。DTO/字段/事件是内部事实坐标，不是实际Export根/文件或权限凭据。

Document owned Repository只读写自己的FileObject与StateEvent；私有final Locator由Document生成，固定显示名/MIME/PERSISTENT用途。首次STAGED INSERT ON CONFLICT后原行锁重核，冲突/重放不改原来源；必须存在单一登记事件和实际匹配Actor/Trace/时点，手工合理元数据而无来源拒绝。当前get持File共享锁到caller事务结束，mark_available持排他锁；Hash/Size/Scope/Owner/创建Actor/定位完全匹配。

可用转换只有STAGED v0→AVAILABLE v1，实际clock时点与状态事件一致；已AVAILABLE重复返回原状态事件不再写，RESTRICTED不复活。结果DTO类型/版本/UTC aware时间/事件形状重核。只有AVAILABLE元数据不等于Audit成功结果或可下载。FAILED/CLEANUP_PENDING/REMOVED不由此成功Port接受或恢复，后续单独清理/失败状态流程，不伪造终态。

无自建UOW/commit、自鉴权、长文件I/O或直接Audit/Jobs表操作。真实当前Root/acceptance/pair/capture/权限/Lease、事务外实际字节证明和同事务Audit/Job/结果发布由可信Owner负责；本项实际caller fixture追加真实Audit以验证事务边界，不宣称生产编排已装配。无Schema/API/角色/依赖变化，head0040不变；默认导出POST/下载仍关闭。

## Tests / Result

- 实际PostgreSQL18临时库与临时文件两Scope：真实staging/Hash读回→元数据→不可覆盖提升→AVAILABLE；新trace重放保持原事件与注册trace、无重复Audit；原Owner/Actor/Scope/Hash/Size/用途/缺登记来源拒绝，版本bool拒绝，已限制不可复活。合成Export UUID无真正导出根，明确非权限/Lease证明。
- 真并发首次登记/可用转换各一次变化及来源/Audit，不拿顺序模拟并发；实际共享读锁阻止另一连接FOR UPDATE到事务结束；post-Audit fault整UOW回滚File/state/Audit，最终文件仍存在但元数据STAGED不返回成功，恢复后当前caller重新转换。并非真实进程崩溃/unknown commit或完整Job结果发布竞态验证。
- 后端902项无失败、2项Windows符号链接权限环境跳过；5项新增请求/嵌套再验证/结果类型版本/缺事务/精确class等unit。0040旧数据/Schema/误绑/历史down与普通上传提交真实回归PASS。
- 开发wheel 0.1.0.dev0 PASS，548824 bytes，SHA256 `8fe315ea32d3551d6ae4197fbed1d21983060d659df789c4f057733abf93603e`，非正式可用安装包。

## Known Issues / Next

接入Audit持久尝试/唯一结果Schema与source/manifest/Job generation固定绑定，随后真实Worker当前权限/Lease/取消下原子发布与下载再授权/HTTP；普通FileObject无通用公开入口。私有状态事件来源不是客户确认或当前许可。正式SystemActor/License信任、真正Job/结果/权限竞争、质量Gate3、三平台/目标账户/性能/发行未关闭。
