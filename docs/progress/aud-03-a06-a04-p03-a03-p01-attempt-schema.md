# AUD-03-A06-A04-P03-A03-P01：不可变渲染尝试Schema

日期2026-09-26；Phase2；依据CR-AUD-002实施前精化/ADR010/DEC208。结果：0041限定Schema PASS，实际Worker计划命令与结果发布未完成。

## Changed / Files / Migration / API

0041/Audit ORM新增`aud_export_render_attempts`子记录：attempt ID、Export/原Job、fencing/attempt号、受控worker_ref、唯一file_id、完整capture count/hash/version和创建时点。每原Job/token一个不可变文件计划，新代次使用不同file_id，固定来源不换集合。计划在I/O前登记，file_id是预分配opaque Ref，不假称FileObject已存在；Job/Lease坐标不是凭据。

own Export根行锁、真实own acceptance/capture存在及原Job/完整源摘要匹配、有限且不早于请求/受理/封口时点；仅FK自己的capture/acceptance，不跨模块读写Jobs/Document表。UUID非零、token/attempt正数、worker ASCII、安全版本/摘要与100000 count上限。不能证明真实Job存在、当前Actor权限或当前Worker Lease；这些须实际公共Port前后核验后才可登记。

计划UPDATE/DELETE/TRUNCATE全部拒绝，旧受理/封口记录不回填新计划。down离线拒绝，实际表排他锁后任何计划历史拒绝回退，不删旧来源。只有无计划可撤0041。无公开API/角色/依赖/生产迁移；应用入口未新增，导出POST仍关闭。

## Tests / Result

- 实际PostgreSQL18临时库：空库/旧双Scope已受理封口数据up/down/reup与所有源字段保持、无猜测回填、ORM parity；缺capture/acceptance/Root、错原Job/count/hash/version/time、UUID/token/attempt/worker格式拒绝；单Job/token及file_id唯一，新代次独立file；Barrier同时起跑的真并发同代只一个计划；immutability/delete/truncate及实际downgrade竞争表写锁/历史拒绝、版本和源全部不变PASS。Job/Event/Lease/File refs合成，未做完整受理权限/Worker文件证明。
- 后端904项无失败（2项Windows符号链接权限环境跳过）；2项新增ORM/DDL常量与离线down无DDL。首次全集因注册清单漏列新增表失败，补显式表清单后重跑通过，非跳过或删除断言。
- 0040用途/旧文件/误绑与历史保护、0039取消元数据历史、实际文件+caller-UOW元数据/Audit回滚真实回归PASS。旧verifier的失败降级版本断言改为当前ScriptDirectory head，继续要求事务失败后版本不变，未放宽历史保护。
- 开发wheel 0.1.0.dev0成功，550715 bytes，SHA256 `8d3c1b0a293dcd316e19c25641c236e382e317e92eaf40b787eef43b13458c99`，不是可用离线安装包。

## Known Issues / Next

P03-A03-P02先实现真正当前权限/原Root/accepted pair/capture/Lease绑定下计划登记与原代次读回，真实到期/取消/撤权/新代次/故障及死锁验收；之后唯一成功结果/manifest来源Schema、文件与Job原子发布、下载再授权。计划没有成功/可下载状态，不用Schema或合成Job宣称Worker完成。正式信任源、质量/Gate3、三平台/目标账户/性能/整体交付仍待。
