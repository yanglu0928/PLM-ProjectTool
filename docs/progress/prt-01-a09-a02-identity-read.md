# PRT-01-A09-A02：Prototype Identity Read Owner

日期：2026-10-08。结论：`PRT_01_A09_A02_IDENTITY_READ_PASS`。下一项：
`PRT-01-A09-A03` 五类签名cursor合同与Windows KeyRef边界。

## 实现

- 新增PrototypePackage/Prototype内部授权读Service与PostgreSQL Repository，补齐
  `PRT_PACKAGE_LIST / PRT_PACKAGE_GET / PRT_LIST / PRT_GET`四项全项目成员只读策略；每次读取重证当前
  Session、License、Project、成员状态与角色，并取得授权读锁。
- 两类LIST按`updated_at DESC, identity DESC`稳定keyset分页，返回当前状态、创建/修改主体时间和强ETag；
  Prototype同时投影当前Approved Version指针。GET按Project复合身份隐藏跨项目/不存在资源。
- Package GET在同一事务读取并按UUID规范排序当前Prototype成员集合；只返回成员ID，不从历史命令结果重建
  当前事实。业务Service只接收成对cursor位置，拒绝半个位置、越界页大小和非规范身份。

## 验证

- Windows 11 / PostgreSQL 18.6隔离数据库验证Package/Prototype双页keyset、Package当前成员集合、强ETag、
  ARCHIVED历史可读、错误Project防枚举和成员暂停后即时撤权；Alembic drift通过。
- 首轮夹具直接写Root触发0123延迟创建闭包并被拒绝；改为事务局部`session_replication_role=replica`仅构造
  合成已有历史后完整重跑。生产读Service、查询和授权均走真实路径，未修改或放宽数据库保护。
- 新增读Owner单元6项；授权定向共13项通过；后端全量3176项通过、3项既有环境条件跳过；compileall通过。
  开发wheel共1218项，SHA-256
  `d091973a2f99f34d8a692235124c4102140a8406e5102b8666b7151f4712b67b`，不是正式发行包。

无Migration、公开API、依赖、Secret、客户数据或外发变化；Schema head保持0134。HTTP、cursor与Windows组合仍
关闭，Server 2025未外推，Debian 13按用户指令跳过；A10前端、A11 Workflow、Gate 3、UAT和发行仍待。
