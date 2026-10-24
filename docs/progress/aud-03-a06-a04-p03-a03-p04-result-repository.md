# AUD-03-A06-A04-P03-A03-P04：结果Repository与规范复核

日期2026-09-26；Phase2；编码前检查PASS；限定结果Repository验收PASS。

- WBS/输入：Gate2原64cdf09、CR-AUD-002/ADR010、0042及真实Worker计划、已有canonical renderer；前置已验证并同步0d7471d。
- 涉及模块/实体：Audit own Root/Acceptance/Capture/Plan/Result/发布Audit；无跨模块私有表调用。
- API/权限：仅trusted caller-UOW Repository Port，禁止自开UOW/commit/文件I/O/授权；返回不是Lease/文件可下载证明，Owner必须先验当前权限、原Queue/Job、Lease、真实文件和Document公共元数据。
- 实施：抽取renderer纯canonical manifest构造，保持原字节；结果DTO严格UUID/bytes/hash/size/version/UTC复核；写与读均实际own Root/accepted/capture/plan/source Audit全绑定，原file_id不换、canonical bytes逐字节重建。
- 验收：真实双Scope empty/nonempty源/renderer→record/get、原计划与来源/完整filters/hash/字节篡改拒绝；重放/并发单结果保持原Audit；caller后置失败整UOW回滚，数据库无私自commit；读无写/缺结果无修复；914项基线回归和0042与Worker验证。
- 风险/回滚：无Schema/API/依赖/升级；撤代码保留0042及结果历史；Job/File/SystemActor source fixture仍合成，不冒充真实发布。下一项Jobs caller-UOW完成及真正文件Worker原子编排。
- 预计文件：render_export helper、result DTO/Port、own Repository、unit/实际PG verifier、本记录/决策/CR/STATUS/CHANGELOG。

## Changed / Files / Migration / API

新增RecordAuditExportResult/AuditExportResult/Mutation及caller-UOW Repository Port，exact UUID/type/bytes/32-byte SHA/128MiB/8192bytes/UTC约束及被修改nested DTO重核。SqlAlchemyAuditExportResults record/get均重读own Root完整Spec、真实accepted来源、capture完整统计、不可变plan及实际own发布Audit字段/时点；同Root锁序下重放原完整结果，不替换原Audit、计划或内容；并发串行后只有一次changed。get缺结果/缺Root返回None，不造来源或修复；结果行转DTO后仍重建并逐字节比较规范manifest。

renderer抽取纯build_audit_export_manifest：保持既有C排序紧凑UTF8/UTC微秒/LF规范bytes，与独立0042 SQL重建一致；空文件与非空最低大小/hash形状及有界清单；无文件存在/内容真实性或授权含义。own实现不commit、自开UOW、文件I/O/调用外部服务或访问其他模块内部表，publish Audit仅显式安全列。无Migration/依赖/API/升级，head0042不变。

## Tests / Result

- 实际PG18 UUID临时库，双Scope empty/nonempty且完整filters，真实own Root/acceptance/capture/source/plan、实际renderer内存bytes、实际own发布Audit→record/get通过；canonical/hash/字节数精确，重放原结果与原Audit、读无写；真并发一changed且相同结果。
- forged plan/file/job/token/worker/time/memberHash、清单空白/Scope/正文以及替换发布Audit拒绝，失败前后全部Audit/Job/Document/own表快照不变；caller同UOW实际append Audit→record→故障后Audit+结果全回滚，原plan/capture保留。
- 实际结果行读取fixture改file/plan/Audit/byte_count/time以及Hash正确但非规范清单，own _view验证拒绝；这是读适配器防错误输入fixture，未关闭/绕过生产触发器修改DB历史。
- 919项后端无失败，2既有Windows符号链接权限环境跳过；新增5项exact DTO/被改nested/无活动交易安全拒绝及manifest helper；0042 Schema/完整规范bytes、真实Worker计划、P01固定源renderer及Document实际文件元数据/Audit回滚回归PASS。
- 开发wheel0.1.0.dev0通过，559452 bytes，SHA256 `337a3afa04cca1ad941c1b02a247b217dc6917df7aa02299c89b3ab1e558a134`，不是可用安装包。

## Known Issues / Next

Job/Lease/File/SystemActor refs及trusted caller合成，物理文件/当前Actor权限/有效Job/租约/正式SystemActor/真正Job SUCCEEDED原子发布不是本Port证明；内存manifest不是客户授权或下载凭据。下一项AUD-03-A06-A04-P03-A04-P01 Jobs caller-UOW当前Lease完成公共Port，随后真正文件Worker短事务组合、发布与下载再授权；POST仍关闭，正式信任源/质量Gate3/三平台/性能/整体程序包和完整Scope均未收口。
