# SOL-05-A04-P08：Windows 11 Edge 章节验证浏览器验收

- 日期/版本：2026-10-12 / `0.1.0-dev.0`。承接 A04-P05 Windows 真实 HTTP/PG 组合与 P07 页面，验收模式见 DEC-1193。
- 范围：对既有一次性 SectionVersion CREATE 浏览器夹具增加独立 VALIDATE 模式；沿用随机合成账户、真实 Session/来源文件、Uvicorn、Edge 和可弃 PostgreSQL 18.6。浏览器从固定版本详情页实际点击“验证当前来源”，检查零正文 POST 200、六维报告与非可送审提示；人工模拟结果未确认的恢复场景后按原操作号重放，验证仍指向首次 Audit，并核对跨项目页面不泄漏验证按钮。
- 验证：新模式脚本退出0；SQL 中 `V1_SOL_SECTION_VERSION_VALIDATE` 收据和 `SOL_SECTION_VERSION_VALIDATED` Audit 各恰好1条，CREATE 版本/首结果/收据/Audit 仍各5条；原 CREATE 浏览器脚本复跑退出0且各6条，说明可选夹具扩展未改变旧模式。新 Edge Profile、端口与可弃库由夹具清理；随机测试口令不入 Git。
- 兼容/升级/回滚：仅验证资产扩展，无产品代码、Schema/Migration、冻结 API、依赖或旧数据变化。撤新模式与脚本可回滚；正式审计历史不删除。
- 限制/下一项：本项是 Windows 11 合成信任与单机浏览器链，非正式目标账户/HTTPS/发行公钥、Server2025/Debian13 实机、性能、Gate3、Pilot 或客户确认。Trace/Spec 仍 `UNAVAILABLE`，不能送审。下一项 `SOL-05-A04-P09`：追溯覆盖/StructuredSpec 缺口与可验证 Owner 前置核查，再按依赖推进 SOL-06/Review。
