# OUT-01-A01-P39 编码前检查：Hosted Edge输出历史下载保存验收

- 日期：2026-11-06
- 状态：编码前检查通过，Hosted Edge验收待实施
- WBS：OUT-01-A01-P39
- 来源：P37只用模拟Client/导航验证前端入口；P38通过PG18与真实FastAPI routes/Repositories/Storage验证Artifact引用到Document内容字节，但采用ASGI原生scope且没有浏览器下载保存。剩余证据缺口是浏览器是否按真实输出历史入口触发附件保存，以及下载内容是否与HTTP响应一致。
- 基线：冻结API Contract V1、Document下载合同、CR-OUT-032/033。维持既有API/Schema/Migration、Opt-in生产路由和Trust边界。

## 编码前检查

- 当前阶段：Phase 2 Platform Core。
- 输入基线：P37 PASS_SCOPE_LIMITED；P38 PASS_SCOPE_LIMITED；OutputRequestListView、OutputArtifactReadClient及Document download attachment response。
- 前置任务：前端产物由P24/P37 Hosted验证；P38已通过真实PG18 Artifact→Document HTTP/Storage组合；Hosted Windows Server 2025 runner可运行Edge并将profile/证据置于D盘RUNNER_TEMP。
- 涉及模块：输出历史Vue视图与现有客户端；仅新增独立Hosted Edge harness/job和合成HTTP fixture。
- 涉及实体：合成Project、OutputRequest、Artifact引用和DocumentVersion下载响应；无持久化业务实体变化。
- API：不变。使用既有Artifact引用GET与Document content GET URL形态、标准response envelope及Content-Disposition attachment头。
- 权限：只使用合成Session与项目授权；不设置Publisher/License生产信任，不向默认应用挂载路由。
- 验收标准：真实Edge载入同run production frontend；输出历史包含一条合成SUCCEEDED行；点击“下载文件”后先获取固定Artifact引用，再请求同源Document content URL；Edge完成附件下载；保存文件字节、长度和SHA-256与预设合成负载一致；无失败/非SUCCEEDED行下载、不可信host/跨项目引用不得引发内容请求或保存；Edge profile、下载和summary只写Hosted D盘临时目录并清理；全量前端测试、typecheck/build和代码/Secret边界检查通过。
- 风险：单独浏览器contract harness不通过真实PostgreSQL或FastAPI网络服务器；P38的真实路由证据与本项浏览器字节保存证据是同一固定合同的分层验收，不宣称同一真实产品进程端到端。P25真实Windows HTTP/Edge全流程仍因initdb 0xC0000135未运行。正式Publisher/License trust、Windows 11设备、Pilot、Gate和Release均不由本项验收。
- 实施步骤：先新增独立验证器和Hosted job，复用同run production dist；只使用合成同源fixture。完成后在GitHub hosted Windows runner验收并核查summary、下载文件hash和全链回归。
- 预期修改：validation/out-01-a01-p39-edge-download、.github/workflows/cloud-sandbox-validation.yml及追踪文档；除非Hosted发现产品缺陷，不修改生产前后端。
- Migration/API变更：无。
- 风险控制/回滚：无信任密钥、客户数据或外部调用；回滚仅删除新增Edge job/harness/追踪记录，不修改已保存业务事实或文件。
- Secret检查：仅合成常量；禁止记录登录密钥、Cookie、session token或文件正文。

## 决定

PASS_WITH_LIMITATION：P39可以进入Hosted Edge harness实现；验收仍限浏览器同源下载合同，不冒充P38实时服务或正式产品信任。按持续授权直接执行并将所有实际偏差先记CR-OUT-034。


## P39实现候选与验收状态

已新增独立Hosted Edge runner及Windows 2025 workflow job，复用当前run production dist；合成同源fixture支持登录、输出历史、固定Artifact引用和Document attachment。保存文件将与预设合成负载逐字节、长度和SHA-256比对，跨项目引用在请求内容URL前被拒绝。浏览器profile/下载仅RUNNER_TEMP（D盘）并由finally清理。尚未运行Hosted验收，保持Incomplete。
