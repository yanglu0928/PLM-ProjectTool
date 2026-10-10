# SOL-03-A05-A02-P02：OutlineVersion 固定历史受权读取 Owner

日期：2026-10-09。结果：`SOL_03_A05_A02_P02_OUTLINE_VERSION_READ_OWNER_PG_PASS`；仅内部 Application Owner，公开 GET/LIST/Windows/UI 未挂载。

编码前检查：Phase 2 / 本 WBS；输入 Gate2 冻结 `SOL_OUTLINE_VERSION_GET/LIST`、A05-A01 只读授权及 A05-A02-P01 双 Scope 历史仓储；前置均已满足。本项仅组合 Solution Application 的 Session、License、Project 当前成员、目录存在性和版本历史，实体/Schema/API 不变。权限为四类有效项目成员，任何非成员/跨项目/失效 Session/License 均拒绝。验收涵盖 GET、版本号倒序 LIST/游标边界、根不存在、错误页和不完整 DTO 失败关闭；风险是历史固定引用不等于来源现时资格或业务批准。

实现 `OutlineVersionReadService`：先验 License、当前 Session 与 Project `SOL_OUTLINE_VERSION_GET/LIST`，同一 UoW 确认目录身份，再交固定历史仓储。GET 错项目/目录/版本统一受控 404；LIST 先证目录存在、按版本号倒序取 `page_size+1`，拒绝假游标/错序/跨项目或不完整投影。历史 DTO 保留当时三类固定引用与状态，不调用当前来源资格服务，也不把首次创建回执当成后来状态。无 DB Migration、公开 API/依赖/角色变化；撤未挂载 Owner 可回滚，历史不删除。

定向单元 3 项/8 子例通过。Win11 两套全新隔离 PostgreSQL 18.6/真实 Auth 与 CREATE 夹具：PROJECT 两版、GLOBAL 一版，实际项目成员读取、分页、跨项目/无效会话/License 拒绝均退出 0。后端全量 3461 通过、3 跳过、5303 子例。未在本项验证公开 HTTP、Windows 组合、前端/浏览器或正式服务账户；Gate3/UAT/发行仍未通过，GLOBAL 候选发布另见 CR-SOL-018。下一项 A05-A03 版本历史 GET/LIST 的签名分页游标与可选 HTTP 合同，须保持默认 404。

TraceLink：Gate2 API-04 → A05-A01 项目只读策略 → A05-A02-P01 双 Scope 历史仓储 → 本 Owner → GET/LIST HTTP/Windows/UI。
