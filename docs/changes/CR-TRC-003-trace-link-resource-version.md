# CR-TRC-003：TraceLink 状态命令资源版本

日期：2026-10-02；来源：`TRC-01-A07-P01` 撤销前置核查；状态：按 V1.1 持续授权先记录再实施。Gate 2 原冻结 Schema/API 提交 `64cdf09` 保留。

## 冲突与证据

冻结 API-01 规定可变资源状态命令携 `If-Match: "v<lock_version>"`、缺失 428、冲突 409；API-02 的 `TRACE_LINK_REVOKE`/`SUPERSEDE` 是状态命令。现有 `plm.trc_links` 只有 `ACTIVE/SUPERSEDED/REVOKED` 和原始创建字段，且守卫允许唯一一次终态转换，没有 `lock_version`。直接从 `link_state` 推算 ETag 会违反通用协议对数据库资源版本的定义，也不利于统一并发证明。

## 方案比较与选择

- A：把 `ACTIVE` 映成 `"v0"`、终态映成 `"v1"`，不改表。虽然当前状态图只有一次转换，但这是隐式版本，冻结 ETag 定义失真，未来扩展容易静默破坏；不选。
- B：增量 `BIGINT NOT NULL lock_version`，原 ACTIVE 历史为0、已终态历史为1；数据库守卫只允许由原 ACTIVE 转终态时自增，拒绝外部直接改版本或改写其他历史。选择 B。公开 API 路径/请求 DTO/状态码不变；Schema 增量可追溯，不追写原冻结提交。

## 影响、迁移与回滚

影响 Trace ORM 与 Alembic，另需后续内部撤销/替代服务、GET 强 ETag 与 HTTP `If-Match` 解析。迁移在事务内独占表，停用原守卫仅为受锁历史回填，随后立即恢复并加版本规则。空库和含 ACTIVE/REVOKED/SUPERSEDED 历史的升级都需验证；保留历史，不重建边。降级只允许所有行版本为0且均为 ACTIVE；若已有终态历史则拒绝降级，避免丢失已使用的并发版本；可通过数据库备份和正向修复恢复，不运行生产回滚。

## 验证计划与风险

验证空库 up/down、含历史 up、历史版本回填、终态一次自增、绕过修改/重复终态拒绝、有数据安全 down 与终态 down 拒绝；随后单元/隔离 PostgreSQL/后端回归与 wheel。P02 只修 Schema，不开启撤销路由；P03 内部命令必须当前 License/Session/CSRF/ProjectManager、行锁、If-Match、持久幂等与 Audit 同事务验证。关系 Owner 身份尚未定义，首个用户路径仅 PM，其他授权路径保持关闭。正式 License、三平台、Gate 3/发行仍按客观证据另验。

2026-10-02 P02 结果：增量 `20261002_0053` 在一次性 PostgreSQL 18 空库、含ACTIVE及含REVOKED/SUPERSEDED历史的三库执行；版本回填/终态自增/非法改写/可安全降级及终态拒绝降级均通过。P03业务命令和公开撤销仍未实现。完整后端/构建结果见P02进度记录。

2026-10-02 P03 结果：PROJECT当前ProjectManager内部撤销在真实Session/CSRF/License、项目行锁、原v0、通用持久收据及Audit同事务下完成；同Key并发仅一终态/一审计/一收据，审计失败回滚。无新Schema/API/依赖；关系Owner及公开HTTP仍关闭。正式信任、目标平台与Gate未因此通过。
