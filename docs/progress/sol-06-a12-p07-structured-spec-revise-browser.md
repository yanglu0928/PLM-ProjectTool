# SOL-06-A12-P07：结构化专项修订 Windows 11 浏览器闭环

- 日期/版本：2026-10-16 / `0.1.0-dev.0`。状态：`STRUCTURED_SPEC_REVISION_WINDOWS_BROWSER_PASS`；仅为 Windows 11 合成信任/可弃数据验收。TraceLink：冻结 `SOL_SPEC_REVISE` → A12-P01～P06 → 本项。
- 编码前检查：P05 已证明 Windows 显式写 Router、真实 Session/CSRF/License/来源/PG/Audit/收据；P06 已证明前端安全合同与 production build。现有 SOL-06 浏览器夹具可在可弃 PostgreSQL 18.6、构建 Vue、生产 FastAPI/Uvicorn 和本机 Edge 上运行，前置满足。
- 范围：只扩展合成验收夹具和浏览器自动化，验证固定详情→显式修订→新 DRAFT→固定详情、未知结果原正文/原 Key 重放、历史来源漂移不自动替换及跨项目隐藏。测试数据均在一次性数据库；不外发客户数据，不引入测试入口到产品代码。
- 兼容/风险/回滚：不改产品 API、Schema、License、权限、依赖或旧数据；共享浏览器夹具仅按显式 `revise_mode` 增量装配，既有模式保持原行为。若验收失败，修复夹具或产品缺陷后完整重跑，不以减少断言取得 PASS；撤显式模式即可回滚测试扩展。
- 验收结果：Windows 11 本机 Edge 读取浏览器创建的固定 v1，入口仅对实施成员显示；原四类来源和迁移正文无损回填，修改范围后经真实 Session/CSRF、生产 FastAPI/Uvicorn 和 PostgreSQL 18.6 创建同系列 v2 DRAFT。手工恢复待决记录后，页面隐藏可编辑正文并以同正文、同 Idempotency-Key 重放 201；数据库保持一条修订收据和一条 `SOL_STRUCTURED_SPEC_REVISED` Audit。
- 漂移/隔离：另建只含旧批准 RequirementVersion 的历史专项，再把旧版本转 `SUPERSEDED` 并发布新的当前批准版本；修订页显示来源漂移且未自动勾选新版本。跨项目 revise POST 返回 404，跨项目修订页不加载详情、不显示表单或旧正文。最终一次性库共 3 个专项版本（漂移夹具 v1、浏览器 v1/v2），创建/修订各一条收据和 Audit。
- 回归与清理：P07 完整链和 A11-P07 既有 51 项双页列表 Edge/PG 链均通过；Alembic 检查无新升级操作，Uvicorn、Edge 临时 profile、临时数据库均由既有夹具退出清理。首轮漂移夹具直接插入第二个 APPROVED 版本触发数据库唯一约束并作废；修正为旧版本先转 `SUPERSEDED` 后完整重跑通过，未修改产品约束或遗留数据。
- 已知边界：使用合成账户、License 与临时浏览器配置，不代表正式服务账户、公钥、License/Vault/ACL/CA；Windows Server 2025、Debian 13、专项类型化验证、送审/Review、OutputArtifact、性能、Gate 3、Pilot 和正式发行仍未通过。
- Next：`SOL-06-A13-P01` 核对冻结 `SOL_SPEC_VALIDATE`、四类 payload 规则和现有 SectionVersion 六维验证边界，先定义类型化报告、当前版本/来源重证与幂等/Audit 行为，再分项实现。
