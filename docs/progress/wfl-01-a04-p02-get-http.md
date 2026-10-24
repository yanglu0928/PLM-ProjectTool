# WFL-01-A04-P02：可选 Workflow GET

- Phase 2；编码前检查冻结 API-02/DM-02/V1 配置及内部读 PASS；只实现 GET 安全适配，不装配 Windows 生产模式或写路由。
- Changed/Files：`workflow/api/read_workflow.py`、API 包与 create_app 可选 Router 注入、五项 HTTP 单元测试、既有隔离脚本 HTTP 扩展、运行合同/版本/状态/决策文档。显式白名单投影，不 asdict ORM 或通用序列化；返回前再验证投影且 ProjectId 必须与路径一致。
- API：实现冻结 WORKFLOW_GET（可选挂载）；成功包络/trace/ETag/no-store，未知 query 拒绝；Host/Cookie/Session 与应用授权/License 接线；内部异常映射 SYSTEM_UNAVAILABLE，不泄露具体原因。无 Breaking Change/Schema/依赖变化，升级无动作。
- Tests：Windows 11/Python 3.13 后端 641 项无失败（2 项既有符号链接环境跳过）。新增 HTTP 单元测试覆盖安全字段、ETag/trace、缺 Cookie/Host/query、注册错误映射、过期 Session、默认 404、外国项目投影禁止返回。
- PostgreSQL：扩展 `validation/wfl-01-a03-p05-authorized-initialize/verify.py`，真实 SessionService/SessionRepo/Project 授权/Workflow 表、合成 License；四角色 200/归档 200、跨项目及无成员 Admin/缺实例 404、无 Cookie/撤销 401、Host/License 403、query 400；计数证明 GET 未初始化或重复 Audit。既有内部/并发撤权锁回归同时 PASS。
- Build：开发 wheel 包含 Router PASS；SHA-256 `fb1ceea16b4862de15136996150990dbfa9b4bd37e564acc7c6c7b63c180fba3`。
- Result：可选 HTTP 范围 PASS；默认和 Windows 显式平台均尚未挂载。HTTP 是合成测试用户/License，不代表生产账户、公钥/密钥来源、安装、性能、真实客户 Review 或 Gate 3/UAT 通过。
- 清理：脚本自建随机库删除，测试 PostgreSQL 服务停止；无生产/客户数据操作。
- Known Issues/Next：WFL-01-A04-P03 Windows 显式平台读组合装配/真实 Session 端到端及缺信任源关闭；启动、Checklist/历史/推进与实际 Gate 仍待。Server 2025 未运行，Debian 13 暂不验证。
