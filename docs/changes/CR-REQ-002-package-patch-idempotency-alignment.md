# CR-REQ-002：RequirementPackage PATCH 幂等边界与冻结 API 对齐

- 日期：2026-10-08
- 状态：`ACCEPTED_UNDER_CONTINUOUS_AUTHORIZATION`
- 触发：`REQ-01-A10-A03` 公开 HTTP 编码前检查
- 基线：Gate 2 冻结 API-01/API-04；原冻结提交 `64cdf09`

## 问题与证据

API-04 将 `REQ_PACKAGE_PATCH` 控制标记冻结为 `S,L,C,M,A`：必须提供强 `If-Match`，
但不提供 `Idempotency-Key`。已实现的内部 `PatchRequirementPackage` 却与 ADD/REMOVE 共用
收据编排，强制要求幂等key。如直接挂载 HTTP，要么破坏冻结 `/api/v1`，要么由服务器
伪造key，两者均不可接受。

## 方案比较与决定

1. 修改冻结API为PATCH必须幂等key：拒绝，属于无必要的`/api/v1` Breaking Change。
2. Router派生或随机生成key：拒绝，既不能提供客户端重放语义，又隐藏内部合同错配。
3. 保持冻结API，将PATCH改为`If-Match`+单事务Audit的非幂等修改；ADD/REMOVE仍保持
   `Idempotency-Key`+`If-Match`：选定。

依用户持续授权，本CR记录后直接执行，不请求逐项确认。原冻结文档和提交保持不变。

## 影响、迁移与回滚

- 修改内部PATCH Command/Service，不再接收或保留幂等key/receipt；仍使用不可变
  Package command result作为提交时投影证明，并与Package更新、Audit同事务。
- ADD/REMOVE的持久幂等、首成功结果重放和并发控制不变。无Schema/Migration、依赖、
  Secret、客户数据或外发变化。
- 当前无生产数据迁移；既有命令结果和receipt保留。如回滚内部代码，公开PATCH必须同时
  关闭，否则会重新出现合同冲突。

## 验证计划

- 定向单元测试证明PATCH DTO不存在key、ADD/REMOVE仍约束key，且Secret/key不进repr。
- Windows 11/PostgreSQL 18.6验证PATCH不产生receipt、旧ETag冲突、Audit失败全回滚，
  ADD/REMOVE重放保持。
- 完整后端回归、Alembic drift和开发wheel通过后关闭P01，再开放P02 HTTP。

## 执行结果

`REQ-01-A10-A03-P01` 已按方案3完成。Windows 11/PostgreSQL 18.6验证PATCH不新增
receipt、强ETag冲突、Audit失败回滚、ADD/REMOVE重放和drift；定向6、后端3033/3、
wheel1153项/`c52ddd2b…e324`通过。P01关闭，进入P02 HTTP。
