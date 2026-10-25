# PRJ-05-A07-P03-A02：Windows 成员候选显式平台装配

- 日期/阶段：2026-09-28 / Phase 2；状态：PASS（Windows 11 隔离合成信任源）。依据 Gate 2、CR-PRJ-006、DEC-20260928-438；A01 前置 PASS。
- Changed：`--platform` 和 `--platform-write` 组合根复用真实 Session、License Guard、Project 授权、Auth 精确用户读取、Project 成员归属和 PostgreSQL 摘要限流后注入 A01 可选候选 Router。默认应用及 `--login` 均不注入；信任源启动失败则组合整体失败。
- Files：`apps/backend/src/plm_assistant/entrypoints/production_login.py`、`validation/prj-05-a07-p03-a01-member-candidates/verify.py`、`validation/prj-05-a07-p03-a02-member-candidate-composition/verify.py`，及本记录、增量合同、状态、版本说明、决策日志。
- Migration：无；兼容当前 DB head `20260927_0049`。API：非破坏性挂载已有 `POST /api/v1/projects/{project_id}/member-candidates:resolve`，请求/响应/权限未变；依赖无变化。升级：无数据操作；正式运行需原有目标账户信任源及受控平台模式。
- Tests：Windows 11 一次性 PostgreSQL 18.6 + pgvector 全迁移，真实 Session/User/Project/Member，两个平台模式精确命中/统一未命中、普通角色/管理员/跨项目 404、Origin/CSRF/License 403、默认与 login 404、缺成员 cursor 信任源启动失败、无成员/Audit 写；测试用临时库与运行目录退出清理。后端全量 1566 OK（2 项既有环境跳过）；开发 wheel 成功，SHA-256 `d8121de02cb3cb01b0ab94db359e8749c260ee28fb27724b0bc5cef8209e2c0d`。合成 Guard/游标/上传令牌/写 Secret 服务只供装配验收，不是正式信任锚。
- Result：PASS（本 WBS）；A01 限流/撤销/状态/归属继续由其隔离 PG 回归覆盖。Known Issues：正式目标账户 License/密钥/TLS，Windows Server 2025、Debian 13、浏览器交互、性能、POC-03 质量及 Gate 3/完整发行包仍未验或未完成。
- Next：`PRJ-05-A07-P03-A03` 前端精确候选及部门安全选择，随后页面与浏览器/PG 成员创建流；不以候选显示替代最终写入授权核验。
