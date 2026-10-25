# AI-04-A04-P04：Egress Preview 内部原子创建与受权读取

- 日期：2026-10-03
- 结果：PASS（Windows 11 / PostgreSQL 18.6 隔离验证）
- 依据：CR-AI-013、DEC-706～709、冻结 `EGRESS_PREVIEW_CREATE/GET`

新增 Egress Preview 内部 Application Service 和 PostgreSQL Repository。创建链在同一事务中验证 License、Session/CSRF、Project 成员权限、固定输入 Owner、当前 ACTIVE Provider/当前配置/AVAILABLE Model 路由和版本化最小外发策略，然后原子写入 Preview Root、SourceRef、Audit 与 Idempotency Receipt。同 Key/同请求从不可变 Preview 精确重放，请求语义不同时拒绝；数据类别按集合规范化，不因输入顺序产生假冲突。

读取链只向当前同项目受权成员返回安全投影，不返回秘密、正文或运行日志。为避免许可或成员身份在读取间隙变化，按平台既有安全模式在 License 校验前后各重验一次当前成员。公开 HTTP 路由与真实外发仍保持关闭。

验证：定向单元12项 PASS；Win11 隔离 PG18.6 真实路由/来源证明、Root+Source+Audit+Receipt 原子落库、精确重放、安全读取、请求冲突、Audit 故障回滚和跨项目隔离 PASS；后端2116运行/3跳过 PASS。首轮全量回归只发现 Project 权限矩阵数量断言仍为33，随新增两个冻结操作更新为35并补充精确角色断言后全量重跑。开发 wheel SHA-256 `2160e09b852932c733add19ef0ee6e5bc2cad10749d0cb8848716ab89be03673`。

边界：本项不新增 Schema，复用0068/0069；未实现 Authorize/Revoke 应用服务、Task Owner 投影、HTTP 或生产组合，不得据此宣称 Gate 3、UAT 或可使用程序包已通过。
