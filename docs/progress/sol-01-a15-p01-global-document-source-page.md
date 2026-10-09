# SOL-01-A15-P01：GLOBAL 文档主来源与可选 Evidence 页面

日期：2026-10-09。结果：`SOL_01_A15_P01_GLOBAL_DOCUMENT_SOURCE_FRONTEND_PASS`；仅前端合同/构建，真实 Edge/PG 待 P02。

## 编码前检查

- Phase/WBS：Phase 2 Platform Core / SOL-01-A15-P01；输入冻结 GLOBAL 脱敏增量 1～100 DocumentVersion/0～500 Evidence、API-04、DEC-20261009-1134、A13 页面和 A14 边界审计，前置满足。
- 单一问题：GLOBAL 来源选择 UI 原要求至少两条 Evidence，拒绝合同允许的文档-only 集合。仅改前端 GLOBAL Source Picker/修订共用视图与测试；部署管理员不变，无后端、Schema/Migration、API 或依赖变化。
- 验收：从受权 GLOBAL 活动 `REFERENCE_MATERIAL`/`STANDARD_CAPABILITY` 文档列表选择固定可用版本，至少一个文档、Evidence 可选；不输入 UUID；Preview/逐项打开原文/人工确认及创建/修订写前重读元数据和哈希；既有多 Evidence 流程保持。后续 P02 在 Win11 Edge/隔离 PG 实测。
- 风险：Document 列表元数据不能证明物理文件现时完整性；最终服务端仍须重新验证来源和人工脱敏确认。浏览器内容链接需以真实授权下载核验。

## 实施与验证

`GlobalReferenceSourcePickerView` 增加受权 GLOBAL Document 候选、可用固定版本列表/选择、已选原文链接。页面只显示当前活动且类别符合服务端白名单的文档；选定时和 Preview/最终 Create/Revise 前分别重新 GET 文档及版本并比较 `content_sha256`。统一固定文档集合按手选文档先、Evidence 衍生文档后去重，Evidence 保持可选；预览回执仍须逐位匹配有序文档和 Evidence 身份，逐项打开/勾选后才允许本人确认。来源分类长度按服务端 ≤128 对齐，避免原前端大写 64 字符的人为收窄。

新增文档-only 创建和修订合同测试，验证 1 个固定文档/0 Evidence、人工确认与写前重复读取；旧多来源、未知结果恢复、权限等测试回归。Windows 11 前端 119 文件/1697 项、typecheck/build通过；构建主包 >500 kB 仍是既有提示，不代表性能目标已验。

## 边界与后续

本项未运行真实文档候选 HTTP/受权下载或文档-only 写链，不宣称端到端可用。A15-P02 需 Edge/隔离 PG 验证创建/修订、DocumentVersion 文件、人工确认、权限和审计；如当前一次性测试服务器未注入 Document READ Router，只在验收夹具显式补装，不改变默认生产模式。Eligibility 仍按 CR-SOL-014 留 A16。正式目标账户/20 并发/Server2025、Gate3/UAT/发行未验；Debian13 实机依用户指令暂跳过。

回滚：撤下文档候选 UI 可回到旧多 Evidence 路径，历史内容与接口不变；但会重新出现合法文档-only 集合无法操作的已知缺口，故不是最终兼容状态。
