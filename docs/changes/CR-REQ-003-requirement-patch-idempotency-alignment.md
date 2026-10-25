# CR-REQ-003：Requirement PATCH 幂等边界与冻结 API 对齐

- 日期：2026-10-08
- 状态：`ACCEPTED_UNDER_CONTINUOUS_AUTHORIZATION`
- 触发：`REQ-01-A10-A04` 公开 HTTP 编码前检查
- 基线：Gate 2 冻结 API-01/API-04；原冻结提交 `64cdf09`

## 问题与证据

API-04 将 `REQ_PATCH` 控制标记冻结为 `S,L,C,M,A`：必须提供强 `If-Match`，但不提供
`Idempotency-Key`。已实现的内部 `PatchRequirementIdentity` 却与 DEFER/REJECT/ARCHIVE
共用收据编排，强制要求幂等 key。如直接挂载 HTTP，要么破坏冻结 `/api/v1`，要么由服务器
伪造 key，两者均不可接受。DEFER、REJECT 和 ARCHIVE 的冻结控制均包含 `I`，不受此冲突影响。

## 方案比较与决定

1. 修改冻结 API，使 PATCH 必须提供幂等 key：拒绝，属于无必要的 `/api/v1` Breaking Change。
2. Router 派生或随机生成 key：拒绝，不能提供客户端重放语义，并会隐藏内部合同错配。
3. 保持冻结 API，将 PATCH 改为 `If-Match` + 单事务 Audit 的非幂等修改；DEFER/REJECT/
   ARCHIVE 继续使用 `Idempotency-Key` + `If-Match`：选定。

依用户持续授权，本 CR 记录后直接执行，不请求逐项确认。原冻结文档和提交保持不变。

## 影响、迁移与回滚

- 修改内部 PATCH Command/Service，不再接收或保留幂等 key/receipt；仍使用不可变
  Requirement command result 作为提交时投影证明，并与 Requirement 更新、Audit 同事务。
- DEFER/REJECT/ARCHIVE 的持久幂等、首成功结果重放和并发控制不变。
- 无 Schema/Migration、依赖、Secret、客户数据或外发变化；当前无生产数据迁移。
- 既有命令结果和 receipt 保留。如回滚内部代码，公开 PATCH 必须同时关闭，否则会重新出现
  合同冲突。

## 验证计划

- 定向单元测试证明 PATCH DTO 不存在 key，其他三个命令仍约束 key，且 Secret/key 不进 repr。
- Windows 11/PostgreSQL 18.6 验证 PATCH 不产生 receipt、旧 ETag 冲突、Audit 失败全回滚，
  DEFER/REJECT/ARCHIVE 重放保持。
- 完整后端回归、Alembic drift 和开发 wheel 通过后关闭 P01，再开放 P02 七个 HTTP。

## 执行结果

`REQ-01-A10-A04-P01` 已按方案 3 完成。Windows 11/PostgreSQL 18.6 验证 PATCH 不新增
receipt、强 ETag 冲突、Audit 失败回滚、DEFER/REJECT/ARCHIVE 重放和 drift；定向 5、
后端 3040/3、wheel 1156 项/`4c1c4cd4…d5`通过。P01 关闭，进入 P02 七个 HTTP。
