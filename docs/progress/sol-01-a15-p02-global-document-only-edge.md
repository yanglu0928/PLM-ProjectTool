# SOL-01-A15-P02：GLOBAL 文档-only 来源 Win11 Edge/隔离 PG 验收

日期：2026-10-09。结果：`SOL_01_A15_P02_GLOBAL_DOCUMENT_ONLY_EDGE_PG_PASS`；仅合成用户/文件、Windows 11、临时 PostgreSQL 18 与真实 Edge，不等于正式部署/UAT。

## 编码前检查

- Phase/WBS：Phase 2 Platform Core / SOL-01-A15-P02；输入冻结 GLOBAL 脱敏增量、API-04、A15-P01 前端合同和既有 GLOBAL 合成文件/Session 夹具；前置满足。
- 单一问题：验证受权固定 GLOBAL 文档版本且无 Evidence 的 Preview/本人确认、Create/Revise、当前版本与审计整链。仅新增一次性测试脚本及默认关闭的文档读路由夹具注入；不改生产路由、Schema/Migration、公开 API、权限或依赖。
- 验收：真实文档候选/固定版本/文件内容访问，0 Evidence 的两次独立确认、创建+修订 201 与当前 GET，数据库两版各 1 文档/0 Evidence、确认号不同、各一条 Audit；旧多/单来源流程回归；临时资源清理。
- 风险：脚本模拟核查点击，仅验机制，不是客户真人脱敏判断；正式信任源、目标账户、Server2025、性能和 Gate3 尚未验。

## 实施与证据

在既有 GLOBAL 浏览器测试服务器增加默认关闭的 `include_document_read`，只为本夹具装载 Document LIST/GET 与 Version LIST/GET。新增 `validation/sol-01-a15-p02-global-document-only-browser/serve.py`、`run-edge-browser.mjs`：真实 Edge 以 DeploymentAdmin 登录，从受权活动 `REFERENCE_MATERIAL` 文档选择固定版本、实际下载私有文件内容 200，页面展示零 Evidence；逐项打开原文并点击本人确认，再创建 Reference 根。进入修订页后重新选同一固定版本、改变脱敏分类、重新预览/确认，修订 201 后当前 GET 指向第 2 版。SQL 证明两版 `(document_count,evidence_count)=(1,0)`，确认号不同，根锁版本 1、Create/Revise Audit 各 1。

第一轮新脚本 UUID 正则漏第四段，后续两个时序等待断言过早；均属夹具问题，修正后最终退出 0。旧 GLOBAL 多/单来源 Edge/PG 创建夹具重新执行退出 0，说明默认 `include_document_read=False` 未影响原模式。前端 P01 119 文件/1697 测试、typecheck/build证据沿用；本项未改前端程序。

## 边界与后续

仅验证合成 Windows 11/隔离 PG；非管理员 GLOBAL 修订拒绝和 201 丢失同号恢复沿 A13-P03 证据，不重复宣称本脚本覆盖。GLOBAL Reference 仍仅是 `REFERENCE_ONLY` 草稿，不能推断 ELIGIBLE；冻结 `SET_ELIGIBILITY` 按 CR-SOL-014 进入 A16。正式目标账户/HTTPS/公钥、20 并发、Server2025、Gate3/UAT/发行未验；Debian13实机依用户指令暂跳过。回滚可删除新夹具/默认关闭的文档路由注入点，不触及生产数据或历史版本。
