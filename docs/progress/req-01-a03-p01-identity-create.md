# REQ-01-A03-P01：Package / Requirement 身份创建 Owner

日期：2026-10-07。结论：`REQ_01_A03_P01_IDENTITY_CREATE_PASS`。下一项：`REQ-01-A03-P02`
Package 元数据、成员增删与持久幂等/Audit。

## 实现与边界

- 新增 Package/Requirement 两类严格命令、初始视图、同事务应用服务与 SQLAlchemy Repository；统一
  执行 Session/CSRF、License、当前 Project 角色、持久幂等、Audit 和提交。
- PM、ImplementationMember 可创建；CustomerManager、失效 Session、错误 CSRF、归档 Project 和
  License 拒绝均失败关闭。Requirement code 固定 ASCII 业务键并按项目内大写规范值唯一。
- Migration0112 新增两个 Owner-owned 不可变首成功结果表；触发器还会重证快照与初始 Root 精确一致，
  防止伪造历史重放。空结果历史可降0111，有结果则拒降。

## 验证

- Windows 11 / PostgreSQL 18.6：0111→head→0111→head、两次 drift、真实Session/三角色、License、
  两类首次/重放、异载荷、大小写重复、同Key并发、Audit故障回滚、快照伪造拒绝、撤权后历史拒读及
  有历史拒降全部通过；临时库清理。
- 定向23项通过；后端全量2966项通过、3项既有环境跳过；compileall通过。
- 开发wheel共1117项，包含P01应用/仓储与Migration0112，SHA-256
  `5dd79c19cadd08a913a6ba67134029b1b44f20c9cefc285647937cf2ac7673e1`，不是正式发行包。

无公开API、前端、依赖、Secret、客户数据或外发变化；P02/P03、A04 Version、HTTP/UI/Workflow、
Gate3/UAT/发行仍待。
