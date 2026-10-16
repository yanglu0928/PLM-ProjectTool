# SUR-01-A05-A03：Survey metadata 与归档 Owner

日期：2026-10-06。结论：`SUR_01_A05_A03_SURVEY_STATE_OWNER_PASS`。下一项：`SUR-01-A05-A04` Survey 五个普通写 HTTP。

## 编码前检查与变更

冻结 API-04 已定义 `SURVEY_PATCH` / `SURVEY_ARCHIVE`，但 Schema0105 守卫禁止名称与状态变化。按持续授权先登记 `CR-SUR-004`，再新增向前 Migration0106；不改写0105或 Gate 2 冻结提交。

0106只开放两种精确形态：ACTIVE Survey 的 `name` 单字段更新，以及 `ACTIVE -> ARCHIVED`。两者均要求 Root 行锁、锁版本递增、当前操作者和更新时间有效，并在数据库与仓储双层拒绝任何 IN_REVIEW Version。既有 Review Owner 的正式指针与 Version 状态路径保持不变；Survey身份、Project、创建信息、正式指针、Version内容与历史删除未开放。

内部 Service 每次验证 License、Session/CSRF 与当前 Project 成员：PATCH 仅 ProjectManager/ImplementationMember，ARCHIVE 仅 ProjectManager。PATCH 规范化 Unicode/首尾空白、强 ETag 并拒绝无变化写；ARCHIVE 使用项目级持久幂等收据并精确重放首次 ARCHIVED 结果。两者在同事务写不可变 Audit，提交前再次检查 License。

## 兼容、迁移与回滚

无新表列、冻结 URL/DTO、依赖、配置、Secret、网络、外发或客户数据变化。公开 Router 仍关闭。0106只替换共享守卫函数；存在 ARCHIVED 或 PATCH/ARCHIVE Audit 历史时拒绝降级。可停止装配状态 Owner 阻止新写；既有归档与审计必须保留，只能向前修复，不能恢复 ACTIVE。

## 客观验证

- 定向17项通过（Service、Schema、授权矩阵、Migration head合同）。
- Windows 11 / PostgreSQL 18.6：空库0106升降重升、两次drift、PM/实施成员/客户角色、跨项目、强ETag、在审PATCH/ARCHIVE拒绝、归档精确重放、License拒绝、Audit失败全链回滚、归档后数据库写拒绝与历史拒降通过。
- 首次全量仅发现Migration head合同仍固定0105；更新为0106后定向及第二次全量通过，未掩盖失败。
- 后端全量：2829项通过，3项跳过。
- wheel内容：`SUR_01_A05_A03_WHEEL_IMPORT_PASS`，1045 entries；SHA-256 `26980b48d6ede0efb24621d278ec8200c6ca903b372a8672ef853ce826996443`。

已知未完成：A04五个普通写 HTTP；A05原子业务送审；A06四读 HTTP/cursor；A07 Windows组合与真实 HTTP/PG；Survey Round/Response/Conclusion、Server 2025、Debian 13实机、Gate 3和发行验收仍按总状态跟踪。
