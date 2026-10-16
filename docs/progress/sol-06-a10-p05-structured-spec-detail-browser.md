# SOL-06-A10-P05：结构化专项详情浏览器验收

- 日期/版本：2026-10-16 / `0.1.0-dev.0`。TraceLink：冻结 `SOL_SPEC_GET` → A10-P01～P03 受权读取/Windows HTTP-PG → A10-P04 前端详情 → 本项。当前 Phase 2。
- 编码前检查：前置创建、详情 API/Windows 装配与前端页面均已完成。本项只验证 Windows 11 Edge→真实 HTTP/可弃 PostgreSQL 18.6 的创建后详情和项目隔离；不改 Schema、冻结 API、角色或 License 机制。合成账户、License 和临时数据库只用于独立验收，不代表正式发行信任。
- 首轮失败/修复：真实 Edge 点击详情时页面在发 GET 前报 `Illegal invocation`；原因是客户端构造器直接保存 `window.fetch` 后以实例方法调用，浏览器要求保留 Window 调用上下文。改为默认闭包 `(...args) => fetch(...args)`，仍保留测试注入点；新增默认客户端回归用例。该修复不改变网络合同或服务端行为。
- Changed：扩展既有可弃浏览器夹具，在详情验收模式装配 SOL_SPEC_GET；浏览器创建并以原正文/原幂等号重放后点击详情，核对中文类型化内容、固定需求/章节/证据及页面链接；直接跨项目 GET 必须 404，跨项目路由必须清空旧内容且不泄漏 200。数据库继续核对唯一 DRAFT、创建收据与 Audit。
- 验证：默认客户端定向 1 文件/4 项；TypeScript 与生产构建；Windows 11 Edge→真实 HTTP/可弃 PG18.6 创建→详情 GET→跨项目 404/页面隐藏；旧 SOL-06 CREATE Edge/PG 浏览器链回归；前端全量 141 文件/1786 项均通过。首次失败已保留在执行轨迹，修复后全部复跑为 0 失败。
- 兼容性/升级/回滚：无 Migration、后端 API、权限、依赖或旧历史变化；客户端默认 fetch 包装和验收夹具可独立撤回，无数据升级动作。Windows Server 2025/Debian 13 未据此推定兼容。
- 限制：这是 Windows 11 合成信任与可弃数据库证据，不等于正式目标账户、公钥、HTTPS、离线安装、性能或客户 UAT。专项列表/修订/验证/送审、OutputArtifact、章节六维 `ready_for_review`、Gate 3/Pilot/正式 Release 仍未完成。
- Next：`SOL-06-A11-P01` 按冻结 `SOL_SPEC_LIST` 核对列表分页、过滤、项目隔离和前端可发现性前置，再拆分内部读取、HTTP/Windows、页面与 Edge 验收。
