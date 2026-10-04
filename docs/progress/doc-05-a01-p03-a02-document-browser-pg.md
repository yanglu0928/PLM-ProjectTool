# DOC-05-A01-P03-A02 项目 Document 历史 Windows 11 浏览器/PG 验收

- 日期：2026-09-29；Phase 2 Platform Core；结果：`WINDOWS_11_SYNTHETIC_BROWSER_PG_PASS`。输入为 P01 客户端、P02 页面、A01 API/PG 验收及冻结 `DOCUMENT_LIST`。仅合成信任，不代表正式发行验收。
- Changed/Files：`validation/prj-05-a04-browser-project/serve.py` 增加互斥 `--document-history-browser` 模式，复用 A01 的 51 ACTIVE + 1 RESTRICTED + 1 FOREIGN 临时元数据；本记录、决策、状态及版本说明。无生产 API/Schema/Migration/权限/依赖变化，撤 browser 模式可回滚。
- Browser：Codex 隔离应用内浏览器使用合成项目成员登录；从“我的项目”进入 OWNED 项目详情，再由“查看项目文档历史”进入页面。首页可见 50 条且有续页按钮；加载后 51 条、末条 `Synthetic Browser Document 50`、无续页按钮；RESTRICTED 与 FOREIGN 均不可见。刷新后回到 50 条和续页按钮。页面明确仅显示元数据、跨页不是同一时刻快照。浏览器 DOM 状态与首轮可见截图已核；没有保留截图文件。
- Database/cleanup：完整第二轮夹具 exit0，SQL 核 OWNED 51 ACTIVE + 1 RESTRICTED、FOREIGN 1、2 项目、1 Session、1 ACTIVE Member；随机库、角色、临时 Vault 凭据不存在。PoC PostgreSQL 测试前停止，第二轮正常启动与 fast stop 恢复停止。
- Known issue：第一轮 UI 已观察到相同行为，但在会话切换时夹具句柄丢失、PoC PG 非正常停机。恢复日志显示自动 crash recovery；精确检查发现遗留随机库/角色和唯一 Test Vault 凭据，已核其临时归属后删除并验证为零。首轮不计完整验收，停机根因未证实；第二轮独立随机资源完整重跑通过，不把首轮清理或 PG 关闭写成 PASS。
- Tests/compatibility/upgrade：A01 独立 API/PG 已 exit0，A02 第二轮实际浏览器/SQL/清理 exit0；前端 P02 808 项/typecheck/build 先前通过，本项未重跑。兼容 DB0049/冻结 `/api/v1`，无升级步骤。正式 License/目标账户信任锚、Server 2025/Debian 13、性能质量、Gate 3/UAT/可用包仍待。
- Next：继续 Phase 2 未完成的独立 Document/业务读取与集成；生产信任源和 Release Gate 另行按证据关闭。
