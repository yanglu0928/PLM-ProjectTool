# DOC-05-A01-P03-A01 Document 项目列表 Windows 11 API/PG 验收

- 日期：2026-09-29；Phase 2 Platform Core；结果：`API_PG_PASS / BROWSER_NOT_VERIFIED`。输入为冻结 API-02 `DOCUMENT_LIST/GET`、DOC-05-A01-P01/P02 与既有隔离验收夹具。
- 范围：只扩展 `validation/prj-05-a04-browser-project/serve.py` 的 `--document-history-api-only` 互斥模式；每轮随机库插入 51 条 OWNED ACTIVE、1 条 OWNED RESTRICTED 和 1 条 FOREIGN ACTIVE 合成元数据。未读取或复制客户文档；不改生产 API、Schema、Migration、权限或依赖。
- HTTP：真实登录 Session 下匿名列表 401、非项目成员管理员 404、跨项目列表/详情 404；OWNED 50+1 两页，签名游标与 Session 绑定，异会话复用 400；51 条唯一、Scope/类别正确且不返回文件正文/物理位置；详情 200 且头部强 ETag 与正文一致。受限与 FOREIGN 对照不进入 OWNED 列表。
- 数据/清理：SQL 核 OWNED 51 ACTIVE + 1 RESTRICTED、FOREIGN 1；每轮随机数据库、角色及临时 Vault 凭据清理断言通过。Python 语法检查与完整 API-only 夹具 exit0。测试前 PoC PostgreSQL 停止，正常启动后运行，结束以 fast stop 恢复停止。
- 未通过范围：曾启动 `--document-history-browser` 临时模式，但电脑操作工具无法可靠确认当前 Chrome URL，按安全策略终止该轮 UI 操作；仅已清理临时资源，不记录浏览器 PASS。正式信任锚、其他平台、性能/质量 Gate 和可使用程序包亦未验。
- 兼容/回滚：仅验收夹具与记录；兼容 DB0049/冻结 `/api/v1`，无升级步骤。回滚可撤 `--document-history-api-only` 模式，历史验收证据保留。
- 下一项：`DOC-05-A01-P03-A02` 实际浏览器项目 Document 列表及分页验收；若浏览器工具仍不可用，继续独立 Phase 2 工作，不以 API/PG 代替 UI 证据。
