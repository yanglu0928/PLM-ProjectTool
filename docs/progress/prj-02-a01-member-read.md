# PRJ-02-A01：ProjectMember 授权列表读取

- 日期：2026-09-25；结果：PASS（内部查询链路，非公开 API）；依据：冻结 API-01 Page/keyset cursor、API-02 `PROJECT_MEMBER_LIST`/`ProjectMemberView`、DM-02 成员历史、DEC-20260925-019。
- Changed：License Guard 与当前 Session 后在同一事务执行 ProjectManager/CustomerManager 逐操作授权；Project Repository 只读所属项目的全部 ACTIVE/SUSPENDED/REMOVED 成员历史与部门名，Auth-owned Port 批量提供最小用户名显示投影。内部以 member_id 升序做稳定 keyset，返回 page 与仅供后续 HTTP 层编码的 after_id；对外不得直接暴露该 UUID，须转换 API-01 不透明 cursor。无权、跨项目和非管理角色统一隐藏。
- Files：Auth-owned 用户摘要适配器、Project 成员列表 Service/SQL Repository、单元测试、一次性 PostgreSQL 验证脚本、决策/进度/版本记录。Migration：无。API：无新公开路由。Permission：不以 Session 摘要代替当前成员事实；归档项目授权只读保留。
- Tests：Windows 11/Python 3.13 后端 265/265 PASS；成员查询服务覆盖率 96%；PostgreSQL 18.6 临时库角色矩阵、跨项目隔离、归档/历史读取、两页 keyset 与当前撤权 PASS；wheel 构建 PASS。Windows Server 2025、Debian 13 本项未运行。
- Known Issues：生产 License/安全运行配置与公开成员路由未完成；合成 License Guard 不代表生产授权可用。HTTP 层的不透明完整性保护 cursor 和请求/错误 Envelope 尚未接线。
- Next：`PRJ-02-A02 ProjectMember 创建命令`；随后角色/部门修改、暂停/恢复/移除。
