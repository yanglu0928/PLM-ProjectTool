# CR-TRC-001：Trace 目标证明与写入同事务

日期：2026-09-26。来源：TRC-01-A05 编码前核查。状态：按用户持续授权记录并实施；验收结果另见进度记录。

## 冲突与证据

TRC-01-A03 的 `TraceTargetOwnerPort.prove` 调用 `DocumentReadService.get_version`，后者自行开启并结束事务。若先证明再于另一事务写 TraceLink，授权成员、Document 状态、DocumentVersion 可用性或 FileObject 可用性可在两次事务之间变化。A04 无环锁只保护图边，不保护端点事实。不能把现有证明直接用于正式写入并称为同事务安全。

## 方案与选择

- A：沿用独立读事务，在写入前重查。仍存在重查与写入间竞态，不采用。
- B：Owner Port 接收调用方事务；Document 提供仅供固定版本证明的事务内读取，锁定 Session/Project 授权事实与 Document/Version/FileObject 行；Trace 创建命令在同一事务内完成目标证明、无环、收据和 Audit。选择 B。

与原冻结基线的差异：不改 `/api/v1`、实体关系或已冻结字段，只加强内部 Trace Owner 接口和锁语义；原提交 `64cdf09` 与 A03 历史记录保留。仅 `document/DOC-02` Owner 当前可用，其他 Owner 不因此获得写入资格。

## 影响、迁移与回滚

数据库无 Migration，现有 Document 公共只读行为不变。内部 Owner 实现须改为接受调用方事务；尚无正式 Trace 写路由。回滚可恢复旧内部接口，但在重新建立事务一致性前必须保持 Trace 创建关闭。锁可能增加同一文档/项目状态修改的等待，须验证并发序列且避免先获取图锁再取得目标锁。

## 验证计划与剩余风险

单元验证错误映射和事务传递；隔离 PostgreSQL 18.6 验证同事务授权、固定版本/文件状态、并发状态变更阻塞或失败关闭；全量后端回归、开发 wheel。License 运行时 Guard 的跨事务信任状态仍遵循现有平台机制，不把合成信任源声明为生产 PASS。真正创建命令及其他 Owner 后续独立验收。

验证结果：2026-09-26 Windows 11 后端 595 项无失败（2 项环境跳过）；隔离 PostgreSQL 18.6 同事务文件与成员更新锁超时、状态撤权后拒绝；开发 wheel PASS。仅本前置修正完成，A05 创建命令仍未完成。
