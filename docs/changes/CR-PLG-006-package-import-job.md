undefined

## A08首段实现与偏差记录（实施后代码复核，2026-11-03）

- 首段实现提交：f116604885d942fb9f2fa7d3d471d03c9652c9f9；GitHub hosted run [41597429890](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41597429890) 13/13 jobs成功，含后端全量/wheel、前端、PG18父包及A35/A17/A34既有集成链。
- 独立分层复核发现：Plugin Application 的 package_import_spool.py 直接导入 Document.infrastructure.LocalFileStorage/LocalStorageError。测试通过但违反模块边界；应用层不能反向依赖其他业务模块基础设施。
- 修复前计划：先定义Plugin自身的 staging storage Protocol/port，让Application层只依赖该抽象；生产Document storage可在组合根通过结构化adapter注入。若无法维持依赖方向，改用平台通用端口，不能保留跨业务层具体依赖。
- 影响：不改变API、DB Schema、包格式、文件路径/内容校验行为；仅依赖方向和构造验证调整。无需数据迁移。
- 回滚：保留旧提交历史；若修正导致验收失败，回滚新适配改动至有边界问题的内部实现并保持A08未完成（不可将其装入默认生产组合）。
- 验证：修复后运行新增定向测试、全后端/wheel与完整hosted云验收；继续确认runner只用D盘临时工作区。


## 分层偏差修复提交（2026-11-03，待验收）

已将Plugin Application对Document.infrastructure的具体导入替换为Plugin-owned storage Protocol；组合根按结构接口注入已有私有存储实现。仅依赖方向/类型边界调整，无API、Schema、文件行为变化。A07关闭文件及本变更历史在修正提交中恢复。修正代码与归档材料进入hosted workflow复验后补录结果。


## 分层偏差复验关闭（2026-11-03）

- Protocol修正提交：8baaaf827bf6b7bbc1cf4b47e8a5606712e4b02e。
- hosted run [41599893419](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41599893419) 全13/13 jobs成功；后端全量/wheel、前端、PG18/pgvector、父包、A35/A17/A34通过。
- 复核确认Plugin Application不再导入Document模块；暂存端口由Plugin-owned Protocol表达，层间依赖由组合根负责。
- 本修复只关闭依赖方向偏差，不关闭A08；HTTP、Job/Outbox/Audit、worker和完整导入链仍待实现。


## Job/Outbox实现进展（2026-11-03）

- 复用现有JOB-01通用Job/Outbox Schema，不新增字段或migration。
- 新增Plugin-owned queue contract/repository：Deployment scope、actor/API operation/key digest绑定的幂等键、同UOW Job+Outbox插入、重放验证摘要/大小并返回初次上传ID；异内容冲突。
- 已记录Payload规则：Job仅保存opaque upload ID、SHA-256、size，Outbox只保存Job与upload ID引用。
- 此提交的单测、hosted全回归及后续PG integration smoke尚未出结果；HTTP、Audit、staging协调和Worker仍待。


## 队列首段测试夹具复核（2026-11-03）

- 首次生成的参数化单测在模块导入时实例化无效命令，可能在pytest collection阶段先抛出异常。修正为参数化无效字段并在测试体内断言构造错误，避免收集期故障；产品逻辑未变。
- 幂等键域分隔改为固定ASCII冒号，确保身份摘要输入易读且稳定；不影响数据库/API合同。
- 随修正提交等待GitHub hosted workflow验收。


## 幂等键域分隔实现核对（2026-11-03）

- 代码审阅发现前一提交的替换未匹配实际转义文本，固定前缀仍保留反斜杠字符序列；已在本提交按CR计划改为固定ASCII冒号分隔。该值仅参与内部哈希输入，不改变键唯一性范围或持久合同。


## 完整异步验证输入的持久化补充（编码前决定，2026-11-03）

- 冻结API-03的签名包验证在后台Job中执行；A06 Inspector需要detached Ed25519 signature及signer_key_ref。仅把包字节暂存而不持久化这两项，会在请求结束后无法完成验证；把它们塞进Job payload又会扩大payload内容并让ref语义失真。
- 选择增加内部append-only staging metadata表（新migration 20261103_0224）：opaque package_upload_id、SHA-256、大小、64-byte detached signature、受限signer_key_ref及创建时间。表不保存ZIP、路径、私钥或客户正文；Job payload仍只有upload ID、摘要和大小。
- 该表是异步输入的技术暂存，不是正式PluginPackage/信任事实；由同UOW原子写入stage metadata、Job、Outbox和Audit。签名验证失败仍由后续Worker作为Job失败处理，不登记正式PluginPackage。
- 新表append-only并拒绝TRUNCATE；降级时若存在任何行就拒绝丢弃，空表才允许down。无历史冻结基线改写；偏差范围、迁移/回滚和PG18验收已补充在A08 precheck。
- Migration/ORM和集成测试实施前的本CR记录即为批准依据；执行由用户持续自主授权覆盖，无需等待逐项批准。


## Migration 0224编码结果（等待hosted验收）

- 新增plm.plg_package_import_stagings ORM/table，保存异步验证必需的package ID、hash、size、detached signature和signer key reference；无ZIP正文/路径。
- append-only UPDATE/DELETE和TRUNCATE守卫；降级若有记录拒绝删除并保持版本，空表允许down。
- PLG schema verifier及迁移head contract已更新至20261103_0224，并新增隔离PG staging行写入/守卫/数据保留/降级阻断测试；本次云端运行待完成。


## 云端回归断言修复与暂存补偿复核（2026-11-03）

- run [41606204207](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41606204207) 暴露两个 ORM 元数据单测未把0224新增表加入期望清单；产品迁移/验证任务没有报告失败。按失败日志仅修正历史清单边界和 Plugin owned-table 断言，无数据库/API行为变化。
- 下一片实现前代码复核发现 Plugin spool 在移除跨模块导入后仍引用未定义的 LocalStorageError；补偿删除失败会触发 NameError并遮蔽原错误。调整为捕获清理异常且不覆盖主错误，并在暂存结果中保留本轮 device/inode，供后续同UOW数据库失败时精确补偿。
- 风险/回滚：不改变持久合同或文件校验；保留原提交历史。若补偿用例失败，不装配导入路由并保持A08未完成。
- 验证：修正后的后端全量、PG18迁移及完整hosted工作流；均只在GitHub hosted D盘执行。


## PostgreSQL 18 migration smoke 夹具修正（2026-11-03）

- run [41612378950](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41612378950) 在PG18迁移验证脚本插入staging夹具时失败。日志显示测试用 `b"\\x31"*32` / `b"\\x41"*64` 生成了反斜杠字符文本，实际长度不符合新表32/64字节约束；并非迁移执行失败，也不表示表约束有误。
- 仅把验证夹具改为显式字节序列（0x31重复32次、0x41重复64次），重跑云端PG18完整验证。产品程序/API/Schema不变；无数据回滚。失败证据和修复原因保留。


## 0223/0222 降级守卫断言顺序修正（2026-11-03）

- run [41613964579](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41613964579) 在staging二进制夹具修正后，成功通过0224新增表插入/append-only校验，随后验证脚本在降级停于0223时错误期待0222才会恢复的四个INSERT owner_closed触发器。
- 0223实际应保持四个immutable更新/删除触发器、四个禁止TRUNCATE触发器且无owner_closed；0222才重新关闭INSERT。仅把验证顺序调整为先核验0223父链开放状态，再降至0222核验四个closed触发器，之后降至0221。不更改迁移或产品数据库守卫。
- 重跑PG18空库升级/父链降级/重升和有数据保护验收；失败记录保留在本CR。
