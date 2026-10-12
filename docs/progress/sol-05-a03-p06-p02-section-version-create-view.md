# SOL-05-A03-P06-P02：SectionVersion 草案候选与创建页

日期：2026-10-12。结果：`SECTION_VERSION_CREATE_VIEW_PASS`（前端合同）；真实浏览器/PG 写入留 P03。

编码前检查：Phase 2；输入冻结 API-04、CR-SOL-003、A02-P12 Windows 11 HTTP/PG CREATE、P06-P01 受控前端传输与 P05 历史只读入口；前置满足。单一问题为当前项目候选选择与可恢复创建页；只改前端 Solution 模块、路由和测试。风险为分页遗漏、过期资格、跨项目候选和未知提交造成重复，先记 DEC-1187。

页面从当前项目活动 Document 中选择固定 AVAILABLE 版本，并可选当前已批准 Requirement 及 ELIGIBLE Evidence；显示文档标题、需求编码、证据标签与已知详情链接，不要求填写内部 UUID，不推断文档物理 Locator。读取完整分页并设上限，重复游标/候选身份/分页异常失败关闭。章节归档或当前用户非项目负责人/实施成员时不开放提交。CREATE Owner 在同事务重验来源，页面结果仅标 DRAFT。

提交前将请求体、原 Idempotency-Key、项目/章节/操作者保存于同会话存储。传输或回执结果不确定时保留原操作，页面要求先核对历史并显式确认，仅按原号与原内容重试；成功后才清理。无法保存或恢复原记录时停止提交，冲突操作号锁定。存储为浏览器 session 范围，不含 API 密钥、文档文件正文或 Locator，但可含用户填写的标题与声明；仍需保护使用终端。

候选/页面定向 7 项通过，覆盖分页与循环/重复/跨项目拒绝、AVAILABLE 版本、角色/归档/读取失败、DRAFT 固定请求、未知提交恢复和无法保存/解析原记录；前端全量 132 文件/1752 项、`vue-tsc`、Node TypeScript 和 Vite 生产构建通过。主 bundle 既有 >500KB warning，无本项运行失败。未将本项合同测试等同于实际 Edge/PG 写链。

兼容/升级/回滚：无 Schema/Migration、冻结 API、后端、权限、旧数据或新依赖变化；可撤新增入口/页面/候选客户端，原章节及历史版本保留。下一项 P03 Windows 11 Edge/隔离 PG 真实页面写入与失败恢复；正式信任源、Server2025、性能、Gate3/Pilot/Release 仍未通过，Debian13 实机依用户指令跳过。TraceLink：Gate2 API-04 → CR-SOL-003 → A02-P12 → DEC-1187 → 本 P02 → P03 → VALIDATE/Review → Gate3/Pilot。
