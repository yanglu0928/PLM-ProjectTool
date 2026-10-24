# SOL-05-A04-P05：SectionVersion VALIDATE Windows 显式组合

- 日期/版本：2026-10-12 / `0.1.0-dev.0`。承接 A04-P03 内部 Owner、P04 可选 HTTP 与冻结 API-04；仍属 Phase 2。
- 范围：仅在 Windows `--platform-write` 显式组合挂载 VALIDATE Router；默认及只读组合不开放写审计路径。组合复用既有 Session、当前 License、公有项目授权、Document/Requirement/Evidence 来源证明、固定 Version 读取、Audit 和持久收据；缺任何必要来源依赖拒启动，不退化为默认 PASS。
- 验证：Windows 11 一次性 PostgreSQL 18.6、真实 Session/Document/Requirement/Evidence/文件与 ASGI HTTP 合成链退出0：默认404、首次200、同 Key 原结果重放、不同 Key 来源 INELIGIBLE 得 `UNAVAILABLE`、实施成员、跨项目/CSRF/Origin/License/正文拒绝；SQL 核对三次新观察各一条 Audit/收据。后端全量3585通过/3跳过/5601子测试、开发 wheel 构建通过。
- 兼容/升级/回滚：无 Schema/Migration/依赖/冻结路径/角色或旧数据变化；关闭显式写模式或撤该可选组合可阻断新写入，已有 Audit/收据历史保留。
- 限制：合成 License 与 Review 来源不等于正式信任/客户确认；本项非 Edge 浏览器页面验收，也非 Server 2025/Debian 13、性能、Gate3 或 Pilot 通过。Trace/Spec 可信证明未接，`ready_for_review` 不得推定为 true。下一项 `SOL-05-A04-P06` 前端 VALIDATE 受控客户端，再接报告 UI 与真实浏览器。
