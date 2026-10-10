# PRJ-04-A02：Windows 显式平台 Project 读取组合

- Phase/WBS：Phase 2 Platform Core / PRJ-04-A02。输入：冻结 Project GET 合同、PRJ-04-A01 可选 HTTP、Windows 生产平台组合；决策 `DEC-20260925-054`。
- Changed：`--platform` 和 `--platform-write` 在原有 Schema/License/游标签名来源通过后，用现行 SessionService 与 License Guard 构造 ProjectReadService 并挂载列表/详情；默认登录模式不挂载。服务再次从数据库核验当前会话、成员/部门状态，不信任前端 Project 权限摘要。
- Files：Windows 组合根、组合契约/临时 PostgreSQL 端到端验证、决策/状态/版本记录。
- Migration：无。API：只挂载已冻结的两个 GET，无 Breaking Change。
- Tests：Windows 11/Python 3.13 后端 384/384 PASS；默认模式 404、显式平台模式无 Cookie 401；PostgreSQL 18 临时库生产组合与真实 Session/Project SQL 多用户隔离、详情 ETag、跨项目 404、合成 License 拒绝 403 PASS；开发 wheel 构建 PASS。临时库已删除，数据库服务停止。
- Result：显式 Windows 组合与隔离合成端到端 PASS；正式发行公钥/目标账户信任源未供给，生产验收、PRJ-04 整体及 Gate 3 未完成。
- Known Issues：Windows Server 2025 服务账户/HTTPS 与 Debian 13 未验证；单有效成员模型仍限制列表最多一项。
- Next：PRJ-04-A03 Project 创建 HTTP 的幂等/管理员安全前置评估，然后按冻结命令逐项实现；真实签发仪式独立待办。
