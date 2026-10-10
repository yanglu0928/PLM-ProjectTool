# HND-02-A04-A04：Action Windows 组合与真实 HTTP/PostgreSQL

日期：2026-10-05。结论：`HND_02_A04_A04_WINDOWS_COMPOSITION_PASS`。下一项：`HND-01-A04-A02` Handover PROJECT Review Subject、送审与终态消费。

## 实施结果

- 新增失败关闭的Windows Action读取组合：仅使用当前账户Windows凭据保管库中独立`handover-action-cursor-v1` 256-bit密钥，不创建、不记录、不导出密钥。
- 组合真实Auth Session身份、Project授权、License守卫、Handover读取Repository与专用cursor；两个显式Windows Platform模式均挂载LIST/GET，Login-only和默认app仍不发布该边界。
- 生产启动组合中任一依赖或密钥缺失时整体失败关闭并释放数据库运行时，不以部分路由降级为“可用”。

## 验证证据

- Windows 11/PostgreSQL 18.6隔离临时库从空库迁移到head且`alembic check`无新操作；真实HTTP路由验证两页同时间戳稳定分页、详情/ETag、cursor篡改400、未认证401、不存在404及业务零写；标记`HND_02_A04_A04_WINDOWS_COMPOSITION_PASS`。
- Windows组合/生产入口定向34项通过；后端全量2659项通过/3项既有条件跳过。
- 开发wheel构建并解包导入通过，SHA-256 `68d630b740cad7ade9f577cb92d5fe2842921ef4bb9972e073cacc41feb200a3`。
- 首轮隔离fixture把Action Root与seq0 Event分成两次提交，被Schema0100完整性触发器正确拒绝；已改为同一事务原子建立后完整重跑PASS，产品Schema/业务代码未因fixture放宽。

## 边界、升级与回滚

无Migration、冻结API破坏、新依赖、网络或数据外发。正式目标服务账户仍需在发行阶段预置独立cursor密钥；本轮验证使用不落盘的合成密钥，不代表目标账户已就绪。回滚时移除Windows组合注入和新入口文件，即恢复默认404；A02/A03内部Owner/可选Router不改。Gate 3继续BLOCKED。
