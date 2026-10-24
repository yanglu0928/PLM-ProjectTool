# RAG-04-A06-P06：Windows 生产组合与公平 Retrieval Worker

日期：2026-10-04

状态：`PASS`

验证标记：`RAG_04_A06_P06_WINDOWS_COMPOSITION_PASS`

## Changed

生产 bootstrap 新增可选且精确的 `rag_retrieval_policies` 单例：只接受 `fts.project.v1`、`PROJECT`、`none.v1` 和 `project-documents.v1`，拒绝额外字段和任何密钥值。查询内容密钥固定从 Windows 受信密钥来源读取 `rag-retrieval-query-v1`，只接受 32 字节；配置文件不承载密钥，缺失或非法时 Retrieval 组合失败关闭。

显式 platform-write 模式且策略完整时，生产 API 一次挂载 Create/Get/Result/Context、Retrieval cancel 别名，并把同一个 `RAGRetrievalCancelOwner` 注册到通用 Job cancel registry；无策略时保持既有 404。组合以 `unit_of_work` 运行时端口为边界，同时兼容 API `DatabaseRuntime` 和服务角色实际使用的 `WorkerDatabaseRuntime`。

既有第四角色 `AI_PROVIDER_WORKER` 承载 Retrieval，不新增第五服务。Probe、AI Task、Retrieval 三个工作族按轮转顺序公平尝试；每周期的 AI 过期对账、Retrieval 终态过期对账和取消对账都有固定上限。只有 Retrieval 策略时角色可在不读取 Provider Secret 主密钥、不建立 Provider 网络的条件下运行；组合停止仍沿用协作排空和数据库释放合同。

一次性 Retrieval Worker 在 claim 后、解密前检查当前取消请求；准备/执行边界出现取消时由专属 Reconciler 原子关闭 Job/Attempt/Lease/Run/Audit，避免已经请求取消的查询继续读钥。无取消仍进入原 FTS-only 零外发链。

## Compatibility / Upgrade / Rollback

- 无新 Migration、公开 URL/DTO 语义、第三方依赖或 Provider I/O；复用 Schema0090 与冻结四服务拓扑。
- 未配置 Retrieval 策略时，API、服务计划和既有 Probe/AI Task 双族循环保持原行为；配置 Retrieval 后只增加同角色内公平工作族。
- 回滚可移除策略并停止新 Retrieval HTTP/claim；已有 Run、结果、取消、Audit 与密文历史必须保留并向前修复，不得把专用密钥回退到 YAML、环境明文或 Provider Secret Store。
- 正式部署必须为目标服务账户供应专用 Vault/Credential 引用；本项合成密钥只证明组合，不是正式密钥验收。

## Tests

- 生产组合、bootstrap、服务计划、Worker、公平循环、取消及 HTTP 定向 **92 项 PASS**。
- 后端全量 **2529 项 PASS，3 项既有环境条件跳过**。
- 开发 wheel 隔离导入：RAG **142 项**、生产组合/合同 **80 项** PASS；SHA-256 `353c0edc1e27ec718a71edeb53c31134d91f1b03f270dda8943192b244256547`。
- Windows 11/PostgreSQL 18.6 隔离真实组合：生产 HTTP 创建 202，第四角色一个周期完成目标 Retrieval，Get/Result/Context 均 200；同一生产取消 Owner 先关闭旧待处理夹具，SQL 最终精确证明一个 SUCCEEDED 与一个 CANCELLED Retrieval。使用真实 `WorkerDatabaseRuntime`，停止后释放数据库；密钥读取仅出现固定专用引用，零 Provider 网络。

## Deviations / Evidence Corrections

首次真实组合运行暴露 Windows Retrieval helper 只接受精确 `DatabaseRuntime` 类型，导致服务角色实际 `WorkerDatabaseRuntime` 被拒绝。按运行时端口兼容原则改为验证可调用 `unit_of_work`，保留失败关闭；该首轮不计证据。

第二轮由同一隔离夹具遗留的旧 PENDING Retrieval 先进入 FIFO，目标生产密钥 Run 未在单周期内完成。验证脚本改为先通过生产 cancel 别名合法关闭旧 Run，再创建并执行目标 Run；该轮不计证据，最终在完整新运行中通过，未为夹具改变产品调度顺序。

wheel 隔离测试首次尝试把临时目录创建、运行与递归删除合并在同一 PowerShell 命令，被本机安全策略在进程启动前拒绝；随后使用已核对的仓库忽略目录分步安装与运行，全部通过。拒绝的命令不计测试证据，也没有改动产品或仓库跟踪文件。

## Result / Known Issues / Next

结果：`PASS`。Windows 生产 API、专用查询密钥、双取消同 Owner 和既有第四 Worker 的公平有界 Retrieval 闭环已组合并有真实 PostgreSQL 证据。

已知问题：前端安全客户端/页面与真实浏览器全链留 P07/P08；正式目标账户密钥供应、Windows SCM 实机、Windows Server 2025、质量/性能、Gate 3、UAT 和发行包仍待。Debian 13 按用户指令跳过实机验证，但仍为正式兼容目标。

下一项：`RAG-04-A06-P07`，实现 Retrieval 前端安全客户端与页面，保持查询不进入 URL/日志/持久化浏览器状态，结果只按服务器安全投影展示。
