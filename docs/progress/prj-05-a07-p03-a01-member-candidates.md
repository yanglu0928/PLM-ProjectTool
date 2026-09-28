# PRJ-05-A07-P03-A01 成员精确用户候选 API

2026-09-28 / 0.1.0.dev0 / PASS（可选端点及Windows11隔离PostgreSQL验证；生产组合未挂载）。输入冻结成员创建合同及CR-PRJ-006，决策DEC-437；Gate2/Phase1前置通过。

Changed：新增Project-owned精确候选服务/未分配检查、Auth-owned规范用户名/ENABLED用户最小读取Port、带Origin/CSRF的只读语义POST可选路由和`create_app`显式装配插槽。仅当前ACTIVE项目负责人且真实Session/CSRF/License通过后查询；PostgreSQL摘要桶限流30/5分钟负责人+项目、10/5分钟负责人+项目+目标。缺失/停用/已分配统一空候选，历史REMOVED不阻止；只返回UserId/显示名，原写POST保留实时最终核验。增量API合同见`docs/api-contract/project-member-candidate-v1-increment.md`。不扩大`AUTH_USER_LIST`权限。

Tests：5新Unit、3新HTTP合同；全后端1566项OK、2项既有Windows符号链接权限跳过；隔离PostgreSQL18.6完成全head0049迁移，真实Session/User/Project/Member命中/统一未命中、非负责人/跨项目/部署管理员非成员、合成License拒绝、角色/归档/撤会话、目标10次/负责人30次持久限流及成员/Audit零新增验证；一次性PG进程/目录清理。开发wheel生成并检查4个新增模块包含，最终POST/CSRF版本SHA256 `7b03b92a3208afb6fd40687526df46f4f3eb1aba53476988410246fdc7e8ccc5`。首次临时集群中文安装路径编码失败，随后复制原PG18.6+pgvector到一次性英文目录；新增撤Session测试初次未递增lock_version被数据库防护拒绝，修夹具后完整重跑exit0。未改变生产数据库。

Migration：无；DB兼容head0049。API：新增可选只读端点，原冻结合同不修改。Architecture/权限：模块化单体，Auth与Project经Port，部署管理员目录保持关闭。Known Issues：Windows显式生产组合尚未挂载，正式信任/HTTPS、Server2025/Debian、浏览器成员创建、性能/质量Gate3及完整包未验。Next：P03-A02 Windows显式组合装配与缺信任源关闭；再做前端候选/部门选择和页面。回滚撤本项增量端点/Port/测试，不涉及数据迁移。
