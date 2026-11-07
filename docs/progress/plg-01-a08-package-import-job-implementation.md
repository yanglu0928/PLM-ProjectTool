# PLG-01-A08：流式暂存实现进度

- 状态：PASS_SCOPE_LIMITED
- 日期：2026-11-03
- 变更：CR-PLG-006
- 当前结论：受控上传、Job/Outbox/Audit/HTTP、fenced Worker及Windows CLI均已实现；按下方分段记录完成云端验收。

## 已实现

- 新增 PluginPackageImportSpool，复用 Document 私有 LocalFileStorage 的opaque GLOBAL staging locator。
- 按不超过1MiB块读取，校验申报长度、SHA-256和最大包上限（不超过 Inspector 的256MiB）；fsync后验证文件身份/链接数并重读内容Hash。
- 写入失败时只尝试按本轮inode删除；删除失败保留孤儿给后续受控恢复，不按路径盲删。
- staging locator 与摘要字段从对象repr隐藏；无路径返回给HTTP。
- 增加合成单元验证覆盖正常暂存、超长、长度/摘要错误、非法chunk和失败清理。

## 首段实现时尚未完成（历史状态）

HTTP Session/License/CSRF/DeploymentAdmin route；Idempotency回放/冲突；staging metadata owner；Job/Outbox/Audit原子入队；worker安全执行。该描述是首段实现时的历史状态；完整范围结论见本文件末尾。


## 首段云端验收与复核

- 首段实现提交 f116604885d942fb9f2fa7d3d471d03c9652c9f9；run [41597429890](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41597429890) 全13/13 jobs成功。后端测试/wheel、前端、PG smoke、父包组装、A35/A17/A34通过。
- 复核发现Application直接导入Document基础设施，属于需先登记再修正的模块依赖偏差。CR-PLG-006已记录。此首段不对外装配；A08仍进行中。


## Protocol修正与结果归档恢复

- 已按CR-PLG-006将Application的Document基础设施直接依赖改为Plugin-owned staging storage Protocol。
- 本次提交同时恢复PLG-01-A07结果文档与CR-PLG-005关闭记录，避免早前Git Tree更新遗漏这些新增路径。
- A08修正后hosted验证尚未完成。


## Protocol修正云端验收

- 修正提交 8baaaf827bf6b7bbc1cf4b47e8a5606712e4b02e；run [41599893419](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41599893419) 全13/13 jobs成功。
- Plugin Application跨模块具体依赖已移除；本次仅验证暂存原语及全链路回归，A08导入API/Job/Worker仍未完成。
- 此提交同时恢复A07结果文档和CR-PLG-005的最终PASS_SCOPE_LIMITED关闭证据。


## Job/Outbox队列Owner首段

- 新增Plugin-owned Application queue contract和SQLAlchemy Job/Outbox repository；复用既有job schema，不新增migration。
- 幂等键在Deployment范围内以actor+API operation+IdempotencyScope摘要生成；相同内容重试复用同一Job/Outbox引用，不同内容返回冲突。
- Job payload最小化为opaque package_upload_id、SHA-256和size；Outbox不含包正文、路径或签名。
- 定向和hosted验收待运行。尚未实现staging协调事务、Audit、HTTP Router、worker；A08仍进行中。


## Job queue单测夹具修正

- 将无效命令测试改为在测试执行阶段创建，避免参数收集时触发构造异常；产品逻辑不变。修正后的hosted验收待完成。


- 幂等键hash前缀已按CR-PLG-006统一为固定ASCII冒号分隔；此前字符转义未命中并已记录修正。


## 当前验证证据

- Job/Outbox queue contract/repository及测试由run [41602717998](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41602717998)全13/13 jobs成功；未覆盖该新Owner的独立真实PG18写/重放集成。
- 独立契约复核发现后台Worker需要detached signature/signer_key_ref；已先记录0224 append-only staging metadata迁移方案，再开展ORM/migration与原子入队集成。


## 异步验证元数据Schema首段

- 新增0224 append-only staging metadata ORM/migration，保存后续Inspector所需detached signature/signer key reference及包摘要/大小，不保存ZIP内容。
- Hosted PostgreSQL 18 migration验证已扩展，包括空库升降级重升、有行阻止0224降级和守卫检查；结果待run完成。


## Windows Worker CLI 组合入口（2026-11-04）

- 新增显式 Windows Worker 入口：读取正式 Bootstrap 和当前账户数据库凭据，执行数据库 readiness、Migration head 与 License 检查后才创建 Worker；支持 `--once` 和有界休眠的常驻轮询。
- Worker 进程登记角色扩展为 `PLUGIN_PACKAGE_WORKER`，用于既有诊断标记；无默认 API 挂载、无服务自动安装、无插件代码执行或新 migration。
- 新增进程角色单测。当前只提交代码，云端验证仍待；A08不关闭。PG18 Worker领取、lease/fencing、真实签名包登记与错误重试/失败验收仍是剩余项。


## Windows Worker CLI 云端回归（2026-11-04）

- 提交 `bcb69866d44038ab66a6948c23e996ababf3065e` 新增Windows显式组合入口、诊断角色及其单测。
- GitHub hosted run [41673992094](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41673992094) 13/13 jobs全通过；覆盖后端全量测试/wheel、前端构建、PG18/pgvector、嵌入式Python、父包和A35/A17/A34验证。测试在GitHub runner执行，未运行用户本机代码。
- 新增PG18端到端Worker smoke和入口模块导入门禁已进入本次待验证提交；旧run通过不能替代这些新覆盖。A08继续进行中。


## Worker CLI与PG18端到端验收结论（2026-11-04）

- 状态：PASS_SCOPE_LIMITED。提交 e37e668e89db2f64856e98799c572b7415801b8f 的GitHub hosted run [41678551589](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41678551589) 全13/13 jobs成功；后端全量测试/wheel、前端测试构建、PG18/pgvector、嵌入式Python、Windows父包、A35、A17、A34均通过。
- A17 packaged flow的PlanVersion PG探针同步执行本文件A08 worker smoke。Smoke覆盖Plugin精确Owner领取、签名不可信时终态FAILED、仅使用本次runner内存合成Ed25519键的有效包登记VERIFIED元数据/PLUGIN_PACKAGE_REGISTER Audit、暂存读取短故障进入RETRY_WAIT、恢复文件后第二attempt成功；含可执行异常的入口脚本未被执行。A17进程退出0，说明同步调用及其断言通过。A17 evidence summary只白名单记录PlanVersion的两个P51 marker，没有单列A08 marker；本结论依赖受控源码调用点、同步异常传播及成功exit status，不声称独立A08证据artifact。
- 未新增Schema/API/migration。所有包和密钥为合成测试输入，测试公钥仅内存存在；包内正式publisher trust manifest仍为空，真实开发者签名、产品服务安装与Windows 11实机尚未验证。
- Windows入口导入保护/诊断角色单测、后端全量、父包及完整集成链成功。CLI只提供显式Windows进程入口，不表示Service安装或开机启动已接线。
- Pilot、Gate 3、正式Release均保持NOT_READY。用户本机/C盘未运行代码。
