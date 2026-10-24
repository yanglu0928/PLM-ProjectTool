# CR-API-001：通用持久幂等收据增量

日期：2026-09-25；状态：ACCEPTED_UNDER_CONTINUOUS_AUTHORIZATION；来源：Gate 2 冻结 API-01 可重试命令、AUT-03-A10 注销前置。

## 冲突与证据

冻结 API-01 要求可重试 POST 按 actor、project、operation、key 持久隔离，保存规范化请求指纹和结果引用；同 key/同 payload 返回原状态与结果，不同 payload 返回 `CONFLICT_IDEMPOTENCY`。当前 Schema 仅有 `plt_configuration_command_receipts`，受数据库 CHECK 限为三种配置命令，且结果外键只指向配置对象，不能为 Auth 注销或其他模块安全复用。进程内缓存无法跨 Uvicorn Worker、重启或事务崩溃恢复。直接开放注销会违反冻结合同。

## 方案与选择

- A：去掉注销的 `Idempotency-Key` 或仅内存去重。拒绝；破坏冻结 API 并发/恢复合同。
- B：修改配置专用收据表以混存 Auth/Project 等操作。拒绝；破坏其已有 CHECK/外键/历史语义，扩大回滚风险。
- C：在 Platform 基础设施新增 `plt_idempotency_receipts` 通用收据；业务模块通过同一数据库事务 reserve→业务变更/Audit→complete，并只保存 Key 摘要、请求指纹、非敏感结果类型/UUID/状态码。选择 C；配置现有专用表保留原样，不追写 Gate 2 冻结提交。

## 差异、风险、迁移与回滚

新增 ORM/Alembic Migration，属于冻结 DB Schema 的可追溯增量；不改冻结 `/api/v1` 路径、技术栈或产品 Scope。唯一范围 `(actor_id, project_id, operation, key_digest)` 使用 PostgreSQL `NULLS NOT DISTINCT`，覆盖部署级无 ProjectId 情况。`operation` 须包含 API 版本，例如 `V1_AUTH_LOGOUT`。已完成收据只允许追加、不得修改/删除；PENDING 只能在同一事务完成，若异常提交为 PENDING，后续安全拒绝并等待受控恢复，不自动重做副作用。收据不存原始 Key、Secret/正文、Cookie/Token 或完整响应。结果引用须由调用方确保足以重建原语义；不能以当前可变资源视图冒充历史响应。

迁移 `20260925_0015` 支持空库升级与已有数据升级，不修改旧表。Downgrade 仅在新收据表为空时允许；非空时拒绝以防丢失去重历史。自动清理暂不启用，避免过期后重复执行不可逆命令；Retention 策略另行验收。回滚代码可停止新命令挂载，但有收据时不得删表。跨进程并发使用 PostgreSQL 唯一约束作为仲裁，必须验证同 payload 重放、不同 payload 冲突、事务回滚重试和并发单赢家。

## 验证计划

ORM/Metadata 与 Alembic up/down 合同；PostgreSQL 18.6 一次性空库迁移、已有配置数据升级、部署/项目范围隔离、并发去重、冲突、失败回滚、已完成不可变和有数据 downgrade 拒绝；Windows 11 全量后端测试与 wheel 构建。该 CR 不自动完成注销、Server 2025/Debian、Gate 3 或 UAT。
