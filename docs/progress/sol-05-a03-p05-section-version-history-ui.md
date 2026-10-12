# SOL-05-A03-P05：SectionVersion 历史列表/详情用户入口与 Win11 浏览器

日期：2026-10-12。结果：`SECTION_VERSION_HISTORY_UI_EDGE_PASS`；仅历史读取页面，不提供 SectionVersion 草案 CREATE、VALIDATE 或 Review 的前端操作。

编码前检查：Phase 2；输入冻结 API-04、A03-P02 Owner、A03-P03 HTTP 合同与 A03-P04 Windows/真实 ASGI-PG，前置满足。本项单一问题是让已授权项目成员在 UI 查看章节版本历史和固定详情。涉及 Solution 前端客户端、两个页面、路由及验收脚本；不改后端 API、Schema/Migration、权限或数据。风险是把历史引用显示成现时合格、凭 UUID 猜测文档定位或跨项目/换路由泄漏旧页面；按 DEC-1185 先登记页面选择。

实现独立只读客户端，严格校验 Project/Section/Version 身份、字段集、页大小/降序、游标、声明计数/固定引用、Trace/no-store 响应和安全错误映射；畸形数据拒绝展示。章节详情增加历史入口；新列表/详情页面仅在当前 Session 授权项目发请求，路由切换清除旧数据。详情链接已有 Requirement 身份页；DocumentVersion/Evidence 仅显示固定标识，不杜撰物理文件或 Locator，并明确历史资格、评审与客户确认需另验。

定向客户端/页面/原章节页 12 项通过。前端全量 129 文件/1741 项通过，`vue-tsc` 与生产 Vite build 通过；构建有既存主 bundle >500KB warning，本项不影响页面运行。Windows 11 Edge 独立临时配置、真实 Uvicorn/Session/一次性 PG18.6 合成项目成员登录，从章节详情进入历史列表/固定详情，观察两个 GET 实际 200、跨项目页面不展示版本，脚本退出0；临时浏览器配置和服务器已清理。首轮定向测试发现新 UUID 校验少一组，修复后复测通过；浏览器验收加强为列表和详情两个 HTTP 200 后重跑通过。

兼容/回滚：无 Migration、API 或旧数据变化；移除新增前端路由/页面可回滚，后端历史保持。未验 SectionVersion 草案 CREATE UI、正式目标账户/HTTPS/公钥、Server2025、20 并发、Gate3/Pilot/Release；Debian13 实机依用户指令跳过。下一项 `SOL-05-A03-P06` 实现受控 SectionVersion CREATE 前端工作流及真实浏览器写链。TraceLink：Gate2 API-04 → CR-SOL-003 → A03-P02～P04 → DEC-1185 → 本 P05 → P06/VALIDATE/Review → Gate3/Pilot。
