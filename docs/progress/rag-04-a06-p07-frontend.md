# RAG-04-A06-P07：Retrieval 前端安全客户端与页面

日期：2026-10-04

状态：`PASS`

验证标记：`RAG_04_A06_P07_FRONTEND_PASS`

## Changed

新增严格的 Retrieval 浏览器客户端，覆盖 Create、Get、Result、Context 和 Cancel 五个冻结 Operation。创建请求只允许当前 `fts.project.v1 + none.v1`、PROJECT ACTIVE Index 及分类/来源类型/固定文档版本三类已实现过滤；query 经 NFKC、空白规范化、Unicode 码点和 UTF-8 字节双重上限后，只进入一次同源 POST body，不进入 URL、浏览器存储、错误消息或客户端对象留存。

读取端逐层复核 Project/Run 身份、ETag、状态、连续排名、来源类型、locator、整数 ScorePart、Context 顺序与 token 总数；公开 View 丢弃服务器内部 bundle fingerprint。任何响应身份、结构或结果/Context 组合漂移均整页失败关闭，不保留部分事实。Cancel 固定使用当前 Run ETag 和单个内存幂等键；未知结果不换号自动重试，首次回执明确不是当前状态证明。

新增项目知识检索创建/详情页及项目详情入口。页面只展示状态、来源、定位、整数分数和最小片段；明确 AI/检索结果不是人工确认结论。query 在成功、已知失败、未知结果、路由变化及卸载时清空。新建与取消均要求用户当次勾选确认；未知创建锁定当前页面，保留非敏感操作号供核对。

## Compatibility / Upgrade / Rollback

- 纯前端增量，无 Schema、Migration、后端 API、依赖、网络外发或数据迁移变化；冻结 `/api/v1` URL 与 DTO 方向保持。
- 后端当前未提供 ACTIVE Index 列表 Operation，创建页暂由实施管理员提供项目 ACTIVE Index UUID，服务器仍复核 Project 归属与 ACTIVE 状态。此为可用性缺口，不表述为最终用户体验完成；P08 真实验收仍使用受控夹具的已知 Index。
- 回滚可移除客户端、两条路由和项目入口；后端历史 Run/结果/Audit 不受影响。不得以持久化 query 或放宽响应校验作为兼容手段。

## Tests

- Retrieval 客户端、页面及关联路由/项目入口定向 **29 项 PASS**。
- 前端全量 **69 个文件、1261 项 PASS**。
- `vue-tsc`、Node TypeScript 检查和 Vite 生产构建 **PASS**；149 modules transformed，最终主 JS 497.92 kB（gzip 126.32 kB）。
- `git diff --check` **PASS**。

## Deviations / Evidence Corrections

首轮页面定向测试有两条断言把页面固定安全说明中的“Golden/最小上下文”误判为结果泄露；断言改为只检查实际结果/Context 区域，该轮不计验收证据。首轮类型检查另发现日期值窄化和测试夹具枚举宽化两处静态错误，修复后完整重跑。

复核后发现初版客户端类型接受 `effective_from/effective_to`，但当前后端策略仍明确关闭日期和 business 过滤。页面虽未暴露该能力，客户端合同仍可能产生“本地接受、服务器拒绝”。已收紧为分类、来源类型和固定文档版本，并增加非法字段传输前拒绝回归；该偏差未改变冻结 API 或后端实现。

## Result / Known Issues / Next

结果：`PASS`。Retrieval 前端五个 Operation 已按最小披露、未知结果不重放和 query 不持久化原则接入。

已知问题：ACTIVE Index 列表仍无前端 API；真实构建页面到生产 FastAPI、Worker、PostgreSQL 的浏览器闭环留 P08。正式目标账户查询密钥、Windows SCM、Windows Server 2025、业务质量/性能、Gate 3、UAT 和发行包仍待；Debian 13 按用户指令跳过实机验证但仍是兼容目标。

下一项：`RAG-04-A06-P08`，执行 Windows 11 真实构建浏览器 → HTTP → Worker → Result/Context/Cancel → PostgreSQL 验收并清理全部临时资源。
