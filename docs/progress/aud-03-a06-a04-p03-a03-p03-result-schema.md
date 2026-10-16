# AUD-03-A06-A04-P03-A03-P03：不可变成功结果Schema

日期2026-09-26；编码前检查PASS；限定Schema验收PASS；实际文件/Job原子发布尚未完成。

- 当前Phase/WBS：Phase2 / P03-A03-P03。
- 输入基线：Gate2冻结64cdf09保留；CR-AUD-002实施前精化、ADR010、0041、规范JSONL/manifest renderer。
- 前置任务：真实Worker计划/固定capture通过并同步178b6c1。
- 涉及模块/实体：Audit own Result/Plan/Root/Capture/Acceptance/发布Audit；外部file_id opaque Ref。
- API/权限：无公开API，不授予任何权限或伪造运行SystemActor。
- 验收/风险/迁移回滚：见CR精化；实际空/旧库up/down/reup/parity、规范清单/来源/唯一/并发/不可变/down历史与表锁；Schema不能证明实际文件/Job/Lease/License/发布可用。
- 预计文件：0042、Audit ORM、migration/catalog unit、实际PG verifier、本记录/决策/CR/STATUS/CHANGELOG。

## Changed / Files / Migration / API

0042/ORM新增aud_export_results，Export唯一成功结果、独立file/plan/Audit Ref、file/manifest二进制SHA256及完整manifest_bytes。own Root→不可变计划/capture→真实own发布Audit字段/时点校验；SYSTEM形状与原actor/trace/Scope/purpose/jobs原Job RUNNING→SUCCEEDED来源匹配，actor非零。无跨Owner私有表读写/FK、API或依赖变更。当前Document/物理文件/Job/Lease与正式SystemActor真实身份不由这些引用证明。

manifest由own原Spec全部filter/version/capture/NEW内容元数据重建，C排序紧凑UTF8/UTC微秒/LF精确比较；8192字节、32字节摘要、128MiB文件上限、空成员空文件标准Hash及非空最低大小。结果UPDATE/DELETE/TRUNCATE全拒绝；原计划不猜回填；空表down先ACCESS EXCLUSIVE锁，任一结果历史拒绝，offline down无DDL；0001～0041不变，无生产迁移。

## Tests / Result

- 实际PG18 UUID临时库空up/down0041/reup与ORM parity；0041旧双Scope empty/nonempty plan、实际标准安全源/真实capture和旧DOCUMENT/File/Version逐字段up/down/reup不变，无结果回填。
- 真正renderer+own固定源生成内存JSONL/manifest，双Scope空及非空完整filters规范bytes通过；所有manifest顶层/filters逐字段篡改、缺项/额外项/重复键/BOM/空白/缺LF/大小/摘要拒绝。非空源伪空文件拒绝；这是来源与内存清单证明，不是物理文件证明。
- 错Root/计划/File/Audit Ref、UUID、时点、MIME、版本、内容Hash/size以及发布Audit的actor形状/原actor/trace/Scope/target/reason/状态/时点拒绝；真并发只一个结果、PK/不可变/delete/truncate、实际down竞争写锁与历史拒绝，失败后版本0042及全历史不变PASS。
- 后端914项无失败（2既有Windows符号链接权限环境跳过），新增2项Schema/offline检查。首次全集因机械补表清单丢失缩进失败，修复后重跑；独立unit外键解析缺表注册改为核对精确FK目标，保持own边界断言。旧0041截断测试被新增外键先拒绝，改临时库TRUNCATE CASCADE以实际验证仍由保护触发器拒绝，未放宽生产约束；失败down版本断言使用实际head，仍要求事务失败版本不变。
- 真实0041计划Schema、Worker计划、0040旧文档用途/误绑/历史保护及Document真实文件+caller元数据/Audit回滚回归PASS。
- 开发wheel0.1.0.dev0 PASS，556102 bytes，SHA256 `81db27f2402d0d81783669290add7edc402c51d31daf71af861134ed6b648a72`，不是可使用离线安装包。

## Known Issues / Next

Job/File/SystemActor refs合成，发布Audit仅真实own事件的合成身份形状，不证明正式Worker/SystemActor、当前权限/Lease或Job已完成；完整manifest不是下载授权。下一项P03-A03-P04结果own Repository/字节复核，随后Jobs caller-UOW完成Port及真正短事务渲染→文件→原子发布；POST保持关闭。正式信任源/质量Gate3/性能/三平台/全部Scope和交付继续保留。
