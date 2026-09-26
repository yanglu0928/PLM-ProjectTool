# PRJ-04-A01：Project 列表与详情 HTTP

- Phase/WBS：Phase 2 Platform Core / PRJ-04-A01。输入：冻结 API-01/API-02 `PROJECT_LIST`/`PROJECT_GET`、PRJ-01-A05 内部读取、Auth Session、License Guard；决策 `DEC-20260925-053`。
- Changed：新增仅显式注入的 Project 列表/详情 GET。可信 Host、Cookie Session、内部事务中再次检查 Auth/License/当前成员/部门授权；跨项目详情统一 404。Page 遵守单有效成员模型最多一项，`page_size` 1～200，未知/重复参数及 cursor 拒绝；详情输出强 ETag，响应不缓存。内部读取服务把真实 RuntimeLicenseError 分类为冻结的 403 `LICENSE_OPERATION_DENIED`，其他依赖故障仍为 503。
- Files：Project API、应用工厂、读取服务、契约与 PostgreSQL HTTP 验证、决策/状态/版本说明。
- Migration：无。API：实现已冻结路径的可选 Router，无 Breaking Change，默认及当前生产组合尚不挂载。
- Tests：Windows 11/Python 3.13 后端 384/384 PASS；默认 404、列表/详情、安全投影、分页参数、跨项目 404、Session 401、License 403、依赖 503；PostgreSQL 18 临时库 HTTP 多用户隔离、有效授权、许可证拒绝、撤销 Session 以及内部归档/成员/部门即时过滤 PASS；开发 wheel PASS。临时库已删除，数据库服务停止。
- Result：可选 Project 读取 HTTP 与隔离合成端到端 PASS；生产组合、正式发行信任源、PRJ-04 整体和 Gate 3 未完成。
- Known Issues：目前单有效成员约束让每页最多一项；若将来支持多项目，必须新增签名/完整性保护 keyset cursor。Windows Server 2025、Debian 13 未验证。
- Next：PRJ-04-A02 将 Project 读取安全接入显式 Windows 平台组合；正式 License 签发仪式继续独立待办。
