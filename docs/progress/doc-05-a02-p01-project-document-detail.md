# DOC-05-A02-P01 项目 Document 元数据详情页

- 日期：2026-09-29；Phase 2 Platform Core；状态：前端合同 PASS，Windows 11 实际浏览器/PG 待后续分项。
- 输入：冻结 API-02 `DOCUMENT_GET`、DOC-05-A01-P01 安全客户端、P02 列表页及 DOC-01-A03-P04 Windows 显式读取组合。只处理 PROJECT 元数据详情；GLOBAL 管理入口、文档版本历史、文件内容/下载和写操作不在本项。
- Changed/Files：新增 `ProjectDocumentDetailView` 与测试、项目文档详情固定路由、列表行详情入口。直达 URL 仍须当前 Session 和服务端授权 GET；展示标题、文件名、分类/细分、状态、版本引用、创建时间、强 ETag，不透传正文或 storage locator。刷新先清旧详情，路由切换/卸载丢弃迟到响应，拒绝或异常不显示旧元数据。
- 验证：定向 12/12（详情新增 6 项，列表 6 项）、前端全量 814/814、typecheck、production build PASS。覆盖无身份/强制改密、直达安全投影、404、ETag 头错配、刷新失败清旧、非法 ID 和切项目/文档迟到响应。实际浏览器/PG、正式信任/其他平台、性能质量/Gate3 未在本项验证。
- 兼容/回滚：无后端 API、Schema、Migration、权限或依赖变更；兼容 DB0049 和冻结 `/api/v1`，无升级步骤。可撤前端路由/视图/列表入口及其测试，保留 P01/P02。
- 下一项：`DOC-05-A02-P02` Windows 11 隔离浏览器/PG 项目 Document 详情读取验收；其他 Document 版本/内容功能独立推进。
