# PRJ-01-A04：Project 创建命令

- 日期：2026-09-25；结果：PASS（内部创建命令，非公开 API）；依据：冻结 API-02 `PROJECT_CREATE`、DM-02 Project/Department/ProjectMember、DEC-20260925-016。
- Changed：部署管理员 Session/CSRF 双检查与 License Guard 后，在同一事务锁定 ENABLED 初始负责人，创建 Project、默认或指定 Department、首位 ProjectManager 和 Audit；创建者不自动获得项目成员资格。Project/Department code 归一化，重复项目 code、已绑定负责人和无效负责人拒绝；Audit 失败回滚全部写入。
- Files：Project 创建服务与 SQL Repository、Auth-owned 负责人资格 Port、单元测试、临时 PostgreSQL 验证脚本、决策/进度/版本记录。Migration：无。API：无新公开路由。Permission：真实 Auth Session/CSRF 适配器；License 集成在临时库使用合成 Guard，生产信任源仍未接线。
- Tests：Windows 11/Python 3.13 后端 246/246 PASS；创建服务覆盖率 92%；PostgreSQL 18.6 临时库管理员/CSRF 拒绝、合成 License 拒绝、停用负责人拒绝、原子创建、默认/指定部门、重复 code、已分配用户和 Audit 回滚 PASS；wheel 构建 PASS。Windows Server 2025、Debian 13 本项未运行。
- Known Issues：公开 `POST /api/v1/projects` 仍未挂载，生产 License/安全运行配置未完成；当前不构成可用业务 API。后续 HTTP 层仍需持久幂等、请求边界和错误映射。
- Next：`PRJ-01-A05 Project 列表与详情读取`；随后项目元数据修改/归档、成员/部门命令及 API 接线。
