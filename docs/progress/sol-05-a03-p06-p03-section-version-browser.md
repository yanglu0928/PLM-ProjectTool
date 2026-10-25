# SOL-05-A03-P06-P03：章节草案真实浏览器创建

日期：2026-10-12。结果：`SECTION_VERSION_CREATE_EDGE_PG_PASS`；限定 Windows 11、一次性合成 PostgreSQL 18.6 与受控测试账户，不代表正式安装或客户确认。

编码前检查：Phase 2；输入冻结 API-04、CR-SOL-003、A02-P11/P12 内部与 HTTP CREATE、A03-P04 历史/Windows 装配、P06-P01/P02 前端传输及页面；前置满足。单一问题为实际浏览器候选选择、创建与原号重放；仅新增可弃验收夹具，不改产品 API、Schema、权限、依赖或正式数据。风险是前端合同测试掩盖真实候选 API 不可用、重试重复写入或隔离库残留。

一次性 PG 升级至当前 Alembic head 后，使用合成项目、DocumentVersion、已批准 Requirement、ELIGIBLE Evidence 和五个已有 SectionVersion；另建临时实施成员及随机测试口令。Uvicorn 装配实际登录/Session、四类候选 GET、Section GET、SectionVersion CREATE/历史 GET；Edge 无头隔离配置登录并从章节详情进入创建页，观察 Document/DocumentVersion/Requirement/Evidence GET 均 200。选定固定来源提交后 CREATE 返回 201；在同会话注入已观察的原操作记录模拟确认响应丢失后的页面恢复，回到页面只允许原号与原请求体经人工确认重试，第二次 201 指向同一版本；跨项目路由不开放表单。最终 PG 核对该章节版本、首次结果、CREATE 收据和创建审计均由 5 增至 6，而非 7。测试浏览器配置、服务器与一次性 PG 在脚本结束时清理。

验证：脚本完整运行两次退出 0；最后一次改为每次随机生成测试口令并通过子进程环境传递，避免将固定口令写入仓库或命令行。首轮观察 4 类候选 GET 和两个 CREATE 201；末轮进一步确认两次结果为同一版本。夹具还复跑既有真实 Auth/Document/Evidence/Requirement 来源证明与 Owner 并发/回滚断言，均 PASS。未模拟真正的传输中途断线；本项只证明已提交原号恢复和实际同号重放，不把合成来源当客户确认或生产信任。

兼容/升级/回滚：仅新增 `validation` 脚本；无 Migration、产品 API、旧数据或配置变更，可移除本夹具而不影响运行。下一项 `SOL-05-A04-P01` SectionVersion VALIDATE 前置核查，随后逐项完成 VALIDATE/Review/Trace 与 Pilot 业务链。正式服务账户/HTTPS/公钥、Server 2025、20 并发、Gate3/Pilot/Release 仍未通过；Debian 13 实机依用户指令跳过。TraceLink：Gate2 API-04 → CR-SOL-003 → A02-P11/P12 → A03-P06-P01/P02 → 本 P03 → VALIDATE/Review → Gate3/Pilot。
