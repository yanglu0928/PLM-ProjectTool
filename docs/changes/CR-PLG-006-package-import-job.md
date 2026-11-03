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


## 0223 history-preservation assertion follow-up (2026-11-03)

- run [41613964579](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41613964579) progressed past the corrected empty-database downgrade sequence but exposed a second stale assertion in the synthetic-history path: downgrading 0224 to 0223 removes only the empty staging table and leaves the 0223 Plugin owner guards open; the test incorrectly expected the 0222 closed-owner state.
- Corrected the verifier to confirm staging table removal and the 0223 open-owner/immutability guards. The explicit empty-database path continues to downgrade to 0222 and independently verifies the four closed INSERT-owner guards.
- This is validation sequence/assertion correction only; migration, product database behavior, and stored history are unchanged. Repeat the hosted PostgreSQL 18 migration lifecycle and end-to-end package checks before claiming acceptance.


## A08 Worker编码前补充决策（2026-11-04）

- **缺口与目标：** A08上传端已把签名ZIP、最小Job/Outbox、签名元数据及提交Audit接通；若没有受限消费者，Job永久停留在PENDING，A08不能验收。补齐只消费 `owner_module=plugin`、`job_type=PLUGIN_PACKAGE_VERIFY` 的Worker；不接触其它Owner的Job。
- **执行方式：** 复用Jobs现有claim/lease/fencing/finish/retry状态机。通用claim必须排除本Owner类型；Plugin专属claim使用精确Owner过滤。领取后在一个只读UOW核对当前RUNNING Job、fencing token、actor、trace、最小payload与append-only staging行的ID/hash/size一致，然后按不透明upload ID推导私有暂存位置。
- **文件读取与安全边界：** LocalFileStorage增加只接受本地GLOBAL暂存locator的已验证快照读取，最多256 MiB；单Worker单包，按精确长度读取并再次比对SHA-256。成功后只调用既有Ed25519签名验证、manifest/ZIP检查和兼容评估/metadata登记，不安装或执行插件代码。文件名、路径和ZIP正文不进入日志、Job/Outbox或API响应。
- **登记和重放：** 使用原Job提交者作为Plugin登记Audit主体；注册成功但Job完成提交失败时，下一次fenced重试由现有package_id/version/hash幂等回读，避免重复登记/Audit。不可恢复包/签名/信任/兼容错误终止Job；存储/数据库暂时错误最多按既定三次Job限制重试。
- **兼容策略：** 新增不可变策略标识 `host.platforms.v1`，只接受manifest声明的受支持产品目标OS集合（Windows 11、Windows Server 2025、Debian 13）、x86_64与Plugin API主版本1；它仅表示静态声明兼容，不表示安装或代码安全。无策略、无签名信任或撤销发布者均fail closed。
- **影响/回滚：** 无冻结API、业务表或数据模型变化；无新增migration。Jobs内部新增精确claim方法及Plugin Worker组合入口。若Worker验收失败，保持HTTP入口关闭于默认组合并保留Job/staging数据，修正或回退Worker代码；不删除历史、不开启执行能力。
- **验收：** hosted Windows runner D盘临时目录；定向测试 + 后端全量/wheel + PG18 claim/租约/重试/真实登记/重放与失败回滚烟测 + 父包构建及A17/A34全链路。Secret扫描通过后仅同步当前功能分支。


## A08 Windows Worker 组合入口实现范围（2026-11-04，编码前边界记录）

- 为让已验收的 Worker 可在 Windows 11 内部包中显式启动，新增仅 Windows 可用的受限 CLI 组合入口及进程诊断角色 `PLUGIN_PACKAGE_WORKER`。入口必须加载既有 Bootstrap、Windows 当前账户数据库凭据及 License 服务，检查当前 Alembic head 后才构造 Worker；支持一次处理或常驻轮询，退出时释放数据库连接。
- 此入口不改变默认 API 组合、Service 自动安装策略、插件信任名单或数据库/API合同；不添加 migration。Worker 仍只验签、解析 manifest、检查静态兼容和登记元数据，禁止安装/执行插件。
- 回滚只需恢复入口、角色枚举与对应测试；不涉及持久数据。验收包含定向/全后端云端测试、wheel、Windows 同提交父包与既有A17/A34链路；PG18 的领取/登记/租约/失败复验烟测仍需单独补齐后才可关闭A08。
- 代码提交前已将此范围纳入CR-PLG-006；无新增Secret或客户数据。
